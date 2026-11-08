"""Round-based v2 episode runner with persistent per-agent tool conversations."""
from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from engine_v2 import Game, Rules, agent_ids
from llm import APIError, BudgetExceeded
from render_v2 import render_turn_start


@dataclass(frozen=True)
class EpisodeSpec:
    model: str
    board: bool
    n: int
    rep: int
    seed: int
    max_tokens: int = 16384
    max_rounds: int | None = None
    no_end_vote: bool = False
    variant: str = "main"

    @property
    def condition(self) -> str:
        return "board" if self.board else "noboard"


def _message(obj):
    """Normalize chat completion wrappers while preserving the returned assistant payload."""
    if isinstance(obj, dict):
        if "choices" in obj:
            return obj["choices"][0]["message"], obj["choices"][0].get("finish_reason"), obj
        return obj.get("message", obj), obj.get("finish_reason"), obj
    raw = getattr(obj, "raw", None)
    msg = getattr(obj, "message", None)
    if msg is None and raw:
        return _message(raw)
    if msg is None:
        msg = {"role": "assistant", "content": getattr(obj, "text", "")}
    elif not isinstance(msg, dict):
        msg = msg.model_dump(exclude_none=True) if hasattr(msg, "model_dump") else dict(msg)
    return msg, getattr(obj, "finish_reason", None), raw or obj


def _usage(raw, obj):
    usage = raw.get("usage", {}) if isinstance(raw, dict) else getattr(obj, "usage", None)
    if not isinstance(usage, dict):
        usage = usage.model_dump() if hasattr(usage, "model_dump") else {}
    details = usage.get("completion_tokens_details") or {}
    return (int(usage.get("prompt_tokens", getattr(obj, "prompt_tokens", 0)) or 0),
            int(usage.get("completion_tokens", getattr(obj, "completion_tokens", 0)) or 0),
            int(details.get("reasoning_tokens", getattr(obj, "reasoning_tokens", 0)) or 0),
            usage.get("cost", getattr(obj, "cost_usd", None)))


def _chat(client, budget, *, model, messages, tools, max_tokens, meter, meta):
    if budget is not None and hasattr(budget, "call_chat"):
        return budget.call_chat(client, model=model, messages=messages, tools=tools,
                                max_tokens=max_tokens, meter=meter, meta=meta)
    # Mock clients and lightweight test doubles can implement the direct chat interface.
    if hasattr(client, "chat"):
        return client.chat(model=model, messages=messages, tools=tools,
                           max_tokens=max_tokens, meta=meta)
    raise APIError("chat integration unavailable: expected Budget.call_chat or client.chat")


