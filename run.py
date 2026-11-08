"""Pooled-gamble experiment. One command reruns the whole grid:

    uv run experiments/pooled-gamble/run.py --mock --pilot   # offline wiring check, no model calls
    uv run experiments/pooled-gamble/run.py --pilot --live   # tiny LIVE pilot (real OpenRouter calls)
    uv run experiments/pooled-gamble/run.py --live           # full LIVE grid (real calls, capped)
    add --out <dir> to write results outside the repo (for example, a scratch folder)

Live runs refuse to start without --live, because they spend money. .env in this workspace
holds a real OPENROUTER_API_KEY, so a run without --mock is live.

Grid: model x condition (board / noboard) x N (2, 4, 8) x rep (3). Each cell is an episode of
N agents running the same model. Board and no-board episodes with the same (N, rep) share a
seed, so they are paired on turn order and game draws. Episodes run concurrently (CONFIG["workers"]),
which is safe because every call reserves its worst-case cost under one shared lock.

Live routing: for each model, the cheapest live endpoint is chosen from OpenRouter's endpoints API
at run start and pinned (provider order, no fallbacks). Budgeting uses that endpoint's prices.

Each invocation writes results/<timestamp>/ with config.json, records.jsonl (append-only event log:
episode started/finished/crashed/not-started, written as it happens), metrics.json (written even when
a run is stopped), and one folder per episode (episode.json, transcript.jsonl). Existing result folders
are never overwritten. Use --max-tokens N (256..65536) to change the per-call output cap for a run.
Use records.py / summarize.py / plots.py to read runs; incomplete runs are reported, not dropped.
Caps (all enforced BEFORE each call, with a reservation): CONFIG["max_calls"], "max_usd_episode"
($0.10 per episode), and "max_usd_total" ($5 across all invocations). The total ledger is always
results/spend_ledger.json, whatever --out is, so scratch folders cannot reset the cap.
Tests: python -m unittest discover -s experiments/pooled-gamble/tests
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
load_dotenv(HERE.parent.parent / ".env")

from episode import EpisodeSpec, run_episode  # noqa: E402
from llm import (APIError, Budget, MockClient, OpenRouterClient,  # noqa: E402
                 choose_cheapest_endpoint, fetch_endpoints)
from metrics import aggregate  # noqa: E402
from records import RECORDS_FILE, RunRecords  # noqa: E402
from render import prompt_dir  # noqa: E402

LEDGER_PATH = HERE / "results" / "spend_ledger.json"  # fixed: shared by every invocation and --out

CONFIG = {
    "seed_base": 20261107,
    "models": [  # pinned, dated slugs (not "-latest" aliases)
        "deepseek/deepseek-v4.1-flash-1017",
        "z-ai/glm-5.3-flash",
    ],
    "ns": [2, 4, 8],
    "reps": 3,
    "turns_per_agent": 8,  # action limit = turns_per_agent * N total turns
    "starting_points": 1,
    "post_max_chars": 280,
    "temperature": 1.0,
    # Output bound per call; part of the worst-case reservation. Reasoning tokens count against it, so
    # it must leave room for thinking plus the visible reply. Override per invocation with --max-tokens.
    # History: 2048 (no reasoning), 1024 (earliest design), 8192 (reasoning on), now 16384.
    "max_tokens": 16384,
    "max_calls": 1500,  # hard cap on model calls, all invocations
    "max_usd_total": 5.00,  # hard cap on spend across ALL invocations (ledger), pilots included
    "max_usd_episode": 0.10,  # hard cap per episode, enforced before every call
    # Per-model reasoning control, sent on every call. Reasoning is ON for both models in this grid.
    # Older runs (results folders created before this change) used reasoning off for DeepSeek and
    # no reasoning field for GLM, whose Relace endpoint then rejected every call (HTTP 400).
    "reasoning": {"deepseek/deepseek-v4.1-flash-1017": {"enabled": True}, "z-ai/glm-5.3-flash": {"enabled": True}},
    "workers": 12,  # concurrent episodes; the shared budget lock keeps the caps exact
    # Snapshot of the pinned Relace endpoints, 2026-11-07, used ONLY by a unit test. Live runs
    # price every call from the live endpoint chosen at run start.
    "prices_usd_per_mtok": {
        "deepseek/deepseek-v4.1-flash-1017": (0.006, 0.50),
        "z-ai/glm-5.3-flash": (0.034, 0.083),
    },
}
PILOT_OVERRIDES = {
    "models": CONFIG["models"][:1],
    "ns": [2],
    "reps": 1,
    "turns_per_agent": 4,
    # No per-pilot "max_calls": the call count is cumulative across invocations (ledger), so a
    # pilot-only value of 40 was already exhausted by earlier runs and blocked every call.
    # Pilots stay small through ns/reps/turns; the dollar caps and the global max_calls still apply.
}


def episode_seed(base: int, n: int, rep: int) -> int:
    return base + 1000 * n + rep


def grid(config: dict):
    for model in config["models"]:
        for n in config["ns"]:
            for rep in range(config["reps"]):
                for board in (True, False):
                    yield model, n, rep, board


def prompt_hashes(prompt_set: str = "prompts") -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(prompt_dir(prompt_set).glob("*.md"))}


class PinnedRouter:
    """Routes each model to its own client, which is pinned to that model's cheapest live provider."""

    def __init__(self, clients: dict[str, OpenRouterClient]) -> None:
        self.clients = clients

    def complete(self, *, model: str, **kw):
        return self.clients[model].complete(model=model, **kw)


