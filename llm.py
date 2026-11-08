"""Model access: OpenRouter client, offline mock policy, and the hard usage cap.

Nothing here runs unless run.py is invoked. Tests use MockClient only.

Budget design (thread-safe, so episodes can run concurrently):
- One shared Budget holds the total-ledger state and a lock.
- Each episode gets its own EpisodeMeter (per-episode dollars and call count).
- Every call RESERVES its worst case under the lock before the request is sent, then SETTLES
  to the actual reported cost (or keeps the worst case when the outcome is ambiguous).
  In-flight reservations therefore count against both caps, so concurrent calls cannot overspend.
- No retries. Any error after the request may have been billed, so it keeps the worst-case charge.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import random
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@contextlib.contextmanager
def _file_lock(path: Path | None):
    """Exclusive inter-process lock on <ledger>.lock. A no-op when there is no ledger."""
    if path is None:
        yield
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_name(path.name + ".lock"), "a") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


class APIError(RuntimeError):
    """A model call failed. The call's worst case stays charged; the episode is recorded as 'error'."""


class BudgetExceeded(RuntimeError):
    """The call or dollar cap was reached. The grid stops."""


@dataclass(frozen=True)
class Completion:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float | None = None  # None when the provider reports no cost
    finish_reason: str | None = None
    provider: str | None = None  # the provider that actually served the call, as reported
    reasoning_tokens: int = 0  # part of completion_tokens, as reported by the provider (0 if not reported)


# Input token estimate: UTF-8 bytes of system + user text, plus fixed template overhead.
# Every token is at least one byte, so bytes >= tokens for byte-level tokenizers: a conservative
# upper bound. The overhead covers role/chat-template tokens and JSON framing.
TOKEN_OVERHEAD = 512


def estimate_input_tokens(system: str, user: str) -> int:
    return len(system.encode("utf-8")) + len(user.encode("utf-8")) + TOKEN_OVERHEAD


class EpisodeMeter:
    """Per-episode counters. Mutated only under the owning Budget's lock."""

    def __init__(self) -> None:
        self.calls = 0
        self.usd = 0.0
        self.unknown_cost_calls = 0


