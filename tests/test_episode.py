"""Prompt rendering, model layer (OpenRouter client, budget caps, mock), episode loop, aggregation."""

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

from engine import Action, Game, Rules, parse_action  # noqa: E402
from episode import EpisodeSpec, run_episode  # noqa: E402
from llm import (APIError, Budget, BudgetExceeded, Completion, MockClient, OpenRouterClient,  # noqa: E402
                 TOKEN_OVERHEAD, choose_cheapest_endpoint)
from metrics import aggregate  # noqa: E402
from render import system_prompt, turn_prompt  # noqa: E402


def spec(**kw):
    base = dict(model="test/model", board=True, n=4, rep=0, seed=7, turns_per_agent=4,
                starting_points=1, post_max_chars=280, temperature=1.0, max_tokens=256)
    base.update(kw)
    return EpisodeSpec(**base)


class FixedClient:
    """Always returns the same reply text."""

    def __init__(self, text, cost=0.0):
        self.text, self.cost, self.prompts = text, cost, []

    def complete(self, *, model, system, user, meta, temperature, max_tokens):
        self.prompts.append(user)
        return Completion(text=self.text, cost_usd=self.cost)


class RenderTests(unittest.TestCase):
    def test_system_prompt_is_identical_for_every_agent_and_states_the_limits(self):
        rules = Rules(n=4, board=True, max_turns=32, post_max_chars=280)
        text = system_prompt(rules)
        self.assertIn("one of 4 agents", text)
        self.assertIn("after 32 turns", text)
        self.assertIn("280 characters", text)
        self.assertNotIn("$", text)
        self.assertNotIn("agent_1", text)  # ids come in the turn prompt, not the system prompt

    def test_board_and_noboard_differ_in_allowed_actions(self):
        board = system_prompt(Rules(n=2, board=True))
        noboard = system_prompt(Rules(n=2, board=False))
        self.assertIn('"action": "post"', board)
        self.assertNotIn('"action": "post"', noboard)
        self.assertIn("There is no message board", noboard)

    def test_multiplier_variant_prompt_explains_choice_probability_and_payout(self):
        rules = Rules(n=2, board=False, multiplier_min=2, multiplier_max=10)
        system = system_prompt(rules)
        self.assertIn("2 <= x <= 10", system)
        self.assertIn("probability 1/x", system)
        self.assertIn("x*s points back", system)
        g = Game.new(rules, random.Random(0))
        g.begin_turn()
        turn = turn_prompt(g, "agent_1")
        self.assertIn('include both "stake" and integer "x" from 2 to 10', turn)
        self.assertIn('{"action": "play", "stake": 1, "x": 2}', turn)

    def test_chosen_multiplier_appears_in_public_record(self):
        rules = Rules(n=2, board=False, multiplier_min=2, multiplier_max=10)
        g = Game.new(rules, random.Random(0))
        g.balances["agent_1"] = 3
        g.begin_turn()
        g.apply("agent_1", parse_action('{"action":"play","stake":2,"x":4}'))
        g.begin_turn()
        self.assertIn("stake of 2 at x=4", turn_prompt(g, "agent_2"))

    def test_turn_prompt_shows_own_state_public_record_and_rejection(self):
        rules = Rules(n=2, board=False, max_turns=8)
        g = Game.new(rules, random.Random(0))
        g.begin_turn()
        g.apply("agent_2", Action("vote_end"))
        g.begin_turn()
        g.apply("agent_1", Action("play", amount=1))  # wins or loses; the public line says which
        g.record_invalid("agent_2", "no JSON object found in your reply")
        g.begin_turn()
        text = turn_prompt(g, "agent_2", last_error="no JSON object found in your reply")
        self.assertIn("Turn 3 of 8. You are agent_2.", text)
        self.assertIn("Your points: 1.", text)
        self.assertIn("You have not played your game yet.", text)
        self.assertIn("Your end vote is active.", text)
        self.assertIn("agent_2 (you): 1 point(s); played: no; end vote: active", text)
        self.assertIn("turn 1: agent_2 voted to end", text)
        self.assertIn("turn 2: agent_1 played a stake of 1: ", text)
        self.assertIn("Your previous reply was rejected (no JSON object found in your reply)", text)
        self.assertNotIn("Message board", text)  # no board in this condition

    def test_board_prompt_lists_posts_and_hides_invalid_replies_from_others(self):
        g = Game.new(Rules(n=2, board=True), random.Random(0))
        g.begin_turn()
        g.apply("agent_1", Action("post", text="let's pool"))
        g.record_invalid("agent_1", "secret garbage")
        text = turn_prompt(g, "agent_2")
        self.assertIn("[turn 1] agent_1: let's pool", text)
        self.assertNotIn("secret garbage", text)
        self.assertNotIn("rejected", text)  # agent_2 was not rejected


