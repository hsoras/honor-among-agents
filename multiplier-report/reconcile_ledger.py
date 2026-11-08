"""Conservative reconciliation of spend before the multiplier grid.

Why: earlier invocations each read the ledger once at start and rewrote it with their own
in-memory total, so concurrent processes overwrote each other. This script rebuilds spend from
the per-call records in every results folder, and charges unknown or unsettled calls at worst case.

Usage (from the repo root):
    .venv/bin/python -I experiments/pooled-gamble/multiplier-report/reconcile_ledger.py          # print only
    .venv/bin/python -I experiments/pooled-gamble/multiplier-report/reconcile_ledger.py --write  # set ledger
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"
LEDGER = RESULTS / "spend_ledger.json"
PRE_GUARD_CHECK_USD = 0.0031  # 6 real calls made before the --live guard existed (DESIGN.md)
IN_FLIGHT_CALLS_MARGIN = 8  # processes killed mid-call: at most one unsettled call per worker

ledger_now = json.loads(LEDGER.read_text())
spent_records = 0.0  # actual cost from transcripts
unknown_worst = 0.0  # calls with no reported cost: worst case
error_worst = 0.0  # calls that raised: never logged, worst case
inflight_worst = 0.0  # episode folders with no episode.json: a call may have been unsettled
calls = 0
unfinished = 0
for d in sorted(RESULTS.glob("2026*")):
    cfg = json.loads((d / "config.json").read_text())
    if cfg.get("mock"):
        continue
    maxtok = cfg["config"]["max_tokens"]
    routes = cfg.get("routes") or {}
    for ep in sorted((d / "episodes").glob("*")) if (d / "episodes").exists() else []:
        model = ep.name.split("__")[0].replace("_", "/", 1)
        _, price_out = routes[model]["price_usd_per_token"] if model in routes else (0.0, 0.0)
        worst_call = maxtok * price_out + 0.0  # input term is negligible at these prices
        tr = ep / "transcript.jsonl"
        if tr.exists():
            for line in tr.read_text().splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                calls += 1
                if r.get("cost_usd") is None:
                    unknown_worst += worst_call
                else:
                    spent_records += r["cost_usd"]
        ej = ep / "episode.json"
        if ej.exists():
            if json.loads(ej.read_text())["summary"]["status"] == "error":
                error_worst += worst_call
                calls += 1
        else:
            unfinished += 1
            inflight_worst += worst_call

reconstructed = spent_records + unknown_worst + error_worst + inflight_worst + PRE_GUARD_CHECK_USD
baseline_usd = math.ceil(max(reconstructed, ledger_now["charged_usd"]) * 100) / 100  # round up to cents
baseline_calls = calls + IN_FLIGHT_CALLS_MARGIN
print(json.dumps({
    "ledger_before": ledger_now,
    "records_actual_usd": round(spent_records, 6),
    "unknown_cost_worst_usd": round(unknown_worst, 6),
    "error_call_worst_usd": round(error_worst, 6),
    "unfinished_episodes": unfinished,
    "inflight_worst_usd": round(inflight_worst, 6),
    "pre_guard_check_usd": PRE_GUARD_CHECK_USD,
    "reconstructed_usd": round(reconstructed, 6),
    "baseline_usd_rounded_up": baseline_usd,
    "calls_counted": calls,
    "baseline_calls": baseline_calls,
}, indent=2))
if "--write" in sys.argv:
    LEDGER.write_text(json.dumps({"charged_usd": baseline_usd, "calls": baseline_calls}, indent=2))
    print("ledger written:", LEDGER)