class Budget:
    """Hard caps, enforced BEFORE each request with a worst-case reservation.

    A call is refused unless the call cap holds, (episode spend + worst case) <= per-episode cap,
    and (total ledger spend incl. in-flight reservations + worst case) <= total cap.
    Worst case = estimated input tokens (UTF-8 bytes + overhead) at the input price + max_tokens
    at the output price. The reservation is written to the ledger before the request, so a crash
    mid-call still keeps the spend. Settling replaces the reservation with the actual cost.

    The ledger is shared by every invocation (and by concurrent processes). Every reservation and
    settlement re-reads the ledger file and writes the new total while holding an exclusive file
    lock, so no process can overwrite another's spend. If the ledger cannot be read or written,
    the budget fails closed: no new call is made. A settlement that cannot be written halts the
    budget after the paid call, keeping the worst-case charge.
    """

    def __init__(self, max_calls: int, max_usd_total: float, max_usd_episode: float,
                 prices: dict[str, tuple[float, float]], ledger_path: Path | None = None) -> None:
        self.max_calls = max_calls
        self.max_usd_total = max_usd_total
        self.max_usd_episode = max_usd_episode
        self.prices = prices  # model -> (USD per input token, USD per output token)
        self.ledger_path = ledger_path
        self.calls = 0  # calls made by this invocation (reserved, including ones that then failed)
        self.unknown_cost_calls = 0
        self.failed_calls = 0
        self.halted: str | None = None  # set to a reason: no new call is made after this
        self.lock = threading.Lock()
        self._ledger_seen = False
        self.charged_usd = 0.0  # ledger total incl. in-flight reservations, as of the last write
        self.ledger_calls = 0  # ledger total of calls reserved, all invocations
        with self.lock, _file_lock(self.ledger_path):
            self.charged_usd, self.ledger_calls = self._read_totals()

    def _read_totals(self) -> tuple[float, int]:
        """Caller holds the file lock (when there is a ledger). Missing ledger at start is zero."""
        if self.ledger_path is None:
            return self.charged_usd, self.ledger_calls
        if not self.ledger_path.exists():
            if self._ledger_seen:
                raise BudgetExceeded("spend ledger disappeared during the run; refusing to continue")
            return 0.0, 0
        data = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        self._ledger_seen = True
        return float(data["charged_usd"]), int(data.get("calls", 0))

    def _write_totals(self, usd: float, calls: int) -> None:
        """Atomic replace with a per-process, per-thread temp name. Caller holds the file lock."""
        self.charged_usd, self.ledger_calls = usd, calls
        if self.ledger_path is None:
            return
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.ledger_path.with_name(f"{self.ledger_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps({"charged_usd": round(usd, 8), "calls": calls}, indent=2), encoding="utf-8")
        os.replace(tmp, self.ledger_path)
        self._ledger_seen = True

    def halt(self, reason: str) -> None:
        """Stop new calls. Calls already reserved finish and settle normally."""
        with self.lock:
            if self.halted is None:
                self.halted = reason

    def meter(self) -> EpisodeMeter:
        return EpisodeMeter()

    def worst_case_usd(self, model: str, system: str, user: str, max_tokens: int) -> float:
        if model not in self.prices:
            raise BudgetExceeded(f"no price for {model!r}; refusing to call")
        price_in, price_out = self.prices[model]
        return estimate_input_tokens(system, user) * price_in + max_tokens * price_out

    def call(self, client, *, model: str, system: str, user: str, meta: dict,
             temperature: float, max_tokens: int, meter: EpisodeMeter) -> Completion:
        worst = self.worst_case_usd(model, system, user, max_tokens)
        # Reserve: check every cap and charge the worst case in one critical section (thread and file lock).
        with self.lock:
            if self.halted is not None:
                raise BudgetExceeded(f"halted: {self.halted}")
            if meter.usd + worst > self.max_usd_episode:
                raise BudgetExceeded(f"episode dollar cap ${self.max_usd_episode:.2f} would be exceeded")
            with _file_lock(self.ledger_path):
                usd, calls = self._read_totals()
                if calls >= self.max_calls:
                    raise BudgetExceeded(f"call cap reached ({self.max_calls})")
                if usd + worst > self.max_usd_total:
                    raise BudgetExceeded(f"total dollar cap ${self.max_usd_total:.2f} would be exceeded")
                self._write_totals(usd + worst, calls + 1)  # written before the request is sent
            self.calls += 1
            meter.calls += 1
            meter.usd += worst
        # Request outside the lock so episodes proceed concurrently.
        try:
            comp = client.complete(model=model, system=system, user=user, meta=meta,
                                   temperature=temperature, max_tokens=max_tokens)
        except Exception:
            # Outcome ambiguous (may have been billed): keep the worst-case reservation. No retry.
            with self.lock:
                self.failed_calls += 1
                self.unknown_cost_calls += 1
                meter.unknown_cost_calls += 1
            raise
        with self.lock:
            if comp.cost_usd is None:
                self.unknown_cost_calls += 1
                meter.unknown_cost_calls += 1
                actual = worst
            else:
                actual = comp.cost_usd
            # Settle: replace the reservation with the actual cost. If the ledger cannot be
            # written, the worst case stays charged in memory and the budget halts (fail closed).
            try:
                with _file_lock(self.ledger_path):
                    usd, calls = self._read_totals()
                    self._write_totals(usd + actual - worst, calls)
            except (OSError, ValueError, KeyError, BudgetExceeded) as e:
                # charged_usd keeps the reservation (the worst case), which is conservative.
                self.halted = self.halted or f"spend ledger could not be settled after a call ({e})"
            meter.usd += actual - worst
        return comp


class OpenRouterClient:
    URL = "https://openrouter.ai/api/v1/chat/completions"
    ENDPOINTS_URL = "https://openrouter.ai/api/v1/models/{model}/endpoints"

    def __init__(self, api_key: str | None = None, timeout: float = 120.0,
                 provider_order: list[str] | None = None, reasoning: dict | None = None) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("OPENROUTER_API_KEY", "")
        if not self.api_key:
            raise APIError("OPENROUTER_API_KEY is not set (add it to the workspace .env)")
        self.timeout = timeout
        # Pin routing to these providers, with no fallback to others.
        self.provider_order = provider_order
        self.reasoning = reasoning  # OpenRouter reasoning control; None leaves the provider default

    def complete(self, *, model: str, system: str, user: str, meta: dict,
                 temperature: float, max_tokens: int) -> Completion:
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": max_tokens,
            "usage": {"include": True},  # ask OpenRouter to report the cost of this call
        }
        if temperature is not None:  # None: model rejects the parameter (e.g. GPT-6.1 Sol)
            body["temperature"] = temperature
        if self.reasoning is not None:
            body["reasoning"] = self.reasoning
        if self.provider_order:
            body["provider"] = {"order": self.provider_order, "allow_fallbacks": False}
        data = self._post(body)
        choice = (data.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content") or ""
        usage = data.get("usage") or {}
        cost = usage.get("cost")
        details = usage.get("completion_tokens_details") or {}
        return Completion(
            text=content,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            cost_usd=float(cost) if cost is not None else None,
            finish_reason=choice.get("finish_reason"),
            provider=data.get("provider"),
            reasoning_tokens=int(details.get("reasoning_tokens") or 0),
        )

    def _post(self, body: dict) -> dict:
        """One attempt only. Any HTTP or network error is raised as APIError with no retry."""
        payload = json.dumps(body).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Title": "pooled-gamble-experiment",
        }
        req = urllib.request.Request(self.URL, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise APIError(f"HTTP {e.code}: {e.read()[:300].decode('utf-8', 'replace')}") from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            raise APIError(f"network or parse error: {e}") from None


def fetch_endpoints(model: str, timeout: float = 60.0) -> list[dict]:
    """Live endpoint list for a model, from OpenRouter's public endpoints API."""
    url = OpenRouterClient.ENDPOINTS_URL.format(model=model)
    with urllib.request.urlopen(urllib.request.Request(url), timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))["data"]
    return data["endpoints"]


