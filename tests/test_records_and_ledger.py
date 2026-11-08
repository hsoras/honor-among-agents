"""Shared spend ledger across processes, halt and fail-closed rules, token accounting, append-only run
records, interrupted and crashed runs, and folder loading. Mock and fake clients only: no network."""

import contextlib
import io
import json
import random
import shutil
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import run  # noqa: E402
from episode import EpisodeSpec, run_episode  # noqa: E402
from llm import Budget, BudgetExceeded, Completion, OpenRouterClient  # noqa: E402
from records import key_of, load_run, select_episodes  # noqa: E402

PRICES = {"test/model": (1e-6, 1e-6)}


class FakeClient:
    """Returns valid skip replies with a fixed reported cost and finish reason."""

    def __init__(self, cost=0.0, finish_reason="stop", reasoning_tokens=0):
        self.cost, self.finish_reason, self.reasoning_tokens = cost, finish_reason, reasoning_tokens
        self.calls = 0

    def complete(self, *, model, system, user, meta, temperature, max_tokens):
        self.calls += 1
        return Completion(text='{"action":"skip"}', prompt_tokens=10, completion_tokens=20,
                          cost_usd=self.cost, finish_reason=self.finish_reason, provider="fake",
                          reasoning_tokens=self.reasoning_tokens)


def spec(**kw):
    base = dict(model="test/model", board=True, n=2, rep=0, seed=7, turns_per_agent=2,
                starting_points=1, post_max_chars=280, temperature=1.0, max_tokens=16384)
    base.update(kw)
    return EpisodeSpec(**base)


class SharedLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pg-ledger-"))
        self.ledger = self.tmp / "spend_ledger.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def budget(self, total=0.05, episode=10.0, calls=1000):
        return Budget(calls, total, episode, PRICES, self.ledger)

    def call(self, b, client, meter=None):
        return b.call(client, model="test/model", system="s", user="u", meta={},
                      temperature=1, max_tokens=1000, meter=meter or b.meter())

    def test_two_invocations_share_the_cap_even_when_one_was_created_before_the_other_spent(self):
        # b2 starts with an empty ledger. b1 then spends. b2 must see b1's spend on disk, not its own stale copy.
        b2 = self.budget()
        b1 = self.budget()
        expensive = FakeClient(cost=0.02)
        for _ in range(3):
            self.call(b1, expensive)
        self.assertAlmostEqual(json.loads(self.ledger.read_text())["charged_usd"], 0.06, places=4)
        with self.assertRaisesRegex(BudgetExceeded, "total dollar cap"):
            self.call(b2, FakeClient(cost=0.0))  # disk already holds 0.06 > 0.05 cap

    def test_concurrent_processes_do_not_overwrite_each_others_spend(self):
        # Two budgets each reserve and settle; a lost update would leave the total below the sum.
        b1, b2 = self.budget(total=100.0), self.budget(total=100.0)
        for i in range(10):
            self.call(b1 if i % 2 else b2, FakeClient(cost=0.01))
        self.assertAlmostEqual(json.loads(self.ledger.read_text())["charged_usd"], 0.10, places=4)
        self.assertEqual(json.loads(self.ledger.read_text())["calls"], 10)

    def test_call_cap_is_shared_across_invocations(self):
        b1 = self.budget(calls=2, total=100.0)
        b2 = self.budget(calls=2, total=100.0)
        self.call(b1, FakeClient())
        self.call(b2, FakeClient())
        with self.assertRaisesRegex(BudgetExceeded, "call cap"):
            self.call(b1, FakeClient())

    def test_halt_refuses_new_calls_and_keeps_the_reason(self):
        b = self.budget(total=100.0)
        client = FakeClient()
        b.halt("operator stop")
        with self.assertRaisesRegex(BudgetExceeded, "operator stop"):
            self.call(b, client)
        self.assertEqual(client.calls, 0)

    def test_failed_settlement_fails_closed_after_the_paid_call(self):
        b = self.budget(total=100.0)
        original = b._write_totals
        writes = []

        def flaky(usd, calls):
            writes.append(usd)
            if len(writes) == 2:  # the settlement write after the call
                raise OSError("disk full")
            return original(usd, calls)

        with mock.patch.object(b, "_write_totals", side_effect=flaky):
            comp = self.call(b, FakeClient(cost=0.001))  # the paid call returns normally
        self.assertEqual(comp.text, '{"action":"skip"}')
        self.assertIn("could not be settled", b.halted)
        with self.assertRaisesRegex(BudgetExceeded, "could not be settled"):
            self.call(b, FakeClient())

    def test_ledger_that_vanishes_mid_run_stops_the_run(self):
        b = self.budget(total=100.0)
        self.call(b, FakeClient())
        self.ledger.unlink()
        with self.assertRaisesRegex(BudgetExceeded, "disappeared"):
            self.call(b, FakeClient())

    def test_corrupt_ledger_is_refused_at_startup(self):
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self.ledger.write_text("{not json")
        with self.assertRaises(ValueError):
            self.budget()

    def test_legacy_ledger_without_call_count_is_still_read_and_counts_toward_the_cap(self):
        # Ledgers written before this change hold only charged_usd. Their spend must still count.
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self.ledger.write_text(json.dumps({"charged_usd": 0.0499}))
        b = self.budget(total=0.05)  # worst case of one call is about 0.0015, so 0.0499 + it exceeds 0.05
        with self.assertRaisesRegex(BudgetExceeded, "total dollar cap"):
            self.call(b, FakeClient(cost=0.0))
        self.assertEqual(b.calls, 0)  # refused before the request was sent


