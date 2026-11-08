"""Append-only run records, and a loader that reads every run folder without dropping incomplete ones.

Each run folder holds:
- records.jsonl (new runs only): one JSON object per line, appended and fsynced as events happen.
  Events: run_started, episode_started, episode_finished, episode_crashed, episode_not_started,
  run_finished. An episode that has episode_started but no finish line was interrupted.
- config.json, metrics.json (written at the end of a run, and absent from interrupted runs).
- episodes/<slug>__<condition>__n<N>__r<R>/episode.json and transcript.jsonl. episode.json is
  written when an episode ends, whatever its status. A folder without it is incomplete.

Nothing here rewrites a record. `select_episodes` picks ONE record per (model, condition, n, rep)
across folders, by status rank and then by run name (timestamps sort chronologically). Every
other record for the same key is returned as superseded, with its reason, so none disappears silently.
"""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path

RECORDS_FILE = "records.jsonl"
FOLDER_RE = re.compile(r"^(?P<slug>.+)__(?P<cond>board|noboard)__n(?P<n>\d+)__r(?P<rep>\d+)$")
# Rank used when choosing among duplicate records for one episode key (higher wins).
STATUS_RANK = {"completed": 3, "truncated": 2, "aborted_budget": 1, "error": 1, "crashed": 1,
               "interrupted": 0, "incomplete": 0, "not_started": 0}


class RunRecords:
    """Append-only JSONL log for one run folder. Thread-safe; every line is flushed and fsynced."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh = path.open("a", encoding="utf-8")  # append only: never truncates an existing log
        self._lock = threading.Lock()

    def append(self, event: str, **fields) -> None:
        row = {"ts": datetime.now().isoformat(timespec="seconds"), "event": event, **fields}
        line = json.dumps(row, sort_keys=True) + "\n"
        with self._lock:
            self._fh.write(line)
            self._fh.flush()
            os.fsync(self._fh.fileno())

    def close(self) -> None:
        with self._lock:
            self._fh.close()


def run_kind(name: str) -> str:
    """Folder-name classification. Original grid runs have no suffix."""
    if name.endswith("-mock"):
        return "mock"
    if name.endswith("-pilot"):
        return "pilot"
    if "multiplier" in name:
        return "multiplier"  # the separate agent-chosen-multiplier game: not analysed with the original
    if "-pooled" in name:
        return "pooled"  # original payoff, pooling-explicit prompt variant: reported separately
    return "grid"


def key_of(model: str, condition: str, n: int, rep: int) -> tuple:
    """Episode identity. Model slugs use '_' for '/', matching the episode folder names."""
    return (model.replace("/", "_"), condition, int(n), int(rep))


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_run(run_dir: Path) -> dict:
    """Everything one run folder holds, complete or not. Never raises on a partial folder."""
    name = run_dir.name
    config_path = run_dir / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else None
    records = _read_jsonl(run_dir / RECORDS_FILE) if (run_dir / RECORDS_FILE).exists() else []
    episodes, incomplete = [], []
    finished_keys = set()
    for ep_dir in sorted((run_dir / "episodes").glob("*")) if (run_dir / "episodes").exists() else []:
        m = FOLDER_RE.match(ep_dir.name)
        ep_file = ep_dir / "episode.json"
        if ep_file.exists():
            data = json.loads(ep_file.read_text(encoding="utf-8"))
            s = dict(data["summary"])
            s["run"], s["dir"], s["kind"] = name, ep_dir.name, run_kind(name)
            s["key"] = key_of(s["model"], s["condition"], s["n"], s["rep"])
            s["turns_logged"] = len((ep_dir / "transcript.jsonl").read_text(encoding="utf-8").splitlines()) \
                if (ep_dir / "transcript.jsonl").exists() else 0
            episodes.append(s)
            finished_keys.add(s["key"])
        elif m:  # folder exists but episode.json does not: the episode was interrupted mid-run
            turns = len((ep_dir / "transcript.jsonl").read_text(encoding="utf-8").splitlines()) \
                if (ep_dir / "transcript.jsonl").exists() else 0
            key = (m["slug"], m["cond"], int(m["n"]), int(m["rep"]))  # folder names already use '_' slugs
            incomplete.append({"key": key, "run": name, "dir": ep_dir.name, "kind": run_kind(name),
                               "status": "incomplete", "turns_logged": turns,
                               "reason": f"no episode.json; transcript has {turns} turn(s)"})
    # Events for episodes that never reached a folder or an episode.json (from the append-only log).
    for ev in records:
        if ev.get("event") == "episode_not_started":
            key = key_of(ev["model"], ev["condition"], ev["n"], ev["rep"])
            if key not in finished_keys:
                incomplete.append({"key": key, "run": name, "dir": None, "kind": run_kind(name),
                                   "status": "not_started", "turns_logged": 0,
                                   "reason": "not started: run was stopped before this episode began"})
        elif ev.get("event") == "episode_crashed":
            key = key_of(ev["model"], ev["condition"], ev["n"], ev["rep"])
            if key not in finished_keys:
                incomplete.append({"key": key, "run": name, "dir": ev.get("dir"), "kind": run_kind(name),
                                   "status": "crashed", "turns_logged": 0,
                                   "reason": f"crashed outside the episode loop: {ev.get('error', '')[:200]}"})
    started = {key_of(ev["model"], ev["condition"], ev["n"], ev["rep"])
               for ev in records if ev.get("event") == "episode_started"}
    for key in started - finished_keys:
        if not any(i["key"] == key for i in incomplete):
            incomplete.append({"key": key, "run": name, "dir": None, "kind": run_kind(name),
                               "status": "incomplete", "turns_logged": 0,
                               "reason": "started but no finish record: the run stopped during this episode"})
    run_finished = [ev for ev in records if ev.get("event") == "run_finished"]
    return {
        "name": name, "dir": run_dir, "kind": run_kind(name), "config": config,
        "has_records": bool(records), "has_metrics": (run_dir / "metrics.json").exists(),
        "run_finished": run_finished[-1] if run_finished else None,
        "episodes": episodes, "incomplete": incomplete,
    }


def select_episodes(runs: list[dict]) -> tuple[list[dict], list[dict]]:
    """One chosen record per episode key across runs. Returns (chosen, superseded).

    Chosen: the highest status rank, then the latest run name. Incomplete entries can be chosen
    only when nothing better exists for that key; they are then unresolved, with a status of
    'incomplete', 'interrupted', 'not_started' or 'crashed'. Superseded entries keep their reason.
    """
    candidates: dict[tuple, list[dict]] = {}
    for run in runs:
        for e in run["episodes"]:
            candidates.setdefault(e["key"], []).append(e)
        for e in run["incomplete"]:
            candidates.setdefault(e["key"], []).append(e)
    chosen, superseded = [], []
    for key in sorted(candidates):
        recs = candidates[key]
        best = max(recs, key=lambda r: (STATUS_RANK.get(r["status"], 0), r["run"], r.get("dir") or ""))
        chosen.append(best)
        for r in recs:
            if r is not best:
                superseded.append({**r, "superseded_by": f"{best['run']}/{best.get('dir') or '-'}"
                                   f" ({best['status']})"})
    return chosen, superseded


def iter_calls(run_dir: Path, ep_dir_name: str):
    """Per-call rows from one episode's transcript (settled costs, tokens, finish reasons)."""
    path = run_dir / "episodes" / ep_dir_name / "transcript.jsonl"
    if not path.exists():
        return
    for row in _read_jsonl(path):
        yield row
