"""Render the prompt templates in prompts/ from engine state. Pure; no model calls."""

from __future__ import annotations

from pathlib import Path
from string import Template

from engine import Game, Rules

PROMPTS_ROOT = Path(__file__).resolve().parent
PROMPTS = PROMPTS_ROOT / "prompts"  # the original prompt set; every earlier run used these files


def prompt_dir(prompt_set: str = "prompts") -> Path:
    """A prompt set is a sibling folder of this module named 'prompts' or 'prompts-<variant>'."""
    if prompt_set != "prompts" and not (prompt_set.startswith("prompts-") and "/" not in prompt_set):
        raise ValueError(f"unknown prompt set {prompt_set!r}")
    return PROMPTS_ROOT / prompt_set


def _load(name: str, prompt_set: str = "prompts") -> str:
    return (prompt_dir(prompt_set) / name).read_text(encoding="utf-8")


def system_prompt(rules: Rules, prompt_set: str = "prompts") -> str:
    """Identical for every agent in a condition. The agent's id arrives in the turn prompt."""
    name = "system_board.md" if rules.board else "system_noboard.md"
    prompt = Template(_load(name, prompt_set)).substitute(
        n=rules.n,
        start=rules.starting_points,
        max_turns=rules.max_turns,
        post_max=rules.post_max_chars,
    )
    if rules.multiplier_min is not None:
        old = ("Play: each agent may play its one game, once per episode. Choose a stake s, a whole number with "
               "1 <= s <= your points. The stake is removed from your balance. With probability s/(s+1) "
               "you receive 2s points back (net +s). Otherwise you receive nothing (net -s). The outcome is random.")
        new = ("Play: each agent may play its one game, once per episode. Choose a whole-number stake s with "
               "1 <= s <= your points, and choose an integer multiplier x with "
               f"{rules.multiplier_min} <= x <= {rules.multiplier_max}. The stake is removed from your balance. "
               "With probability 1/x you receive x*s points back (a net gain of (x-1)*s); otherwise you "
               "receive nothing (a net loss of s). Your chosen x determines the probability and payout. "
               "The outcome is random.")
        prompt = prompt.replace(old, new)
    return prompt


def _describe(ev: dict) -> str | None:
    """One public line per public action. Posts and invalid replies are not listed here."""
    actor, t = ev["actor"], ev["turn"]
    kind = ev["action"]
    if kind == "transfer":
        return f"turn {t}: {actor} transferred {ev['amount']} point(s) to {ev['to']}"
    if kind == "play":
        multiplier = f" at x={ev['x']}" if "x" in ev else ""
        if ev["won"]:
            return f"turn {t}: {actor} played a stake of {ev['stake']}{multiplier}: WON, received {ev['received']} point(s)"
        return f"turn {t}: {actor} played a stake of {ev['stake']}{multiplier}: LOST the stake"
    if kind == "vote_end":
        return f"turn {t}: {actor} voted to end"
    if kind == "skip":
        return f"turn {t}: {actor} skipped"
    return None


def turn_prompt(game: Game, actor: str, last_error: str | None = None, prompt_set: str = "prompts") -> str:
    """The user message for one turn. Stateless: it shows the whole public state each time."""
    bal = game.balances[actor]
    played_line = (
        "You have already played your one game." if actor in game.played
        else "You have not played your game yet."
    )
    vote_line = (
        "Your end vote is active." if actor in game.voting
        else "You have no active end vote."
    )
    agent_lines = []
    for other, b in game.balances.items():
        agent_lines.append(
            f"- {other}{' (you)' if other == actor else ''}: {b} point(s); "
            f"played: {'yes' if other in game.played else 'no'}; "
            f"end vote: {'active' if other in game.voting else 'none'}"
        )
    events = [line for line in (_describe(e) for e in game.events) if line is not None]
    if game.rules.board:
        posts = [f"[turn {p['turn']}] {p['author']}: {p['text']}" for p in game.board]
        board_section = "\nMessage board (all posts, oldest first):\n" + ("\n".join(posts) or "(no posts yet)") + "\n"
    else:
        board_section = ""
    error = f"Your previous reply was rejected ({last_error}). It used your turn.\n" if last_error else ""
    prompt = Template(_load("turn.md", prompt_set)).substitute(
        turn=game.turn,
        max_turns=game.rules.max_turns,
        agent_id=actor,
        balance=bal,
        played_line=played_line,
        vote_line=vote_line,
        error=error,
        agents="\n".join(agent_lines),
        events="\n".join(events) or "(none yet)",
        board_section=board_section,
    )
    if game.rules.multiplier_min is not None:
        prompt += (f'For play, include both "stake" and integer "x" from '
                   f'{game.rules.multiplier_min} to {game.rules.multiplier_max}, for example '
                   '{"action": "play", "stake": 1, "x": 2}.\n')
    return prompt
