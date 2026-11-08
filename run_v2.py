"""Grid runner for the isolated v2 experiment."""
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


from episode_v2 import EpisodeSpec, run_episode  # noqa: E402
from llm import (APIError, Budget, MockClient, OpenRouterClient,
                 choose_cheapest_endpoint, fetch_endpoints)  # noqa: E402
from records import RunRecords  # noqa: E402

DEFAULT_MODELS = ["openai/gpt-6.1-sol", "anthropic/claude-opus-5.5"]


def _arg(parser, argv):
    return parser.parse_args(argv)


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser()
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--mock", action="store_true")
    p.add_argument("--models", default=",".join(DEFAULT_MODELS))
    p.add_argument("--provider", action="append", default=[], metavar="MODEL=PROVIDER_SLUG")
    p.add_argument("--ns", default="4")
    p.add_argument("--board-reps", type=int, default=10)
    p.add_argument("--noboard-reps", type=int, default=3)
    p.add_argument("--rep-start", type=int, default=0)
    p.add_argument("--no-end-vote", action="store_true")
    p.add_argument("--max-tokens", type=int, default=16384)
    p.add_argument("--max-usd-episode", type=float, default=10.0)
    p.add_argument("--max-usd-total", type=float, default=150.0)
    p.add_argument("--max-calls", type=int, default=50000)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--pilot", action="store_true")
    args = _arg(p, sys.argv[1:] if argv is None else argv)
    if args.live:
        load_dotenv(HERE / ".env")
    models = [x.strip() for x in args.models.split(",") if x.strip()]
    overrides = {}
    for item in args.provider:
        model, sep, slug = item.partition("=")
        if not sep or not model.strip() or not slug.strip() or model.strip() in overrides:
            p.error("--provider must be a unique MODEL=PROVIDER_SLUG")
        overrides[model.strip()] = slug.strip()
    if set(overrides) - set(models):
        p.error("--provider models must be included in --models")
    ns = [int(x) for x in args.ns.split(",")]
    if not models or any(n < 2 for n in ns):
        p.error("--models must be nonempty and every --ns value must be at least 2")
    if args.max_tokens < 1 or args.workers < 1 or min(args.board_reps, args.noboard_reps, args.rep_start) < 0 or args.board_reps + args.noboard_reps == 0:
        p.error("token, repetition, and worker counts must be positive")
    if args.pilot:
        args.board_reps = args.noboard_reps = 1
    plans = [(m, n, rep, board) for m in models for n in ns
             for board, count in ((True, args.board_reps), (False, args.noboard_reps))
             for rep in range(args.rep_start, args.rep_start + count)]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S") + ("-pilot" if args.pilot else "") + ("-mock" if args.mock else "") + ("-novote" if args.no_end_vote else "")
    out = HERE / "results-v2" / stamp
    out.mkdir(parents=True, exist_ok=False)
    routes = {}
    if args.mock:
        client = MockClient()
        prices = {m: (0.0, 0.0) for m in models}
        ledger = None
    else:
        clients = {}
        prices = {}
        for model in models:
            endpoints = fetch_endpoints(model)
            if model in overrides:
                slug = overrides[model]
                endpoints = [e for e in endpoints if e.get("tag", "").split("/")[0] == slug]
                if not endpoints:
                    raise APIError(f"provider {slug!r} not found for model {model!r}")
            try:
                choice = choose_cheapest_endpoint(endpoints, required_params=["tools", "reasoning"],
                                                  need_temperature=False)
            except APIError as exc:
                raise APIError(f"no eligible endpoint for {model!r} provider {overrides.get(model, '(automatic)')!r}: requires live status, max_tokens, tools, and reasoning") from exc
            routes[model] = choice
            clients[model] = OpenRouterClient(provider_order=[choice["provider_slug"]],
                                              reasoning={"enabled": True})
            prices[model] = choice["price_usd_per_token"]
        class RoutedChat:
            def chat(self, *, model, **kwargs):
                return clients[model].chat(model=model, **kwargs)
        client = RoutedChat()
        ledger = HERE / "results" / "spend_ledger.json"
    budget = Budget(args.max_calls, args.max_usd_total, args.max_usd_episode, prices, ledger)
    prompt_files = [HERE / ("prompts-v2-novote" if args.no_end_vote else "prompts-v2") / name for name in ("system_board.md", "system_noboard.md")]
    hashes = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in prompt_files if f.exists()}
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=HERE,
                            capture_output=True, text=True).stdout.strip() or None
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=HERE,
                                capture_output=True, text=True).stdout.strip())
    config = {"models": models, "ns": ns, "board_reps": args.board_reps,
              "noboard_reps": args.noboard_reps, "rep_start": args.rep_start, "no_end_vote": args.no_end_vote, "max_tokens": args.max_tokens,
              "max_usd_episode": args.max_usd_episode, "max_usd_total": args.max_usd_total,
              "max_calls": args.max_calls, "workers": args.workers, "pilot": args.pilot,
              "mock": args.mock, "provider_overrides": overrides, "routes": routes, "prompt_sha256": hashes,
              "git_commit": commit, "git_dirty": dirty, "argv": sys.argv if argv is None else argv}
    (out / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    records = RunRecords(out / "records.jsonl")
    records.append("run_started", planned_episodes=len(plans))
    episodes_dir = out / "episodes"
    episodes_dir.mkdir()
    specs = []
    for model, n, rep, board in plans:
        spec = EpisodeSpec(model=model, board=board, n=n, rep=rep,
                           seed=20261108 + 1000 * n + rep, max_tokens=args.max_tokens, no_end_vote=args.no_end_vote)
        folder = model.replace("/", "_") + f"__{spec.condition}__n{n}__r{rep}"
        specs.append((spec, episodes_dir / folder, prompt_files[0 if board else 1]))
    summaries = []
    def job(item):
        spec, folder, prompt_path = item
        records.append("episode_started", model=spec.model, condition=spec.condition, n=spec.n, rep=spec.rep)
        from string import Template
        system = Template(prompt_path.read_text(encoding="utf-8")).substitute(
            n=spec.n, start=1, max_rounds=2 * spec.n)
        return run_episode(spec, client, budget, folder, system)
    stopped = None
    recorded = set()
    pool = ThreadPoolExecutor(max_workers=args.workers)
    future_map = {pool.submit(job, item): item for item in specs}
    def record_future(fut):
        spec = future_map[fut][0]
        fields = dict(model=spec.model, condition=spec.condition, n=spec.n, rep=spec.rep,
                      dir=future_map[fut][1].name)
        if fut.cancelled():
            records.append("episode_not_started", **fields)
            return
        try:
            summary = fut.result()
            summaries.append(summary)
            records.append("episode_finished", **fields, summary=summary)
        except Exception as exc:
            records.append("episode_crashed", **fields, error=f"{type(exc).__name__}: {exc}")
    try:
        for fut in as_completed(future_map):
            record_future(fut)
            recorded.add(fut)
    except KeyboardInterrupt:
        stopped = "KeyboardInterrupt"
        budget.halt("run stopped; no new calls")
        for fut in future_map:
            fut.cancel()
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
    for fut in future_map:
        if fut not in recorded:
            record_future(fut)
    summaries.sort(key=lambda x: (x["model"], x["n"], x["rep"], x["condition"]))
    (out / "metrics.json").write_text(json.dumps({"episodes": summaries,
        "run": {"complete": stopped is None and len(summaries) == len(plans), "stopped": stopped},
        "budget": {"calls": budget.calls, "ledger_usd_total": budget.charged_usd,
                   "halted": budget.halted}}, indent=2), encoding="utf-8")
    records.append("run_finished", complete=stopped is None and len(summaries) == len(plans),
                   calls=budget.calls, episodes_finished=len(summaries), stopped=stopped)
    records.close()
    print(out)


if __name__ == "__main__":
    main()
