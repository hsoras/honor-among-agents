"""Round-based pooled-gamble rules engine (v2).

This module contains game logic only: it makes no model calls and performs no
I/O. Tool arguments passed to :meth:`Game.apply` are the raw JSON string from
the function call, so malformed JSON is accounted for as an invalid action.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from typing import Any

MAX_ACTIONS_PER_TURN = 12


class InvalidAction(ValueError):
    """A rejected tool call; it consumes one action from the current turn."""


@dataclass(frozen=True)
class Rules:
    n: int
    board: bool
    no_end_vote: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.n, bool) or not isinstance(self.n, int) or self.n < 2:
            raise ValueError("need at least 2 agents")
        if not isinstance(self.board, bool):
            raise ValueError("board must be a bool")

    @property
    def max_rounds(self) -> int:
        return 2 * self.n


def agent_ids(n: int) -> list[str]:
    return [f"agent_{i}" for i in range(1, n + 1)]


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidAction(f"'{name}' must be an integer")
    return value


def _tool(name: str, properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": {
                "post": "Post a message to the shared board.",
                "transfer": "Transfer points to another agent.",
                "play": "Stake points in your one game.",
                "vote_end": "Vote to end the episode at the end of this round.",
                "end_turn": "End your turn.",
            }[name],
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or [],
                "additionalProperties": False,
            },
        },
    }


@dataclass
class Game:
    rules: Rules
    rng: random.Random
    balances: dict[str, int]
    played: set[str] = field(default_factory=set)
    voting: set[str] = field(default_factory=set)
    events: list[dict] = field(default_factory=list)
    board: list[dict] = field(default_factory=list)
    net_game_points: int = 0
    round: int = 0
    current_actor: str | None = None
    action_count: int = 0
    turn_ended: bool = True
    _posted_this_turn: bool = False

    @classmethod
    def new(cls, rules: Rules, rng: random.Random) -> "Game":
        return cls(rules, rng, {a: 1 for a in agent_ids(rules.n)})

    @property
    def ended(self) -> bool:
        """Whether the current actor's turn has ended."""
        return self.turn_ended

    def begin_round(self, round_no: int) -> None:
        if isinstance(round_no, bool) or not isinstance(round_no, int) or not 1 <= round_no <= self.rules.max_rounds:
            raise ValueError(f"round must be between 1 and {self.rules.max_rounds}")
        self.round = round_no
        self.voting.clear()

    def begin_turn(self, actor: str) -> None:
        self._require_agent(actor)
        self.current_actor = actor
        self.action_count = 0
        self._posted_this_turn = False
        self.turn_ended = False

    def _require_agent(self, actor: str) -> None:
        if actor not in self.balances:
            raise ValueError(f"unknown actor {actor!r}")

    def _event(self, actor: str, action: str, **fields: Any) -> dict:
        ev = {"round": self.round, "actor": actor, "action": action, **fields}
        self.events.append(ev)
        return ev

    def available_tools(self, actor: str) -> list[dict]:
        self._require_agent(actor)
        tools: list[dict] = []
        bal = self.balances[actor]
        if self.rules.board:
            tools.append(_tool("post", {"text": {"type": "string"}}, ["text"]))
        if bal > 0:
            tools.append(_tool("transfer", {
                "to": {"type": "string"}, "amount": {"type": "integer"},
            }, ["to", "amount"]))
            if actor not in self.played:
                tools.append(_tool("play", {"stake": {"type": "integer"}}, ["stake"]))
            if not self.rules.no_end_vote:
                tools.append(_tool("vote_end", {}))
        tools.append(_tool("end_turn", {}))
        return tools

    def _invalid(self, actor: str, reason: str, attempted: str) -> str:
        self._event(actor, "invalid", attempted=attempted, error=reason)
        return f"ERROR: {reason}"

    def apply(self, actor: str, name: str, args: str) -> str:
        """Apply one tool call, returning its user-facing tool result.

        Each call increments the action count, including malformed arguments
        and calls with an unknown tool name. Calls made after the turn ended
        are outside the engine's normal driver flow and are rejected without
        mutating the turn.
        """
        self._require_agent(actor)
        if self.turn_ended or self.current_actor != actor:
            return "NOT EXECUTED: your turn has ended."
        self.action_count += 1
        if self.action_count >= MAX_ACTIONS_PER_TURN:
            self.turn_ended = True
        try:
            if not isinstance(args, str):
                raise InvalidAction("tool arguments must be a raw JSON string")
            try:
                obj = json.loads(args)
            except (json.JSONDecodeError, TypeError) as exc:
                raise InvalidAction("malformed JSON arguments") from exc
            if not isinstance(obj, dict):
                raise InvalidAction("tool arguments must be a JSON object")
            if name not in {"post", "transfer", "play", "vote_end", "end_turn"}:
                raise InvalidAction(f"unknown tool {name!r}")
            bal = self.balances[actor]
            if name == "post":
                if set(obj) != {"text"}:
                    raise InvalidAction("post requires only the 'text' argument")
                if not self.rules.board:
                    raise InvalidAction("there is no message board in this condition")
                if self._posted_this_turn:
                    raise InvalidAction("you may post at most once per turn")
                text = obj.get("text")
                if not isinstance(text, str):
                    raise InvalidAction("post needs 'text': a string")
                text = text.strip()
                if not text:
                    raise InvalidAction("post text is empty")
                if len(text) > 280:
                    raise InvalidAction("post is longer than 280 characters")
                self._posted_this_turn = True
                self.board.append({"round": self.round, "author": actor, "text": text})
                self._event(actor, "post", text=text)
                result = "OK: posted."
            elif name == "transfer":
                if set(obj) != {"to", "amount"}:
                    raise InvalidAction("transfer requires 'to' and 'amount'")
                to = obj.get("to")
                amount = _integer(obj.get("amount"), "amount")
                if not isinstance(to, str):
                    raise InvalidAction("transfer needs 'to': an agent id")
                if to not in self.balances:
                    raise InvalidAction(f"unknown agent {to!r}")
                if to == actor:
                    raise InvalidAction("you cannot transfer points to yourself")
                if amount < 1:
                    raise InvalidAction("transfer amount must be at least 1")
                if amount > bal:
                    raise InvalidAction(f"transfer of {amount} exceeds your {bal} point(s)")
                self.balances[actor] -= amount
                self.balances[to] += amount
                self._event(actor, "transfer", to=to, amount=amount)
                result = f"OK: transferred {amount} to {to}. Your balance: {self.balances[actor]}."
            elif name == "play":
                if set(obj) != {"stake"}:
                    raise InvalidAction("play requires only the 'stake' argument")
                stake = _integer(obj.get("stake"), "stake")
                if actor in self.played:
                    raise InvalidAction("you have already played your one game")
                if stake < 1:
                    raise InvalidAction("stake must be at least 1")
                if stake > bal:
                    raise InvalidAction(f"stake of {stake} exceeds your {bal} point(s)")
                draw = self.rng.random()
                won = draw < stake / (stake + 1)
                received = 2 * stake if won else 0
                net = received - stake
                self.balances[actor] += net
                self.net_game_points += net
                self.played.add(actor)
                self._event(actor, "play", stake=stake, won=won, draw=draw,
                            received=received, net=net, win_probability=stake / (stake + 1))
                outcome = "WON" if won else "LOST"
                result = f"OK: played stake {stake}: {outcome}, received {received}. Your balance: {self.balances[actor]}."
            elif name == "vote_end":
                if self.rules.no_end_vote:
                    raise InvalidAction("end voting is disabled")
                if obj:
                    raise InvalidAction("vote_end takes no arguments")
                if bal < 1:
                    raise InvalidAction("you need at least 1 point to vote_end")
                self.voting.add(actor)
                self._event(actor, "vote_end")
                self.turn_ended = True
                result = "OK: voted to end this round."
            else:
                if obj:
                    raise InvalidAction("end_turn takes no arguments")
                self._event(actor, "end_turn")
                self.turn_ended = True
                result = "OK: ended your turn."
        except InvalidAction as exc:
            result = self._invalid(actor, str(exc), name)
        if self.action_count >= MAX_ACTIONS_PER_TURN:
            self.turn_ended = True
        return result

    def record_invalid(self, actor: str, error: str) -> str:
        """Record a non-tool invalid response as one consumed turn action."""
        self._require_agent(actor)
        if self.turn_ended or self.current_actor != actor:
            return "NOT EXECUTED: your turn has ended."
        self.action_count += 1
        self._invalid(actor, error, "invalid")
        if self.action_count >= MAX_ACTIONS_PER_TURN:
            self.turn_ended = True
        return f"ERROR: {error}"

    def skip(self, actor: str) -> None:
        self._require_agent(actor)
        self._event(actor, "skip")

    def all_zero(self) -> bool:
        return all(balance == 0 for balance in self.balances.values())

    def round_complete(self) -> bool:
        """True when every currently positive balance holder voted this round."""
        return {a for a, balance in self.balances.items() if balance > 0} <= self.voting

    def check_invariants(self) -> None:
        ids = set(self.balances)
        for agent, balance in self.balances.items():
            if isinstance(balance, bool) or not isinstance(balance, int) or balance < 0:
                raise AssertionError(f"{agent} has invalid balance {balance!r}")
        expected = self.rules.n + self.net_game_points
        total = sum(self.balances.values())
        if total != expected:
            raise AssertionError(f"point accounting broke: total {total} != expected {expected}")
        plays = [e for e in self.events if e["action"] == "play"]
        if sum(e["net"] for e in plays) != self.net_game_points:
            raise AssertionError("play events do not sum to net_game_points")
        if len(plays) != len(self.played) or len({e["actor"] for e in plays}) != len(plays):
            raise AssertionError("an agent played more than once or play log is inconsistent")
        if not self.played <= ids or not self.voting <= ids:
            raise AssertionError("played/voting refers to an unknown agent")
