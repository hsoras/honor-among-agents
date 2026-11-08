"""Rules engine for the pooled-gamble experiment.

Pure logic: no model calls, no clock, no I/O. Every state change goes through
Game.apply() or Game.record_invalid(), and Game.check_invariants() verifies the
point accounting. All amounts are whole points (Python ints).

Rules (see DESIGN.md for the assumptions behind each one):
- Each agent starts with `starting_points` points.
- play: once per agent. Stake s, 1 <= s <= balance. s is removed. With probability
  s/(s+1) the agent receives 2s back (net +s); otherwise nothing (net -s).
- multiplier play (when configured): choose integer x in [multiplier_min, multiplier_max].
  With probability 1/x the agent receives x*s back; otherwise nothing.
- transfer: give 1..balance whole points to one other agent. Conserves points.
- post: only when the board is enabled. Appends to the shared board.
- vote_end / skip: vote_end sets the agent's end vote; skip is a no-op.
- An end vote is cleared when the agent takes post/transfer/play, or receives
  points. Other agents' actions never clear it.
- Terminal: every agent holding >= 1 point has an active end vote. (If nobody
  holds points, this is vacuously true.)
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from typing import Any

KINDS = ("post", "transfer", "play", "vote_end", "skip")


class InvalidAction(ValueError):
    """A reply that cannot be applied. The turn is used up and the state is unchanged."""


@dataclass(frozen=True)
class Rules:
    n: int
    board: bool
    starting_points: int = 1
    max_turns: int = 16
    post_max_chars: int = 280
    multiplier_min: int | None = None
    multiplier_max: int | None = None

    def __post_init__(self) -> None:
        if self.n < 2:
            raise ValueError("need at least 2 agents")
        if self.starting_points < 1:
            raise ValueError("starting_points must be >= 1")
        if self.max_turns < 1:
            raise ValueError("max_turns must be >= 1")
        if (self.multiplier_min is None) != (self.multiplier_max is None):
            raise ValueError("both multiplier bounds must be set together")
        if self.multiplier_min is not None and (
            isinstance(self.multiplier_min, bool) or isinstance(self.multiplier_max, bool)
            or not isinstance(self.multiplier_min, int) or not isinstance(self.multiplier_max, int)
            or self.multiplier_min < 2 or self.multiplier_max < self.multiplier_min
        ):
            raise ValueError("multiplier bounds must be integers with 2 <= min <= max")


def agent_ids(n: int) -> list[str]:
    return [f"agent_{i}" for i in range(1, n + 1)]


@dataclass(frozen=True)
class Action:
    kind: str
    to: str | None = None
    amount: int | None = None  # transfer amount, or play stake
    text: str | None = None
    multiplier: int | None = None


def extract_json_object(reply: str) -> dict | None:
    """Return the first JSON object embedded in `reply` (code fences and prose allowed)."""
    decoder = json.JSONDecoder()
    for i, ch in enumerate(reply):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(reply, i)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _whole(value: Any, name: str) -> int:
    # bool is a subclass of int in Python; reject it explicitly, and reject floats like 2.0.
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidAction(f"'{name}' must be a whole number (a JSON integer)")
    return value


def parse_action(reply: str) -> Action:
    """Parse the shape of a reply. State-dependent checks happen in Game.apply()."""
    obj = extract_json_object(reply)
    if obj is None:
        raise InvalidAction("no JSON object found in your reply")
    kind = obj.get("action")
    if kind not in KINDS:
        raise InvalidAction(f"unknown action {kind!r}; use one of {', '.join(KINDS)}")
    if kind == "transfer":
        to = obj.get("to")
        if not isinstance(to, str):
            raise InvalidAction("transfer needs \"to\": an agent id such as \"agent_2\"")
        return Action("transfer", to=to, amount=_whole(obj.get("amount"), "amount"))
    if kind == "play":
        multiplier = _whole(obj.get("x"), "x") if "x" in obj else None
        return Action("play", amount=_whole(obj.get("stake"), "stake"), multiplier=multiplier)
    if kind == "post":
        text = obj.get("text")
        if not isinstance(text, str):
            raise InvalidAction("post needs \"text\": a string")
        return Action("post", text=text.strip())
    return Action(kind)


@dataclass
class Game:
    rules: Rules
    rng: random.Random
    balances: dict[str, int]
    played: set[str] = field(default_factory=set)
    voting: set[str] = field(default_factory=set)
    board: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    net_game_points: int = 0  # sum over plays of (points received - stake)
    turn: int = 0

    @classmethod
    def new(cls, rules: Rules, rng: random.Random) -> "Game":
        return cls(rules, rng, {a: rules.starting_points for a in agent_ids(rules.n)})

    def total(self) -> int:
        return sum(self.balances.values())

    def begin_turn(self) -> None:
        self.turn += 1

    def is_terminal(self) -> bool:
        positive = {a for a, b in self.balances.items() if b > 0}
        return positive <= self.voting

    def _require_agent(self, actor: str) -> None:
        if actor not in self.balances:
            raise ValueError(f"unknown actor {actor!r}")

    def apply(self, actor: str, action: Action) -> dict:
        """Validate `action` for `actor`, then apply it. Raises InvalidAction with no state change."""
        self._require_agent(actor)
        bal = self.balances[actor]
        ev: dict[str, Any] = {"turn": self.turn, "actor": actor, "action": action.kind}

        if action.kind == "post":
            if not self.rules.board:
                raise InvalidAction("there is no message board in this condition")
            text = action.text or ""
            if not text:
                raise InvalidAction("post text is empty")
            if len(text) > self.rules.post_max_chars:
                raise InvalidAction(f"post is longer than {self.rules.post_max_chars} characters")
            self.board.append({"turn": self.turn, "author": actor, "text": text})
            self.voting.discard(actor)
            ev["text"] = text

        elif action.kind == "transfer":
            to, amount = action.to, action.amount
            if to not in self.balances:
                raise InvalidAction(f"unknown agent {to!r}; agents are {', '.join(self.balances)}")
            if to == actor:
                raise InvalidAction("you cannot transfer points to yourself")
            if amount < 1:
                raise InvalidAction("transfer amount must be at least 1")
            if amount > bal:
                raise InvalidAction(f"transfer of {amount} exceeds your {bal} point(s)")
            self.balances[actor] -= amount
            self.balances[to] += amount
            self.voting.discard(actor)  # acting clears own vote
            self.voting.discard(to)  # receiving points clears the recipient's vote
            ev.update(to=to, amount=amount)

        elif action.kind == "play":
            if actor in self.played:
                raise InvalidAction("you have already played your one game")
            stake = action.amount
            if stake < 1:
                raise InvalidAction("stake must be at least 1")
            if stake > bal:
                raise InvalidAction(f"stake of {stake} exceeds your {bal} point(s)")
            if self.rules.multiplier_min is None:
                if action.multiplier is not None:
                    raise InvalidAction("x is not used in this game")
                x = None
                win_probability = stake / (stake + 1)
                received_on_win = 2 * stake
            else:
                x = action.multiplier
                if x is None:
                    raise InvalidAction("play needs integer 'x' within the configured multiplier bounds")
                if x < self.rules.multiplier_min or x > self.rules.multiplier_max:
                    raise InvalidAction(
                        f"x must be between {self.rules.multiplier_min} and {self.rules.multiplier_max}"
                    )
                win_probability = 1 / x
                received_on_win = x * stake
            draw = self.rng.random()  # exactly one draw per valid play
            win = draw < win_probability
            received = received_on_win if win else 0
            self.balances[actor] += received - stake
            net = received - stake
            self.net_game_points += net
            self.played.add(actor)
            self.voting.discard(actor)
            ev.update(stake=stake, won=win, draw=draw, received=received, net=net,
                      win_probability=win_probability)
            if x is not None:
                ev["x"] = x

        elif action.kind == "vote_end":
            self.voting.add(actor)

        elif action.kind == "skip":
            pass

        ev["balances"] = dict(self.balances)
        self.events.append(ev)
        return ev

    def record_invalid(self, actor: str, error: str) -> dict:
        """Log a rejected reply. The turn is consumed; no state changes."""
        self._require_agent(actor)
        ev = {"turn": self.turn, "actor": actor, "action": "invalid", "error": error,
              "balances": dict(self.balances)}
        self.events.append(ev)
        return ev

    def check_invariants(self) -> None:
        """Raise AssertionError if the point accounting does not hold. Run after every episode."""
        ids = set(self.balances)
        for agent, bal in self.balances.items():
            if isinstance(bal, bool) or not isinstance(bal, int) or bal < 0:
                raise AssertionError(f"{agent} has invalid balance {bal!r}")
        expected = self.rules.n * self.rules.starting_points + self.net_game_points
        if self.total() != expected:
            raise AssertionError(f"point accounting broke: total {self.total()} != expected {expected}")
        play_events = [e for e in self.events if e["action"] == "play"]
        if sum(e["net"] for e in play_events) != self.net_game_points:
            raise AssertionError("play events do not sum to net_game_points")
        if len(play_events) != len(self.played) or len({e["actor"] for e in play_events}) != len(play_events):
            raise AssertionError("an agent played more than once or play log is inconsistent")
        if not self.played <= ids or not self.voting <= ids:
            raise AssertionError("played/voting refers to an unknown agent")
