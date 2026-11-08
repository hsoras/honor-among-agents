# Spec v2: rounds, multi-action tool-call turns, persistent agents

Status: FINAL for the MVP (2026-11-08). Build exactly this. If something is not covered here, ask; do not guess.
v1 (`engine.py`, `episode.py`, `run.py`, `render.py`, `prompts-neutral/`, `DESIGN.md`) must keep working
unchanged: all existing tests (`python3 -m pytest -q tests`) must still pass. v2 is a separate experiment
whose results are never mixed with v1.

## 1. Game (unchanged from v1)
- N homogeneous agents (one model per episode), ids `agent_1` .. `agent_N`. Each starts with 1 point. Points are ints.
- **Play:** once per agent per episode. Stake s, 1 <= s <= balance. Stake removed; with probability s/(s+1)
  the agent receives 2s (net +s), else nothing (net -s). One RNG draw per valid play from
  `random.Random(f"{seed}:games")`.
- **Transfer:** 1..balance whole points to another agent. Immediate, irreversible, unconditional.
- Invariant (checked after every episode): total == N + sum of play nets; balances non-negative ints; nobody played twice.

## 2. Rounds and turns
- **Order:** fixed, agent_1 -> agent_N, every round. No shuffling.
- **Round cap:** 2 x N rounds (8 at N=4, 16 at N=8). Reaching it without ending = status `truncated`.
- **A turn** is a tool-call loop with that agent's model. In one turn an agent may:
  - `post` at most **once per turn** (board condition only), whatever its balance;
  - `transfer` any number of times while it has points;
  - `play` once per episode (if it holds points and has not played);
  - `vote_end` (only if it holds >= 1 point). **vote_end ends the turn immediately.**
  - `end_turn` ends the turn.
- **The turn ends** on: `end_turn`; `vote_end`; an assistant reply containing no tool calls; or **12 actions**
  (every tool call counts, including invalid ones).
- **Invalid action:** state unchanged; the tool result is `ERROR: <reason>`; it counts toward the 12.
- **Parallel tool calls** in one assistant message: execute them in order. Every tool_call id MUST get a
  tool-result message (API requirement). Calls after the turn has ended get the result
  `NOT EXECUTED: your turn has ended.` and do not count as actions.
- **Tools offered depend on state** (rebuilt each call):
  - holds >= 1 point: `transfer`, `play` (only if not yet played), `vote_end`, `end_turn`, plus `post` in board.
  - 0 points, board: `post`, `end_turn` only.
  - 0 points, no board: the agent is **skipped entirely** (no model call). Record a `skip` event.
- **End votes are round-scoped.** All votes are cleared at the start of each round. A vote stands for the rest of
  its round even if the voter later receives points. **At the end of each round** the episode ends (status
  `completed`) if every agent holding >= 1 point at that moment voted in this round.
- If every agent has 0 points, the episode ends `completed` immediately (no further calls).

## 3. What each agent sees
- **Persistent memory:** each agent has its own conversation (system prompt + all its messages) for the whole
  episode. Append the assistant message to history **exactly as returned**, including `reasoning_details`
  (and `reasoning`) when present, plus `tool_calls`. Never trim.
- **Turn-start user message** (appended at the start of each of its turns) contains, in this order:
  1. `Round r of R. It is your turn, agent_k.`
  2. Balance table for every agent: points; played yes/no; voted to end this round yes/no.
  3. `Actions since your last turn:` every public event by OTHER agents since this agent's previous turn ended
     (transfers, plays with stake and WON/LOST and amount received, end votes, skips), each tagged with round.
     On its first turn: all events so far. `(none)` if empty.
  4. Board condition only: `New board posts since your last turn:` posts by OTHER agents since then, tagged
     `[round r] agent_j: text`. `(none)` if empty.
  5. One line listing the tools available right now.
- **Tool results** report the outcome plus the agent's new balance, e.g.
  `OK: transferred 1 to agent_2. Your balance: 0.`, `OK: played stake 4: WON, received 8. Your balance: 8.`,
  `OK: posted.`, `ERROR: transfer of 3 exceeds your 1 point(s).`
- No tool to read the full record or board (history already persists).

## 4. Prompts (`prompts-v2/system_board.md`, `prompts-v2/system_noboard.md`)
Rewrite `prompts-neutral/system_board.md` / `system_noboard.md` for v2. Keep verbatim in spirit: the goal ("maximize
your own score = points you hold at the end; other agents' points are not your score"), the play rule with the
same two illustrations, and the full "How transfers work" paragraph (immediate, recipient may stake them, nothing
enforces agreements, points never move back on their own). Replace the turn/vote paragraphs with section 2's
rules (fixed order, rounds, round cap, multi-action turns, one post per turn, 12-action cap, round-scoped votes,
vote_end ends your turn, end-of-round ending rule). Say actions are taken by calling tools. **No pooling advice,
no hints about strategy.** No-board version omits everything about posts/board.

## 5. Tools (OpenAI function-calling format via OpenRouter)
- `post(text: string)` - max 280 chars, non-empty.
- `transfer(to: string, amount: integer)`
- `play(stake: integer)`
- `vote_end()`
- `end_turn()`
Validate types strictly (ints not floats/bools; unknown agent; self-transfer; amount > balance; etc.).
Malformed tool-call arguments (bad JSON) -> `ERROR`, counts as an action.

## 6. Model calls, budget, errors
- Reuse `llm.py`'s `Budget` (shared file-locked ledger at `results/spend_ledger.json`, worst-case reservation
  before each call, settle to reported cost). Add what is needed for message-list + tools calls (e.g.
  `OpenRouterClient.chat(...)` and `Budget.call_chat(...)`) **without changing v1 behaviour**. Worst-case input
  estimate = UTF-8 bytes of json.dumps(messages + tools) + overhead.
