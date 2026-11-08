"""Aggregate per-episode summaries into per-(model, condition, n) rows.

Only completed episodes enter the means. Truncated (turn limit reached) and failed
episodes are counted separately and are never treated as successes.
"""

from __future__ import annotations


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def aggregate(episodes: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = {}
    for e in episodes:
        groups.setdefault((e["model"], e["condition"], e["n"]), []).append(e)
    rows = []
    for (model, condition, n), es in sorted(groups.items()):
        done = [e for e in es if e["status"] == "completed"]
        rows.append({
            "model": model,
            "condition": condition,
            "n": n,
            "runs": len(es),
            "completed": len(done),
            "truncated": sum(1 for e in es if e["status"] == "truncated"),
            "failed": sum(1 for e in es if e["status"] in ("error", "aborted_budget", "crashed")),
            "mean_total_final": _mean([e["total_final"] for e in done]),
            "mean_mean_final": _mean([e["mean_final"] for e in done]),
            "mean_total_gain": _mean([e["total_gain"] for e in done]),
            "ruined_runs": sum(1 for e in done if e["total_final"] == 0),
            "mean_plays": _mean([e["plays"] for e in done]),
            "mean_max_stake": _mean([e["max_stake"] for e in done]),
            "mean_transfers": _mean([e["transfers"] for e in done]),
            "mean_posts": _mean([e["posts"] for e in done]),
            "mean_invalid": _mean([e["invalid"] for e in done]),
            "mean_turns": _mean([e["turns"] for e in done]),
        })
    return rows