class TokenAccountingTests(unittest.TestCase):
    def test_reasoning_tokens_are_parsed_from_usage_details(self):
        body = {"choices": [{"message": {"content": "x"}, "finish_reason": "length"}],
                "usage": {"prompt_tokens": 9, "completion_tokens": 16384,
                          "completion_tokens_details": {"reasoning_tokens": 15000}, "cost": 0.008}}
        resp = mock.MagicMock()
        resp.read.return_value = json.dumps(body).encode()
        resp.__enter__.return_value = resp
        with mock.patch("llm.urllib.request.urlopen", return_value=resp):
            c = OpenRouterClient(api_key="k").complete(model="m", system="s", user="u", meta={},
                                                       temperature=1, max_tokens=16384)
        self.assertEqual((c.completion_tokens, c.reasoning_tokens, c.finish_reason), (16384, 15000, "length"))

    def test_missing_reasoning_detail_counts_as_zero(self):
        body = {"choices": [{"message": {"content": "x"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2}}
        resp = mock.MagicMock()
        resp.read.return_value = json.dumps(body).encode()
        resp.__enter__.return_value = resp
        with mock.patch("llm.urllib.request.urlopen", return_value=resp):
            c = OpenRouterClient(api_key="k").complete(model="m", system="s", user="u", meta={},
                                                       temperature=1, max_tokens=8)
        self.assertEqual(c.reasoning_tokens, 0)

    def test_episode_summary_counts_length_limited_and_token_totals(self):
        tmp = Path(tempfile.mkdtemp(prefix="pg-tokens-"))
        try:
            client = FakeClient(cost=0.0, finish_reason="length", reasoning_tokens=5)
            budget = Budget(1000, 100.0, 100.0, PRICES, None)
            summary = run_episode(spec(), client, budget, tmp / "ep")
            self.assertEqual(summary["max_tokens"], 16384)
            self.assertEqual(summary["length_limited_replies"], summary["calls"])
            self.assertEqual(summary["reasoning_tokens"], 5 * summary["calls"])
            self.assertEqual(summary["completion_tokens"], 20 * summary["calls"])
            self.assertEqual(summary["status"], "truncated")  # this client never votes to end
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_unexpected_exception_in_an_episode_is_recorded_as_crashed(self):
        tmp = Path(tempfile.mkdtemp(prefix="pg-crash-"))

        class Broken(FakeClient):
            def complete(self, **kw):
                raise KeyError("bug")

        try:
            summary = run_episode(spec(), Broken(), Budget(1000, 100.0, 100.0, PRICES, None), tmp / "ep")
            self.assertEqual(summary["status"], "crashed")
            self.assertIn("KeyError", summary["error"])
            self.assertTrue((tmp / "ep" / "episode.json").exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class RunCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pg-run-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_main(self, *extra, expect_raise=None):
        argv = ["run.py", "--mock", "--out", str(self.tmp), *extra]
        out = io.StringIO()
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(out):
            if expect_raise:
                with self.assertRaises(expect_raise):
                    run.main()
            else:
                run.main()
        return out.getvalue()

    def only_run(self):
        dirs = [d for d in self.tmp.iterdir() if d.is_dir()]
        self.assertEqual(len(dirs), 1)
        return dirs[0]

    @staticmethod
    def events(run_dir, name):
        return [json.loads(l) for l in (run_dir / "records.jsonl").read_text().splitlines()
                if json.loads(l)["event"] == name]

    def test_default_max_tokens_is_16384_and_flag_overrides_it(self):
        self.assertEqual(run.CONFIG["max_tokens"], 16384)
        self.run_main("--max-tokens", "12000")
        cfg = json.loads((self.only_run() / "config.json").read_text())
        self.assertEqual(cfg["config"]["max_tokens"], 12000)

    def test_invalid_max_tokens_is_refused(self):
        with self.assertRaises(SystemExit):
            self.run_main("--max-tokens", "100")

    def test_complete_mock_run_writes_one_record_per_episode_and_is_complete(self):
        self.run_main()
        d = self.only_run()
        self.assertEqual(len(self.events(d, "episode_started")), 36)
        self.assertEqual(len(self.events(d, "episode_finished")), 36)
        self.assertEqual(self.events(d, "run_finished")[-1]["complete"], True)
        loaded = load_run(d)
        self.assertEqual(len(loaded["episodes"]), 36)
        self.assertEqual(loaded["incomplete"], [])
        self.assertTrue(loaded["has_metrics"])

    def test_records_are_appended_not_rewritten(self):
        self.run_main()
        d = self.only_run()
        lines = (d / "records.jsonl").read_text().splitlines()
        self.assertEqual(json.loads(lines[0])["event"], "run_started")
        self.assertEqual(json.loads(lines[-1])["event"], "run_finished")

    def test_interrupted_run_accounts_for_every_job_and_is_marked_incomplete(self):
        real_as_completed = run.as_completed

        def interrupt_after_first(fs):
            it = real_as_completed(fs)
            yield next(it)
            raise KeyboardInterrupt

        with mock.patch("run.as_completed", side_effect=interrupt_after_first):
            self.run_main(expect_raise=KeyboardInterrupt)
        d = self.only_run()
        finished = len(self.events(d, "episode_finished"))
        not_started = len(self.events(d, "episode_not_started"))
        self.assertEqual(finished + not_started, 36)  # every planned episode has exactly one outcome
        self.assertGreaterEqual(not_started, 1)
        metrics = json.loads((d / "metrics.json").read_text())
        self.assertFalse(metrics["run"]["complete"])
        self.assertIsNotNone(metrics["run"]["stopped"])
        loaded = load_run(d)
        self.assertEqual(sum(1 for i in loaded["incomplete"] if i["status"] == "not_started"), not_started)

    def test_crashing_episode_is_recorded_and_the_rest_of_the_grid_still_runs(self):
        real = run.run_episode

        def flaky(sp, client, budget, ep_dir):
            if sp.n == 4 and sp.board:
                raise RuntimeError("injected bug")
            return real(sp, client, budget, ep_dir)

        with mock.patch("run.run_episode", side_effect=flaky):
            out = self.run_main()
        d = self.only_run()
        self.assertEqual(len(self.events(d, "episode_crashed")), 6)  # n=4, board, 2 models x 3 reps
        self.assertEqual(len(self.events(d, "episode_finished")), 30)
        self.assertIn("RUN INCOMPLETE", out)
        loaded = load_run(d)
        self.assertEqual(sum(1 for i in loaded["incomplete"] if i["status"] == "crashed"), 6)


class RecordSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pg-select-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make_episode(self, run_dir, status, model="a/b", cond="board", n=2, rep=0, turns=1):
        slug = model.replace("/", "_")
        ep = run_dir / "episodes" / f"{slug}__{cond}__n{n}__r{rep}"
        ep.mkdir(parents=True)
        summary = {"model": model, "condition": cond, "n": n, "rep": rep, "status": status,
                   "total_final": n, "mean_final": 1.0, "plays": 0, "transfers": 0, "posts": 0,
                   "invalid": 0, "ruined_agents": 0, "final_balances": {}, "turns": turns, "calls": turns,
                   "cost_usd": 0.0, "max_stake": 0, "total_gain": 0, "stake_total": 0, "error": None}
        (ep / "episode.json").write_text(json.dumps({"summary": summary}))
        (ep / "transcript.jsonl").write_text("\n".join("{}" for _ in range(turns)) + "\n")
        return ep

    def make_run(self, name):
        d = self.tmp / name
        d.mkdir()
        return d

    def test_completed_record_beats_a_later_crashed_attempt_and_keeps_it_visible(self):
        a = self.make_run("20261107-000001")
        self.make_episode(a, "completed")
        b = self.make_run("20261107-000002")
        (b / "records.jsonl").write_text(json.dumps({"event": "episode_crashed", "model": "a/b",
                                                    "condition": "board", "n": 2, "rep": 0,
                                                    "error": "boom"}) + "\n")
        chosen, superseded = select_episodes([load_run(a), load_run(b)])
        self.assertEqual(len(chosen), 1)
        self.assertEqual(chosen[0]["status"], "completed")
        self.assertEqual(len(superseded), 1)
        self.assertIn("superseded_by", superseded[0])

    def test_folder_without_episode_json_is_an_incomplete_entry_not_a_silent_drop(self):
        a = self.make_run("20261107-000003")
        ep = a / "episodes" / "a_b__noboard__n4__r1"
        ep.mkdir(parents=True)
        (ep / "transcript.jsonl").write_text("{}\n{}\n")
        loaded = load_run(a)
        self.assertEqual(loaded["episodes"], [])
        self.assertEqual(loaded["incomplete"][0]["status"], "incomplete")
        self.assertEqual(loaded["incomplete"][0]["turns_logged"], 2)
        chosen, _ = select_episodes([loaded])
        self.assertEqual(chosen[0]["key"], key_of("a/b", "noboard", 4, 1))

    def test_run_kinds_classify_pilot_mock_and_multiplier_folders(self):
        from records import run_kind
        self.assertEqual(run_kind("20261107-1-pilot"), "pilot")
        self.assertEqual(run_kind("20261107-1-mock"), "mock")
        self.assertEqual(run_kind("20261107-1-multiplier-x2-10"), "multiplier")
        self.assertEqual(run_kind("20261107-1"), "grid")


if __name__ == "__main__":
    unittest.main()