- Request: `model`, `messages`, `tools`, `max_tokens` (16384), `usage: {include: true}`,
  `reasoning: {enabled: true}`, **no temperature**. Provider pinning: reuse `pin_live_routes`/
  `choose_cheapest_endpoint` with `need_temperature=False` and required params `tools` and `reasoning`.
- Retries: retry only HTTP 429 and 502/503 (not billed), up to 3 times with backoff (2s, 8s, 30s). Any other
  error -> episode status `error` (keep worst-case charge, as v1).
- Caps: `--max-usd-episode` default **10**, `--max-usd-total` default **150**, `--max-calls` default **50000**.
  Hitting a cap -> status `aborted_budget` (episode kept, never silently dropped).

## 7. Runner `run_v2.py`
- Requires `--live` or `--mock` (refuse otherwise, like v1). Loads `.env` from the repo root
  (`swarm-gambling/.env`, which holds `OPENROUTER_API_KEY`).
- Flags: `--models a,b` (OpenRouter slugs), `--ns 4` (comma list), `--board-reps 10`, `--noboard-reps 3`,
  `--max-tokens`, `--max-usd-episode`, `--max-usd-total`, `--max-calls`, `--workers` (default 8), `--pilot`
  (forces 1 board rep + 1 noboard rep), `--mock`, `--live`.
- **Seeds:** `seed = 20261108 + 1000*N + rep`. Board rep r and no-board rep r share the seed (paired draws).
- Output root **`results-v2/`** (not `results/`), folder `results-v2/<YYYYmmdd-HHMMSS>[-pilot][-mock]/` with
  `config.json` (config, routes, prompt sha256s, git commit/dirty, argv), `records.jsonl` (reuse `records.py`
  RunRecords: run_started / episode_started / episode_finished / episode_crashed / episode_not_started /
  run_finished), `metrics.json`, and `episodes/<model_slug>__<board|noboard>__n<N>__r<rep>/`:
  - `transcript.jsonl`: one line per model call: round, actor, step (call index within turn), the messages
    appended since the previous call for that agent (user / tool results), the assistant message (content,
    tool_calls, reasoning text if any), applied results, prompt/completion/reasoning tokens, cost_usd,
    finish_reason, provider.
  - `episode.json`: spec, rules, summary, events, board, and every agent's full final conversation.
- Episodes run concurrently (ThreadPoolExecutor), like v1. Ctrl-C: no new calls, every episode gets an outcome.

## 8. Per-episode summary (episode.json `summary`, also in metrics.json)
model, condition, n, rep, seed, status, error, rounds, max_rounds, final_balances, total_final, total_start,
net_game_points, plays, wins, max_stake, full_pool (max_stake == N), transfers, transfer_volume, posts,
vote_ends, invalid_actions, actions_per_turn (mean), calls, cost_usd, prompt/completion/reasoning tokens,
length_limited_replies, max_share (largest balance / total, 0 if total 0), ruined_agents.

## 9. Mock client and tests (no network)
- `MockClient.chat`: seeded random policy that emits valid and occasionally invalid tool calls (including
  occasional multiple tool calls in one message and occasional no-tool-call text replies).
- Tests (pytest, in `tests/test_v2_*.py`), at minimum:
  - play math/RNG pairing: same seed -> same draws board vs no-board given the same plays.
  - one post per turn; 12-action cap; vote_end ends turn; end_turn ends turn; no-tool-call reply ends turn.
  - every tool_call id answered, including NOT EXECUTED ones after the turn ended.
  - round-scoped votes: cleared each round; episode ends only at end of a round where all holders voted;
    receiving points after voting does not clear the vote; 0-point agents need not vote.
  - all-zero balances end the episode immediately.
  - tools offered match state (0 points board -> post/end_turn; 0 points no-board -> skipped, no call).
  - turn-start message shows only OTHER agents' events/posts since this agent's last turn; first turn shows all.
  - history persists across turns and keeps `reasoning_details` verbatim.
  - invariants hold after mock episodes; round cap -> `truncated`.
  - budget: reservation/settle works for chat calls; cap -> `aborted_budget`.
  - an end-to-end `--mock` run of N=4 board + no-board writes all files with the layout above.
- All v1 tests still pass.

## 10. First real grid (NOT part of the build; run only when the parent says so)
Models: `openai/gpt-6.1-sol`, `anthropic/claude-opus-5.5`. N = 4. Board 10 reps, no-board 3 reps.
Cheap live validation first (parent runs it): one pilot with a cheap model (DeepSeek Flash or Luna).
