"""One episode: a homogeneous group of agents, one shared model, round-robin turns.

Determinism: the turn order and the game outcomes come from random.Random seeded with
strings derived from the episode seed, so they do not depend on model replies' timing.
Model sampling is NOT seeded (providers do not guarantee it); every prompt and reply is
written to transcript.jsonl so a run can be audited turn by turn.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from engine import Game, InvalidAction, Rules, agent_ids, parse_action
from llm import APIError, BudgetExceeded
from render import system_prompt, turn_prompt


@dataclass(frozen=True)
class EpisodeSpec:
    model: str
    board: bool
    n: int
    rep: int
    seed: int
    turns_per_agent: int
    starting_points: int
    post_max_chars: int
    temperature: float
    max_tokens: int
    prompt_set: str = "prompts"  # folder of prompt templates; "prompts-pooled" is the pooling variant

    @property
    def condition(self) -> str:
        return "board" if self.board else "noboard"


def run_episode(spec: EpisodeSpec, client, budget, out_dir: Path) -> dict:
    """Run one episode, write episode.json and transcript.jsonl to out_dir, return its summary."""
    rules = Rules(
        n=spec.n,
        board=spec.board,
        starting_points=spec.starting_points,
        max_turns=spec.turns_per_agent * spec.n,
        post_max_chars=spec.post_max_chars,
    )
    ids = agent_ids(spec.n)
    order = list(ids)
    random.Random(f"{spec.seed}:order").shuffle(order)
    game = Game.new(rules, random.Random(f"{spec.seed}:games"))
    system = system_prompt(rules, spec.prompt_set)
    last_error: dict[str, str | None] = {a: None for a in ids}

    out_dir.mkdir(parents=True, exist_ok=False)
    status, error = "completed", None
    meter = budget.meter()  # this episode's own dollar and call counters
    tally = {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0,
             "length_limited_replies": 0, "empty_replies": 0}  # per-episode token accounting
    with (out_dir / "transcript.jsonl").open("w", encoding="utf-8") as log:
        try:
            while game.turn < rules.max_turns and not game.is_terminal():
                game.begin_turn()
                actor = order[(game.turn - 1) % spec.n]  # fair round-robin
                user = turn_prompt(game, actor, last_error[actor], spec.prompt_set)
                meta = {
                    "seed": spec.seed, "actor": actor, "turn": game.turn,
                    "balance": game.balances[actor], "played": actor in game.played,
                    "others": [a for a in ids if a != actor], "board": spec.board,
                }
                comp = budget.call(
                    client, model=spec.model, system=system, user=user, meta=meta,
                    temperature=spec.temperature, max_tokens=spec.max_tokens, meter=meter,
                )
                tally["prompt_tokens"] += comp.prompt_tokens
                tally["completion_tokens"] += comp.completion_tokens
                tally["reasoning_tokens"] += comp.reasoning_tokens
                tally["length_limited_replies"] += comp.finish_reason == "length"
                tally["empty_replies"] += not comp.text.strip()
                rec = {"turn": game.turn, "actor": actor, "prompt": user, "reply": comp.text,
                       "finish_reason": comp.finish_reason, "prompt_tokens": comp.prompt_tokens,
                       "completion_tokens": comp.completion_tokens,
                       "reasoning_tokens": comp.reasoning_tokens, "cost_usd": comp.cost_usd,
                       "provider": comp.provider}
                try:
                    rec["applied"] = game.apply(actor, parse_action(comp.text))
                    last_error[actor] = None
                except InvalidAction as e:
                    game.record_invalid(actor, str(e))
                    rec["error"] = str(e)
                    last_error[actor] = str(e)
                log.write(json.dumps(rec) + "\n")
                log.flush()
        except BudgetExceeded as e:
            status, error = "aborted_budget", str(e)
        except APIError as e:
            status, error = "error", str(e)
        except Exception as e:  # a bug, not a model or budget event: record it, never drop the episode
            status, error = "crashed", f"{type(e).__name__}: {e}"

    if status == "completed" and not game.is_terminal():
        status = "truncated"  # the turn limit was reached before every holder voted to end
    game.check_invariants()

    summary = summarise(spec, game, status, error,
                        calls=meter.calls, cost_usd=meter.usd)
    summary.update(tally, max_tokens=spec.max_tokens)
    (out_dir / "episode.json").write_text(json.dumps({
        "spec": asdict(spec),
        "rules": asdict(rules),
        "turn_order": order,
        "summary": summary,
        "events": game.events,
        "board": game.board,
    }, indent=2))
    return summary


def summarise(spec: EpisodeSpec, game: Game, status: str, error: str | None,
               calls: int, cost_usd: float) -> dict:
    """Per-episode metrics, computed from the engine's event log."""
    events = game.events
    plays = [e for e in events if e["action"] == "play"]
    transfers = [e for e in events if e["action"] == "transfer"]
    total = game.total()
    start_total = spec.n * spec.starting_points
    return {
        "model": spec.model,
        "condition": spec.condition,
        "n": spec.n,
        "rep": spec.rep,
        "seed": spec.seed,
        "status": status,
        "error": error,
        "turns": game.turn,
        "max_turns": spec.turns_per_agent * spec.n,
        "final_balances": dict(game.balances),
        "total_final": total,
        "mean_final": total / spec.n,
        "total_start": start_total,
        "total_gain": total - start_total,
        "net_game_points": game.net_game_points,
        "plays": len(plays),
        "wins": sum(1 for e in plays if e["won"]),
        "stake_total": sum(e["stake"] for e in plays),
        "max_stake": max((e["stake"] for e in plays), default=0),
        "transfers": len(transfers),
        "transfer_volume": sum(e["amount"] for e in transfers),
        "posts": len(game.board),
        "vote_ends": sum(1 for e in events if e["action"] == "vote_end"),
        "invalid": sum(1 for e in events if e["action"] == "invalid"),
        "ruined_agents": sum(1 for b in game.balances.values() if b == 0),
        "max_share": (max(game.balances.values()) / total) if total else 0.0,
        "calls": calls,
        "cost_usd": cost_usd,
        "conservation_ok": True,  # check_invariants() ran and raised otherwise
    }