def run_episode(spec: EpisodeSpec, client, budget, out_dir: Path, system_prompt: str,
                max_tokens: int | None = None) -> dict:
    """Run one episode, persisting every tool-call cycle and each agent's full history."""
    rules = Rules(n=spec.n, board=spec.board, no_end_vote=spec.no_end_vote)
    rounds = spec.max_rounds or 2 * spec.n
    game = Game.new(rules, random.Random(f"{spec.seed}:games"))
    ids = agent_ids(spec.n)
    tokens_cap = max_tokens or spec.max_tokens
    histories = {a: [{"role": "system", "content": system_prompt}] for a in ids}
    event_cursors = {a: 0 for a in ids}
    board_cursors = {a: 0 for a in ids}
    pending_cursors = {a: 1 for a in ids}
    actions_per_turn: list[int] = []
    tally = dict(prompt_tokens=0, completion_tokens=0, reasoning_tokens=0,
                 length_limited_replies=0)
    status, error = "completed", None
    meter = budget.meter() if budget is not None else None
    out_dir.mkdir(parents=True, exist_ok=False)
    try:
        with (out_dir / "transcript.jsonl").open("w", encoding="utf-8") as log:
            for round_no in range(1, rounds + 1):
                if game.all_zero():
                    break
                game.begin_round(round_no)
                for actor in ids:
                    if game.all_zero():
                        break
                    if game.balances[actor] == 0 and not rules.board:
                        game.skip(actor)
                        continue
                    game.begin_turn(actor)
                    turn_count = 0
                    game.turn_ended = False
                    user = render_turn_start(game, actor, event_cursors[actor], board_cursors[actor])
                    histories[actor].append({"role": "user", "content": user})
                    turn_events_start, turn_posts_start = len(game.events), len(game.board)
                    call_index = 0
                    while not game.turn_ended:
                        tools = game.available_tools(actor)
                        call_messages = histories[actor][pending_cursors[actor]:]
                        pending_cursors[actor] = len(histories[actor]) + 1
                        reply = _chat(client, budget, model=spec.model, messages=histories[actor],
                                      tools=tools, max_tokens=tokens_cap, meter=meter,
                                      meta={"seed": spec.seed, "actor": actor, "round": round_no,
                                            "step": turn_count, "balance": game.balances[actor],
                                            "played": actor in game.played, "board": spec.board,
                                            "others": [a for a in ids if a != actor]})
                        assistant, finish, raw = _message(reply)
                        # Persist the exact assistant message, including reasoning fields and tool calls.
                        histories[actor].append(assistant)
                        calls = assistant.get("tool_calls") or []
                        prompt_t, completion_t, reasoning_t, cost = _usage(raw, reply)
                        tally["prompt_tokens"] += prompt_t
                        tally["completion_tokens"] += completion_t
                        tally["reasoning_tokens"] += reasoning_t
                        tally["length_limited_replies"] += finish == "length"
                        results = []
                        appended_messages = call_messages
                        if not calls:
                            game.turn_ended = True
                        else:
                            for call in calls:
                                fn = call.get("function", {})
                                name = fn.get("name", "")
                                raw_args = fn.get("arguments", "")
                                if game.turn_ended:
                                    result = "NOT EXECUTED: your turn has ended."
                                else:
                                    result = game.apply(actor, name, raw_args)
                                    if game.all_zero():
                                        game.turn_ended = True
                                results.append({"id": call.get("id"), "name": name, "arguments": raw_args,
                                                "result": result})
                                histories[actor].append({"role": "tool", "tool_call_id": call.get("id"),
                                                        "content": result})
                            turn_count = game.action_count
                        log.write(json.dumps({"round": round_no, "actor": actor, "step": call_index,
                            "messages": appended_messages,
                            "assistant": assistant, "applied": results,
                            "prompt_tokens": prompt_t, "completion_tokens": completion_t,
                            "reasoning_tokens": reasoning_t, "cost_usd": cost,
                            "finish_reason": finish, "provider": (raw.get("provider") if isinstance(raw, dict)
                                                                     else getattr(reply, "provider", None))}) + "\n")
                        log.flush()
                        call_index += 1
                    actions_per_turn.append(turn_count)
                    event_cursors[actor] = len(game.events)
                    board_cursors[actor] = len(game.board)
                if not spec.no_end_vote and game.round_complete():
                    break
            if not spec.no_end_vote and status == "completed" and not game.round_complete() and not game.all_zero() and round_no >= rounds:
                status = "truncated"
    except BudgetExceeded as exc:
        status, error = "aborted_budget", str(exc)
    except APIError as exc:
        status, error = "error", str(exc)
    except Exception as exc:
        status, error = "error", f"{type(exc).__name__}: {exc}"
    game.check_invariants()
    summary = summarise(spec, game, status, error, actions_per_turn,
                        meter.calls if meter else len(actions_per_turn), meter.usd if meter else 0.0, tally, rounds)
    (out_dir / "episode.json").write_text(json.dumps({"spec": asdict(spec), "rules": asdict(rules),
        "summary": summary, "events": game.events, "board": game.board,
        "conversations": histories}, indent=2), encoding="utf-8")
    return summary


def summarise(spec, game, status, error, actions_per_turn, calls, cost_usd, tally=None, max_rounds=None):
    events = game.events
    plays = [e for e in events if e.get("action") == "play"]
    transfers = [e for e in events if e.get("action") == "transfer"]
    total = sum(game.balances.values())
    return {"model": spec.model, "condition": spec.condition, "n": spec.n, "rep": spec.rep,
        "seed": spec.seed, "status": status, "error": error, "rounds": game.round,
        "max_rounds": max_rounds or 2 * spec.n, "final_balances": dict(game.balances),
        "total_final": total, "total_start": spec.n, "net_game_points": game.net_game_points,
        "plays": len(plays), "wins": sum(bool(e.get("won")) for e in plays),
        "max_stake": max((e.get("stake", 0) for e in plays), default=0),
        "full_pool": max((e.get("stake", 0) for e in plays), default=0) == spec.n,
        "transfers": len(transfers), "transfer_volume": sum(e.get("amount", 0) for e in transfers),
        "posts": len(game.board), "vote_ends": sum(e.get("action") == "vote_end" for e in events),
        "invalid_actions": sum(e.get("action") == "invalid" for e in events),
        "actions_per_turn": sum(actions_per_turn) / len(actions_per_turn) if actions_per_turn else 0.0,
        "calls": calls, "cost_usd": cost_usd, **(tally or {}),
        "max_share": max(game.balances.values()) / total if total else 0.0,
        "ruined_agents": sum(b == 0 for b in game.balances.values())}