def pin_live_routes(models: list[str], reasoning_by_model: dict, need_temperature: bool = True) -> tuple[PinnedRouter, dict[str, dict]]:
    """Choose and pin the cheapest live endpoint per model. Fails closed if any lookup fails."""
    clients, routes = {}, {}
    for model in models:
        # A requested reasoning setting must be supported by the endpoint we pin, not just the model.
        required = ["reasoning"] if reasoning_by_model.get(model) is not None else []
        choice = choose_cheapest_endpoint(fetch_endpoints(model), required_params=required,
                                         need_temperature=need_temperature)
        routes[model] = choice
        clients[model] = OpenRouterClient(provider_order=[choice["provider_slug"]],
                                          reasoning=reasoning_by_model.get(model))
    return PinnedRouter(clients), routes


def _flag(name: str, default=None):
    """The value after a command-line flag, or default when the flag is absent."""
    if name not in sys.argv:
        return default
    i = sys.argv.index(name)
    if i + 1 >= len(sys.argv):
        sys.exit(f"error: {name} needs a value")
    return sys.argv[i + 1]


def episode_fields(spec: EpisodeSpec) -> dict:
    return {"model": spec.model, "condition": spec.condition, "n": spec.n, "rep": spec.rep}


def main() -> None:
    pilot = "--pilot" in sys.argv
    mock = "--mock" in sys.argv
    if not mock and "--live" not in sys.argv:
        sys.exit("refusing to run: this would make paid OpenRouter calls. Add --live, or use --mock.")
    out_root = Path(_flag("--out")) if "--out" in sys.argv else HERE / "results"
    config = {**CONFIG, **(PILOT_OVERRIDES if pilot else {})}
    if "--model" in sys.argv:  # run only one configured model (its results are merged later by report)
        only = _flag("--model")
        if only not in CONFIG["models"]:
            sys.exit(f"error: --model {only!r} is not a configured model")
        config["models"] = [only]
    if "--add-model" in sys.argv:  # run one model that is not in CONFIG (reasoning on), e.g. a new-model check
        slug = _flag("--add-model")
        config["models"] = [slug]
        config["temperature"] = None  # newer OpenAI models reject temperature; the provider default is used
        config["reasoning"] = {**config["reasoning"], slug: {"enabled": True}}
    if "--ns" in sys.argv:  # comma-separated group sizes, e.g. 4 or 2,4
        config["ns"] = [int(x) for x in _flag("--ns").split(",")]
    if "--reps" in sys.argv:
        config["reps"] = int(_flag("--reps"))
    if "--max-tokens" in sys.argv:  # output cap per call; part of the worst-case reservation
        raw = _flag("--max-tokens")
        if not raw.isdigit() or not 256 <= int(raw) <= 65536:
            sys.exit("error: --max-tokens must be an integer from 256 to 65536")
        config["max_tokens"] = int(raw)
    prompt_set = _flag("--prompts", "prompts")  # "prompts" = original; "prompts-<variant>" = a variant set
    try:
        prompt_dir(prompt_set)
    except ValueError as e:
        sys.exit(f"error: {e}")
    if not all((prompt_dir(prompt_set) / f).exists() for f in ("system_board.md", "system_noboard.md", "turn.md")):
        sys.exit(f"error: prompt set {prompt_set!r} is missing a template file")
    config["prompt_set"] = prompt_set
    if "--max-usd-episode" in sys.argv:  # per-episode dollar cap; recorded in config.json
        try:
            cap = float(_flag("--max-usd-episode"))
        except ValueError:
            cap = 0.0
        if not 0 < cap <= 1.0:
            sys.exit("error: --max-usd-episode must be a number in (0, 1.0]")
        config["max_usd_episode"] = cap
    if "--max-calls" in sys.argv:  # cumulative call cap across invocations; recorded in config.json
        raw = _flag("--max-calls")
        if not raw.isdigit() or int(raw) < 1:
            sys.exit("error: --max-calls must be a positive integer")
        config["max_calls"] = int(raw)
    # Folder name: date, then -pooled for a non-original prompt set, then -pilot / -mock.
    variant = "" if prompt_set == "prompts" else "-" + prompt_set.removeprefix("prompts-")
    stamp = (datetime.now().strftime("%Y%m%d-%H%M%S") + variant + ("-pilot" if pilot else "")
             + ("-mock" if mock else ""))
    try:  # build clients and pin routes first, so a failure leaves no empty results folder
        if mock:
            client, routes = MockClient(), None
        else:
            client, routes = pin_live_routes(config["models"], config["reasoning"], config["temperature"] is not None)
    except APIError as e:
        sys.exit(f"error: {e}")
    except Exception as e:  # network failure during endpoint lookup: refuse, spend nothing
        sys.exit(f"error: live endpoint lookup failed, nothing was run: {e}")
    out_dir = out_root / stamp
    out_dir.mkdir(parents=True)

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                            cwd=HERE).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", str(HERE)], capture_output=True,
                                text=True, cwd=HERE).stdout.strip())
    cells = sum(1 for _ in grid(config))
    meta = {
        "config": config,
        "mock": mock,
        "routes": routes,
        "prompt_set": prompt_set,
        "prompt_sha256": prompt_hashes(prompt_set),
        "planned_episodes": cells,
        "max_turns_per_episode": {n: config["turns_per_agent"] * n for n in config["ns"]},
        "git_commit": commit or None,
        "git_dirty": dirty,
        "argv": sys.argv,
        "started": stamp,
    }
    (out_dir / "config.json").write_text(json.dumps(meta, indent=2))

    if mock:  # free offline policy: zero prices, no ledger
        prices = {m: (0.0, 0.0) for m in config["models"]}
        ledger = None
    else:  # live prices come from the pinned endpoint, not the snapshot in CONFIG
        prices = {m: r["price_usd_per_token"] for m, r in routes.items()}
        ledger = LEDGER_PATH
    budget = Budget(config["max_calls"], config["max_usd_total"], config["max_usd_episode"], prices, ledger)

    jobs = []
    for model, n, rep, board in grid(config):
        cond = "board" if board else "noboard"
        spec = EpisodeSpec(
            model=model, board=board, n=n, rep=rep,
            seed=episode_seed(config["seed_base"], n, rep),
            turns_per_agent=config["turns_per_agent"],
            starting_points=config["starting_points"],
            post_max_chars=config["post_max_chars"],
            temperature=config["temperature"],
            max_tokens=config["max_tokens"],
            prompt_set=prompt_set,
        )
        slug = model.replace("/", "_")
        ep_dir = out_dir / "episodes" / f"{slug}__{cond}__n{n}__r{rep}"
        jobs.append((spec, ep_dir))

    skipped = 0
    if "--skip-done" in sys.argv:  # skip episodes already completed in an earlier run folder
        done_dir = Path(_flag("--skip-done"))
        before = len(jobs)
        jobs = [(spec, ep_dir) for spec, ep_dir in jobs
                if not (done_dir / "episodes" / ep_dir.name / "episode.json").exists()]
        skipped = before - len(jobs)
        print(f"skipping episodes completed in {done_dir}; {len(jobs)} remaining", flush=True)

    workers = 1 if mock else int(_flag("--workers", config["workers"]))
    records = RunRecords(out_dir / RECORDS_FILE)  # append-only: every outcome is written as it happens
    records.append("run_started", stamp=stamp, live=not mock, pilot=pilot, planned=cells, to_run=len(jobs),
                   skipped_done=skipped, max_tokens=config["max_tokens"], workers=workers,
                   ledger_before_usd=round(budget.charged_usd, 6))
    episodes: list[dict] = []
    crashed: list[dict] = []
    recorded: set = set()

    def job(spec: EpisodeSpec, ep_dir: Path) -> dict:
        records.append("episode_started", **episode_fields(spec), dir=ep_dir.name)
        return run_episode(spec, client, budget, ep_dir)

    def record_outcome(fut, spec: EpisodeSpec, ep_dir: Path) -> None:
        recorded.add(fut)
        try:
            summary = fut.result()
        except Exception as e:  # run_episode records its own errors; this path is a bug, so keep it visible
            crashed.append({**episode_fields(spec), "dir": ep_dir.name, "error": f"{type(e).__name__}: {e}"})
            records.append("episode_crashed", **episode_fields(spec), dir=ep_dir.name, error=crashed[-1]["error"])
            print(f"{spec.model:36s} {spec.condition:8s} n={spec.n} r={spec.rep}  CRASHED: {crashed[-1]['error']}",
                  flush=True)
            return
        episodes.append(summary)
        records.append("episode_finished", **episode_fields(spec), dir=ep_dir.name,
                       status=summary["status"], summary=summary)
        print(f"{spec.model:36s} {spec.condition:8s} n={spec.n} r={spec.rep}  {summary['status']:14s} "
              f"turns={summary['turns']:3d}  total={summary['total_final']:3d}  calls={summary['calls']}",
              flush=True)

    pool = ThreadPoolExecutor(max_workers=workers)
    futures = {pool.submit(job, spec, ep_dir): (spec, ep_dir) for spec, ep_dir in jobs}
    stopped: BaseException | None = None
    try:
        for fut in as_completed(futures):
            record_outcome(fut, *futures[fut])
    except BaseException as e:  # Ctrl-C, or a failure in this loop: make no new calls, then account for all jobs
        stopped = e
        budget.halt(f"run stopped ({type(e).__name__}); in-flight calls finish, no new calls are made")
    finally:
        pool.shutdown(wait=True, cancel_futures=True)  # running episodes end at their next call
    for fut, (spec, ep_dir) in futures.items():  # every job gets exactly one outcome line
        if fut in recorded:
            continue
        if fut.cancelled():
            records.append("episode_not_started", **episode_fields(spec), dir=ep_dir.name)
        else:
            record_outcome(fut, spec, ep_dir)

    episodes.sort(key=lambda s: (s["model"], s["n"], s["rep"], s["condition"]))
    groups = aggregate(episodes)
    run_complete = stopped is None and not crashed and len(episodes) == len(jobs)
    metrics = {
        "episodes": episodes,
        "groups": groups,
        "run": {"complete": run_complete, "stopped": repr(stopped) if stopped else None,
                "jobs": len(jobs), "skipped_done": skipped, "crashed": crashed,
                "not_started": sum(1 for f in futures if f.cancelled())},
        "budget": {"calls": budget.calls, "ledger_usd_total": round(budget.charged_usd, 6),
                   "unknown_cost_calls": budget.unknown_cost_calls, "failed_calls": budget.failed_calls,
                   "halted": budget.halted, "episodes_planned": cells, "episodes_run": len(episodes)},
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    records.append("run_finished", complete=run_complete, stopped=repr(stopped) if stopped else None,
                   calls=budget.calls, ledger_total_usd=round(budget.charged_usd, 6),
                   halted=budget.halted, episodes_finished=len(episodes), crashed=len(crashed))
    records.close()
    print(f"\nresults: {out_dir}")
    print(f"calls={budget.calls} episode-sum usd={sum(e['cost_usd'] for e in episodes):.4f} "
          f"ledger total usd={budget.charged_usd:.4f} / cap {config['max_usd_total']:.2f} "
          f"unknown_cost_calls={budget.unknown_cost_calls} failed_calls={budget.failed_calls}")
    if not run_complete:
        print(f"RUN INCOMPLETE: {len(episodes)}/{len(jobs)} episodes finished; crashed={len(crashed)}; "
              f"stopped={stopped!r}. Unfinished episodes are listed in records.jsonl and summarize.py.")
    print("\n| model | condition | n | runs | completed | truncated | failed | mean total | mean per agent | ruined | mean plays | mean transfers | mean posts | mean invalid |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for g in groups:
        f = lambda x: "-" if x is None else f"{x:.2f}"  # noqa: E731
        print(f"| {g['model']} | {g['condition']} | {g['n']} | {g['runs']} | {g['completed']} | {g['truncated']} "
              f"| {g['failed']} | {f(g['mean_total_final'])} | {f(g['mean_mean_final'])} | {g['ruined_runs']} "
              f"| {f(g['mean_plays'])} | {f(g['mean_transfers'])} | {f(g['mean_posts'])} | {f(g['mean_invalid'])} |")
    if stopped is not None:
        raise stopped


if __name__ == "__main__":
    main()