def choose_cheapest_endpoint(endpoints: list[dict], w_in: int = 3000, w_out: int = 200,
                             required_params: list[str] | tuple = (), need_temperature: bool = True) -> dict:
    """Cheapest live endpoint by blended cost per call (w_in input tokens, w_out output tokens).

    Eligible: status 0 (live) and supports temperature and max_tokens. Returns the chosen endpoint
    with prices per token and the OpenRouter provider slug (the tag prefix, e.g. 'relace/fp4' -> 'relace').
    """
    best = None
    for e in endpoints:
        if e.get("status") != 0:
            continue
        params = e.get("supported_parameters") or []
        if any(p not in params for p in ("max_tokens", *(("temperature",) if need_temperature else ()), *required_params)):
            continue
        p_in = float(e["pricing"]["prompt"])
        p_out = float(e["pricing"]["completion"])
        blended = w_in * p_in + w_out * p_out
        key = (blended, e["provider_name"])
        if best is None or key < best[0]:
            best = (key, e, p_in, p_out)
    if best is None:
        raise APIError("no live endpoint supports temperature and max_tokens")
    _, e, p_in, p_out = best
    return {
        "provider_name": e["provider_name"],
        "provider_slug": e["tag"].split("/")[0],
        "tag": e["tag"],
        "quantization": e.get("quantization"),
        "price_usd_per_token": (p_in, p_out),
        "blended_usd_per_call_estimate": w_in * p_in + w_out * p_out,
        "weights": {"input_tokens": w_in, "output_tokens": w_out},
    }


class MockClient:
    """Offline stand-in for wiring tests and `--mock` runs. A seeded random policy that always
    emits a valid action. It is not a model, and its results mean nothing about models."""

    def complete(self, *, model: str, system: str, user: str, meta: dict,
                 temperature: float, max_tokens: int) -> Completion:
        rng = random.Random(f"{meta['seed']}:{meta['actor']}:{meta['turn']}")
        bal = meta["balance"]
        options = ["skip", "vote_end"]
        if bal >= 1 and not meta["played"]:
            options += ["play", "play"]
        if bal >= 1 and meta["others"]:
            options.append("transfer")
        if meta["board"]:
            options.append("post")
        choice = rng.choice(options)
        if choice == "play":
            obj = {"action": "play", "stake": rng.randint(1, bal)}
        elif choice == "transfer":
            obj = {"action": "transfer", "to": rng.choice(meta["others"]), "amount": rng.randint(1, bal)}
        elif choice == "post":
            obj = {"action": "post", "text": f"mock note from {meta['actor']} on turn {meta['turn']}"}
        else:
            obj = {"action": choice}
        return Completion(text=json.dumps(obj), prompt_tokens=len(user) // 4,
                          completion_tokens=len(json.dumps(obj)) // 4, cost_usd=0.0, finish_reason="stop",
                          provider="mock")
