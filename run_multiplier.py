"""Run the agent-chosen multiplier variant without changing the original game.

Examples:
    uv run experiments/pooled-gamble/run_multiplier.py --mock --pilot
    uv run experiments/pooled-gamble/run_multiplier.py --pilot --live
    uv run experiments/pooled-gamble/run_multiplier.py --live --x-min 2 --x-max 10

The x bounds default to 2..10. Live model calls still require --live.
"""
from __future__ import annotations

import sys
from datetime import datetime as _datetime


def main() -> None:
    args = list(sys.argv[1:])
    bounds = {"--x-min": 2, "--x-max": 10}
    for flag in bounds:
        if flag in args:
            pos = args.index(flag)
            try:
                bounds[flag] = int(args[pos + 1])
            except (IndexError, ValueError):
                raise SystemExit(f"{flag} needs an integer")
            del args[pos:pos + 2]
    x_min, x_max = bounds["--x-min"], bounds["--x-max"]
    if x_min < 2 or x_max < x_min:
        raise SystemExit("multiplier bounds must satisfy 2 <= x-min <= x-max")
    max_tokens = 16384  # per-call output cap (reasoning counts toward it); the user approved 16384
    if "--max-tokens" in args:
        pos = args.index("--max-tokens")
        try:
            max_tokens = int(args[pos + 1])
        except (IndexError, ValueError):
            raise SystemExit("--max-tokens needs an integer")
        del args[pos:pos + 2]
    if max_tokens < 1:
        raise SystemExit("--max-tokens must be positive")

    from pathlib import Path
    HERE = Path(__file__).resolve().parent
    sys.path.insert(0, str(HERE))
    import episode
    import run
    from engine import Rules as BaseRules

    def multiplier_rules(*args, **kwargs):
        kwargs["multiplier_min"] = x_min
        kwargs["multiplier_max"] = x_max
        return BaseRules(*args, **kwargs)

    episode.Rules = multiplier_rules
    old_summarise = episode.summarise

    def summarise_multiplier(*args, **kwargs):
        result = old_summarise(*args, **kwargs)
        plays = [e for e in args[1].events if e["action"] == "play" and "x" in e]
        result["multiplier_choices"] = [e["x"] for e in plays]
        result["mean_multiplier"] = sum(e["x"] for e in plays) / len(plays) if plays else None
        return result

    episode.summarise = summarise_multiplier
    run.CONFIG["multiplier_min"] = x_min
    run.CONFIG["multiplier_max"] = x_max
    run.CONFIG["max_tokens"] = max_tokens
    # The call cap counts every call in the ledger, including earlier invocations, so the pilot's
    # own 40-call override would refuse every call. Keep the ledger-wide cap for pilots too.
    run.PILOT_OVERRIDES["max_calls"] = run.CONFIG["max_calls"]

    # Make collisions with original-run folders impossible, even if started in the same second.
    class VariantClock:
        @staticmethod
        def now():
            return VariantStamp(_datetime.now())

    class VariantStamp:
        def __init__(self, dt):
            self.dt = dt

        def strftime(self, fmt):
            return self.dt.strftime(fmt) + f"-multiplier-x{x_min}-{x_max}"

    run.datetime = VariantClock
    sys.argv = [sys.argv[0], *args]
    run.main()


if __name__ == "__main__":
    main()