class OpenRouterClientTests(unittest.TestCase):
    OK = {"choices": [{"message": {"content": '{"action":"skip"}'}, "finish_reason": "stop"}],
          "usage": {"prompt_tokens": 10, "completion_tokens": 3, "cost": 0.00012}}

    def _response(self, payload):
        resp = mock.MagicMock()
        resp.read.return_value = json.dumps(payload).encode()
        resp.__enter__.return_value = resp
        return resp

    def test_parses_text_tokens_and_reported_cost(self):
        client = OpenRouterClient(api_key="k")
        with mock.patch("llm.urllib.request.urlopen", return_value=self._response(self.OK)) as up:
            c = client.complete(model="m", system="s", user="u", meta={}, temperature=1.0, max_tokens=9)
        self.assertEqual(c.text, '{"action":"skip"}')
        self.assertEqual((c.prompt_tokens, c.completion_tokens, c.cost_usd), (10, 3, 0.00012))
        req = up.call_args.args[0]
        body = json.loads(req.data)
        self.assertEqual(body["model"], "m")
        self.assertEqual(body["usage"], {"include": True})
        self.assertEqual(req.get_header("Authorization"), "Bearer k")

    def test_rate_limit_is_not_retried_and_raises(self):
        err = urllib.error.HTTPError("u", 429, "rate", {}, io.BytesIO(b"slow down"))
        client = OpenRouterClient(api_key="k")
        with mock.patch("llm.urllib.request.urlopen", side_effect=[err, self._response(self.OK)]) as up:
            with self.assertRaisesRegex(APIError, "HTTP 429"):
                client.complete(model="m", system="s", user="u", meta={}, temperature=1.0, max_tokens=9)
        self.assertEqual(up.call_count, 1)

    def test_pins_provider_order_with_no_fallback(self):
        client = OpenRouterClient(api_key="k", provider_order=["relace"])
        with mock.patch("llm.urllib.request.urlopen", return_value=self._response(self.OK)) as up:
            client.complete(model="m", system="s", user="u", meta={}, temperature=1.0, max_tokens=9)
        body = json.loads(up.call_args.args[0].data)
        self.assertEqual(body["provider"], {"order": ["relace"], "allow_fallbacks": False})

    def test_network_error_is_not_retried(self):
        client = OpenRouterClient(api_key="k")
        with mock.patch("llm.urllib.request.urlopen", side_effect=TimeoutError("slow")) as up:
            with self.assertRaisesRegex(APIError, "network"):
                client.complete(model="m", system="s", user="u", meta={}, temperature=1.0, max_tokens=9)
        self.assertEqual(up.call_count, 1)

    def test_non_retryable_error_raises_api_error_without_retry(self):
        err = urllib.error.HTTPError("u", 400, "bad", {}, io.BytesIO(b"bad model"))
        client = OpenRouterClient(api_key="k")
        with mock.patch("llm.urllib.request.urlopen", side_effect=err) as up:
            with self.assertRaisesRegex(APIError, "HTTP 400"):
                client.complete(model="m", system="s", user="u", meta={}, temperature=1.0, max_tokens=9)
        self.assertEqual(up.call_count, 1)

    def test_missing_key_is_refused_up_front(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(APIError, "OPENROUTER_API_KEY"):
                OpenRouterClient(api_key="")


def make_budget(calls=100, total=10.0, episode=10.0, out_price=1e-6, ledger=None):
    return Budget(calls, total, episode, {"test/model": (1e-6, out_price)}, ledger)


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pg-budget-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def call(self, b, client, meter, max_tokens=1024, user="u"):
        return b.call(client, model="test/model", system="s", user=user, meta={},
                      temperature=1, max_tokens=max_tokens, meter=meter)

    def test_call_cap_stops_before_the_call(self):
        client = FixedClient('{"action":"skip"}')
        b = make_budget(calls=2)
        m = b.meter()
        self.call(b, client, m)
        self.call(b, client, m)
        with self.assertRaisesRegex(Exception, "call cap"):
            self.call(b, client, m)
        self.assertEqual(len(client.prompts), 2)

    def test_episode_cap_refuses_before_any_call_when_worst_case_would_exceed_it(self):
        client = FixedClient('{"action":"skip"}', cost=0.0)
        b = make_budget(episode=0.10, out_price=1e-4)  # 1024 tokens * $1e-4 = $0.1024 worst case
        with self.assertRaisesRegex(Exception, "episode dollar cap"):
            self.call(b, client, b.meter())
        self.assertEqual(client.prompts, [])  # refused before the request was made

    def test_reported_cost_is_charged_and_counted_per_episode(self):
        client = FixedClient('{"action":"skip"}', cost=0.02)
        b = make_budget()
        m1 = b.meter()
        self.call(b, client, m1)
        self.call(b, client, m1)
        self.assertAlmostEqual(m1.usd, 0.04)
        m2 = b.meter()
        self.assertEqual(m2.usd, 0.0)
        self.assertAlmostEqual(b.charged_usd, 0.04)

    def test_missing_cost_is_charged_at_worst_case_and_flagged(self):
        client = FixedClient('{"action":"skip"}', cost=None)
        b = make_budget()
        m = b.meter()
        self.call(b, client, m)
        self.assertEqual(b.unknown_cost_calls, 1)
        self.assertAlmostEqual(m.usd, b.worst_case_usd("test/model", "s", "u", 1024))

    def test_input_estimate_uses_utf8_bytes_plus_overhead_not_chars(self):
        b = make_budget(out_price=0.0)
        text = "\u00e9" * 1000  # 1000 characters, 2000 UTF-8 bytes
        expected = (len(("s" + text).encode("utf-8")) + TOKEN_OVERHEAD) * 1e-6
        self.assertAlmostEqual(b.worst_case_usd("test/model", "s", text, 0), expected)
        self.assertGreater(b.worst_case_usd("test/model", "s", text, 0), (1001 / 2) * 1e-6)

    def test_ambiguous_error_keeps_worst_case_charged_and_is_not_retried(self):
        class Boom:
            calls = 0

            def complete(self, **kw):
                Boom.calls += 1
                raise APIError("HTTP 500: unknown outcome")

        ledger = self.tmp / "ledger.json"
        b = make_budget(ledger=ledger)
        m = b.meter()
        worst = b.worst_case_usd("test/model", "s", "u", 1024)
        with self.assertRaisesRegex(APIError, "HTTP 500"):
            self.call(b, Boom(), m)
        self.assertEqual(Boom.calls, 1)  # no retry
        self.assertAlmostEqual(b.charged_usd, worst)  # the call stays charged
        self.assertAlmostEqual(m.usd, worst)
        self.assertEqual(b.failed_calls, 1)
        self.assertAlmostEqual(json.loads(ledger.read_text())["charged_usd"], worst, places=7)

    def test_total_ledger_persists_across_invocations_and_blocks_overspend(self):
        ledger = self.tmp / "ledger.json"
        client = FixedClient('{"action":"skip"}', cost=0.5)
        first = make_budget(total=0.6, ledger=ledger)
        self.call(first, client, first.meter())
        self.assertEqual(json.loads(ledger.read_text())["charged_usd"], 0.5)
        second = make_budget(total=0.6, out_price=1e-4, ledger=ledger)  # a new invocation, e.g. the next pilot
        self.assertAlmostEqual(second.charged_usd, 0.5)
        with self.assertRaisesRegex(Exception, "total dollar cap"):
            self.call(second, FixedClient('{"action":"skip"}'), second.meter())  # 0.5 + 0.1024 > 0.6
        self.assertEqual(second.calls, 0)

    def test_concurrent_calls_never_exceed_total_cap(self):
        import threading
        import time
        lock = threading.Lock()
        state = {"inflight": 0, "max_inflight": 0}

        class Slow:
            def complete(self, *, model, system, user, meta, temperature, max_tokens):
                with lock:
                    state["inflight"] += 1
                    state["max_inflight"] = max(state["max_inflight"], state["inflight"])
                time.sleep(0.05)
                with lock:
                    state["inflight"] -= 1
                return Completion(text='{"action":"skip"}', cost_usd=0.0)

        worst = make_budget().worst_case_usd("test/model", "s", "u", 1024)
        b = make_budget(calls=100, total=3.5 * worst, episode=100.0)  # room for 3 reservations at once
        results = []
        threads = []

        def worker():
            try:
                self.call(b, Slow(), b.meter())
                results.append("ok")
            except BudgetExceeded:
                results.append("refused")

        for _ in range(8):
            threads.append(threading.Thread(target=worker))
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertLessEqual(state["max_inflight"], 3)
        self.assertEqual(len(results), 8)
        self.assertLessEqual(b.charged_usd, 3.5 * worst + 1e-12)

    def test_unpriced_model_is_refused_before_any_call(self):
        client = FixedClient('{"action":"skip"}')
        b = Budget(100, 10.0, 10.0, {})
        with self.assertRaisesRegex(Exception, "no price"):
            self.call(b, client, b.meter())
        self.assertEqual(client.prompts, [])

    def test_choose_cheapest_live_endpoint_by_blended_cost(self):
        eps = [
            {"provider_name": "Dead", "tag": "dead/fp8", "status": -5, "pricing": {"prompt": "0", "completion": "0"},
             "supported_parameters": ["max_tokens", "temperature"]},
            {"provider_name": "NoMax", "tag": "nomax/x", "status": 0, "pricing": {"prompt": "0", "completion": "0"},
             "supported_parameters": ["temperature"]},
            {"provider_name": "Pricey", "tag": "pricey/fp8", "status": 0,
             "pricing": {"prompt": "0.000001", "completion": "0.000002"},
             "supported_parameters": ["max_tokens", "temperature"]},
            {"provider_name": "Relace", "tag": "relace/fp4", "status": 0,
             "pricing": {"prompt": "0.000000006", "completion": "0.0000005"},
             "supported_parameters": ["max_tokens", "temperature"]},
        ]
        choice = choose_cheapest_endpoint(eps)
        self.assertEqual(choice["provider_slug"], "relace")
        self.assertEqual(choice["provider_name"], "Relace")

    def test_one_worst_case_call_fits_the_per_episode_cap(self):
        import run  # the configured prices and caps
        prices = {m: (p_in / 1e6, p_out / 1e6) for m, (p_in, p_out) in run.CONFIG["prices_usd_per_mtok"].items()}
        self.assertLessEqual(run.CONFIG["max_usd_episode"], 0.10)
        for model, (p_in, p_out) in prices.items():
            b = Budget(10_000, 5.0, 0.10, {model: (p_in, p_out)})
            big_prompt = "x" * 12_000  # about 3x the largest N=8 turn prompt
            per_call = b.worst_case_usd(model, "", big_prompt, run.CONFIG["max_tokens"])
            self.assertLess(per_call, 0.10, model)

    def test_n8_episode_never_exceeds_the_episode_cap_even_when_every_reply_is_maximal(self):
        # The reservation is settled after each call, so the cap binds on ACTUAL spend, not on 64 worst cases.
        # A maximal-cost reply on every call must therefore be cut off (aborted_budget) before $0.10 is passed.
        import run
        model = "deepseek/deepseek-v4.1-flash-1017"
        p_in, p_out = (x / 1e6 for x in run.CONFIG["prices_usd_per_mtok"][model])
        max_tokens = run.CONFIG["max_tokens"]
        max_cost = 2000 * p_in + max_tokens * p_out  # ~2k input tokens, full output

        class MaxCostClient:
            def complete(self, *, model, system, user, meta, temperature, max_tokens):
                return Completion(text="{}", prompt_tokens=2000, completion_tokens=max_tokens, cost_usd=max_cost)

        budget = Budget(10_000, 5.0, 0.10, {model: (p_in, p_out)})
        summary = run_episode(spec(model=model, n=8, turns_per_agent=8, max_tokens=max_tokens),
                              MaxCostClient(), budget, self.tmp / "n8max")
        self.assertLessEqual(summary["cost_usd"], 0.10 + 1e-12)
        self.assertEqual(summary["status"], "aborted_budget")


class EpisodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pg-test-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_ep(self, client, name="ep", budget=None, **kw):
        return run_episode(spec(**kw), client, budget or make_budget(), self.tmp / name)

    def test_all_vote_end_completes_in_exactly_n_turns(self):
        s = self.run_ep(FixedClient('{"action":"vote_end"}'), n=4)
        self.assertEqual(s["status"], "completed")
        self.assertEqual(s["turns"], 4)
        self.assertEqual(s["total_final"], 4)

    def test_never_ending_group_is_truncated_not_completed(self):
        s = self.run_ep(FixedClient('{"action":"skip"}'), n=3, turns_per_agent=4)
        self.assertEqual(s["status"], "truncated")
        self.assertEqual(s["turns"], 12)
        self.assertEqual(s["plays"], 0)

    def test_round_robin_gives_each_agent_the_same_number_of_turns(self):
        self.run_ep(FixedClient('{"action":"skip"}'), n=4, turns_per_agent=3, name="rr")
        rows = [json.loads(line) for line in (self.tmp / "rr" / "transcript.jsonl").read_text().splitlines()]
        actors = [r["actor"] for r in rows]
        self.assertEqual({a: actors.count(a) for a in set(actors)}, {a: 3 for a in set(actors)})
        self.assertEqual(len(actors), 12)

    def test_invalid_replies_consume_turns_and_are_fed_back(self):
        s = self.run_ep(FixedClient("I think I'll wait."), n=2, turns_per_agent=2, name="bad")
        self.assertEqual(s["status"], "truncated")
        self.assertEqual(s["invalid"], 4)
        rows = [json.loads(line) for line in (self.tmp / "bad" / "transcript.jsonl").read_text().splitlines()]
        self.assertIn("rejected", rows[2]["prompt"])  # the agent's second turn carries the reason

    def test_budget_cap_marks_episode_aborted_and_keeps_partial_log(self):
        s = self.run_ep(FixedClient('{"action":"skip"}'), n=2, turns_per_agent=4,
                        budget=make_budget(calls=3), name="cap")
        self.assertEqual(s["status"], "aborted_budget")
        self.assertEqual(s["calls"], 3)
        lines = (self.tmp / "cap" / "transcript.jsonl").read_text().splitlines()
        self.assertEqual(len(lines), 3)

    def test_api_error_marks_episode_error(self):
        class Broken:
            def complete(self, **kw):
                raise APIError("HTTP 500: down")

        s = self.run_ep(Broken(), n=2, name="err")
        self.assertEqual(s["status"], "error")
        self.assertIn("down", s["error"])

    def test_same_seed_gives_identical_event_log_and_summary(self):
        a = self.run_ep(MockClient(), name="a", n=4, seed=99)
        b = self.run_ep(MockClient(), name="b", n=4, seed=99)
        ja = json.loads((self.tmp / "a" / "episode.json").read_text())
        jb = json.loads((self.tmp / "b" / "episode.json").read_text())
        self.assertEqual(ja["events"], jb["events"])
        self.assertEqual(ja["turn_order"], jb["turn_order"])
        self.assertEqual(a, b)

    def test_different_seed_changes_order_or_outcomes(self):
        self.run_ep(MockClient(), name="a", n=4, seed=1)
        self.run_ep(MockClient(), name="b", n=4, seed=2)
        ja = json.loads((self.tmp / "a" / "episode.json").read_text())
        jb = json.loads((self.tmp / "b" / "episode.json").read_text())
        self.assertNotEqual((ja["turn_order"], ja["events"]), (jb["turn_order"], jb["events"]))

    def test_mock_policy_always_valid_and_points_conserved_across_grid(self):
        for n in (2, 4, 8):
            for board in (True, False):
                for seed in range(5):
                    s = self.run_ep(MockClient(), name=f"m{n}{board}{seed}", n=n, board=board, seed=seed,
                                    turns_per_agent=6)
                    self.assertEqual(s["invalid"], 0, (n, board, seed))
                    self.assertEqual(s["total_final"], n + s["net_game_points"])
                    self.assertTrue(s["conservation_ok"])
                    if not board:
                        self.assertEqual(s["posts"], 0)

    def test_episode_json_has_full_event_log_and_summary(self):
        s = self.run_ep(MockClient(), name="full", n=2, turns_per_agent=6, seed=3)
        doc = json.loads((self.tmp / "full" / "episode.json").read_text())
        self.assertEqual(doc["summary"], s)
        self.assertEqual(len(doc["events"]), s["turns"])
        self.assertEqual(doc["spec"]["model"], "test/model")


class MetricsTests(unittest.TestCase):
    def ep(self, status, total, cond="board", n=2):
        return {"model": "m", "condition": cond, "n": n, "status": status, "total_final": total,
                "mean_final": total / n, "total_gain": total - n, "plays": 1, "max_stake": 1,
                "transfers": 0, "posts": 0, "invalid": 0, "turns": 4}

    def test_truncated_and_failed_runs_do_not_enter_means(self):
        rows = aggregate([self.ep("completed", 4), self.ep("completed", 2), self.ep("truncated", 0),
                          self.ep("error", 1)])
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual((r["runs"], r["completed"], r["truncated"], r["failed"]), (4, 2, 1, 1))
        self.assertEqual(r["mean_total_final"], 3)
        self.assertEqual(r["ruined_runs"], 0)

    def test_groups_split_by_model_condition_and_n(self):
        rows = aggregate([self.ep("completed", 4, "board"), self.ep("completed", 4, "noboard"),
                          self.ep("completed", 8, "board", n=4)])
        self.assertEqual({(r["condition"], r["n"]) for r in rows}, {("board", 2), ("noboard", 2), ("board", 4)})


if __name__ == "__main__":
    unittest.main()
