# Pooled gamble: design and assumptions

Status: harness built and tested offline. No live model runs yet. Pilot and grid need user sign-off (see "Before any live run").

**Stage:** explore. Three runs per cell is too few for claims. The output is descriptive, and it can only rule out large effects.

## Question

Does a shared message board change how a homogeneous group of LLM agents pools points, gambles and ends the episode, compared with the same group that can only transfer points and act publicly?

Agents maximise their own final points, so the collective total is an outcome of individual choices rather than the target. The idea's "will agents take riskier actions to maximise their collective score" becomes "what total do they reach, and by which actions".

## Hypotheses

- **H1 (user's hypothesis):** the board lets agents coordinate pooling. Board episodes end with a higher total, and more and larger stakes, than no-board episodes.
- **H2 (boring alternative):** the board adds nothing. Transfers and public actions already carry the same behaviour, and any gap is noise.
- **H3 (alternative):** talk without closure. The board raises truncation or lowers completion, and the total does not rise.
- **Not yet thought of:** most probability sits on something else. Candidates: models skip or stake 1 forever, which keeps the total near N in both conditions.

**Distinguishing prediction:** H1 predicts a higher mean total and more stakes of 2 or more in board episodes, with transfers into the eventual staker. H2 predicts no difference in totals or stake profile. H3 predicts a higher truncation rate under the board.

**Falsification:** H1 is dropped if the paired board-minus-noboard difference in mean total is near zero across all N and both models, and the stake and transfer profile does not differ. Three reps per cell cannot show small differences, so "no difference" here means "no large difference".

## Derived facts (not measured)

- A stake `s` has expected net `s(s-1)/(s+1)`. Stake 1 is a fair coin (EV 0). Every stake of 2 or more has positive EV, approaching `+s` as `s` grows.
- The points could pool into one agent, or chain through agents in turn order. The red-team reviews that analysed this have been removed from the repo. This harness does not test a principal or a policy, so a "client accounts" redesign is not implemented.

## Setup

| Item | Value |
|---|---|
| Models | `deepseek/deepseek-v4.1-flash-1017`, `z-ai/glm-5.3-flash` (dated slugs, not `-latest` aliases; prices read from the OpenRouter model list on 2026-11-07). One model per episode, so all agents in a group are the same model. |
| Conditions | `board` (post + transfer + play + vote_end + skip) vs `noboard` (transfer + play + vote_end + skip; no messages) |
| Group size | N = 2, 4, 8 |
| Reps | 3 per cell, so 36 episodes per model and 72 in total |
| Starting points | 1 each |
| Turn limit | 8 turns per agent (16, 32, 64 total) |
| Sampling | temperature 1.0; `max_tokens` 16384 by default (`--max-tokens` overrides it; reasoning counts against it; part of the cost reservation). Not seeded: providers do not guarantee it. |
| Caps | Hard, checked BEFORE each call. A call is refused unless spend so far plus its worst case stays under $0.10 for the episode and $5.00 across all invocations (ledger `results/spend_ledger.json`, pilots included). Worst case = input estimated at 2 chars/token at the model's input price, plus `max_tokens` at its output price. Missing provider cost is charged at worst case. Also 1,500 calls total. The ledger is re-read and updated under a file lock for each reservation and settlement, so concurrent processes share the caps; an unreadable or unwritable ledger stops new calls (fail closed). Prices: `CONFIG["prices_usd_per_mtok"]`, from OpenRouter's public list on 2026-11-07. |
| Seeds | `20261107 + 1000·N + rep`. Shared across model and condition, so comparisons are paired on turn order and game draws. |

Prompts are files in `prompts/`. Their SHA-256 hashes go in `config.json` for each run. The system prompt is identical for every agent in a condition. The per-turn prompt carries the whole public state, so there is no chat history.

## Assumptions

Everything below is my reading of the request and the idea. Items marked **(confirm)** are unresolved.

1. **Stake (confirm).** The idea says agents "input n points" and never says what `n` is. I let each agent choose any whole stake from 1 to its balance. The fixed-`n` reading is not implemented.
2. **Payout.** A win returns `2s` (net `+s`). A loss keeps nothing (net `-s`). Each agent plays once.
3. **Turn order.** A fixed round-robin order, shuffled once from the seed. Each agent gets one turn per round and may skip. Turns are numbered globally.
4. **End vote.** The episode stops when every agent holding at least one point has an active `vote_end`. If nobody holds points, the stop is immediate. Zero-point agents need not vote.
5. **Vote clearing (confirm).** An agent's end vote clears when that agent posts, transfers or plays, and when it receives points. Other agents' actions, skips and invalid replies do not clear it.
6. **Acting after playing or voting.** Allowed. This is the "freedom" reading of the request.
7. **Truncation.** Reaching the turn limit without the stop rule gives `status = truncated`. Truncated episodes are never counted as completed or successful. Their final state is still logged, and they are reported separately.
8. **Public information (confirm).** In both conditions, balances, transfers, plays (stake and outcome), end votes and skips are public. The board condition adds posts, which are visible to all. Invalid replies are private to their sender, who is told the reason on its next turn.
9. **Invalid replies.** Anything that does not parse or is not allowed uses the turn and changes no state. Points must be whole JSON integers. Booleans and floats are rejected.
10. **Individual objective.** The system prompt says each agent's score is its own points, and that others' points do not count.
11. **Homogeneous groups.** One model per episode. Mixed groups are not part of this build.

## Metrics

Per episode (`episode.json`, `metrics.json`):
- total and mean final points, and total gain over start
- number of plays, wins, stake total, and largest stake
- number of transfers and transfer volume; number of posts; end votes; invalid replies
- ruined agents (0 points) and the largest holder's share of the total
- turns used, calls, and cost

Per group (model × condition × N, completed episodes only): means of the above, plus truncated, failed and ruined counts.

## Validation

- `engine.Game.check_invariants()` runs at the end of every episode. It checks that the total equals `N·start + Σ net game points`, that balances are non-negative whole numbers, that each agent played at most once, and that the play log matches the net total. Any failure raises, and the run stops.
- Tests (`tests/`, run with `uv run python -m unittest discover -s experiments/pooled-gamble/tests`): payouts, validation, vote clearing, the stop rule, accounting, parsing, prompt rendering, round-robin fairness, determinism, truncation, invalid replies, budget caps, the OpenRouter client with mocked HTTP, and aggregation. The offline mock policy is also checked for validity and conservation across the grid.

## How to run

```
uv run experiments/pooled-gamble/run.py --mock --pilot --out <dir>  # offline wiring check, no model calls
uv run experiments/pooled-gamble/run.py --pilot --live              # LIVE pilot: 1 model, N=2, 1 rep, 8 turns max
uv run experiments/pooled-gamble/run.py --live                      # LIVE grid: 2 models × 2 conditions × 3 N × 3 reps
```

Live runs need `--live`, which refuses to start otherwise. The workspace `.env` holds a real `OPENROUTER_API_KEY`, so any run without `--mock` spends money. The mock client is a random policy, not a model, so its results mean nothing about models.

## Cost estimate (live)

- Per episode: at most 64 calls (N=8, 8 turns each). Worst case per call is `1024 × output price` plus a small input term, so under $0.04 per episode at listed prices. The $0.10 episode cap is therefore never reached by the reservation alone.
- Full grid: at most 1,344 calls. Worst case is about $0.45 at listed prices, which is under the $5 total cap. The total ledger also includes the $0.0031 already spent (see below).
- Already spent: an accidental live check made 6 real calls for $0.0031 before the `--live` guard existed. It is recorded in the ledger.
- Pilot: at most 16 calls, a few cents.

## Before any live run

- Workflow step 6 asks for a pre-registered prediction before each real run. Not done yet. I need your predicted direction and confidence (1–5) for H1 versus H2 before the pilot.
- Confirm the **(confirm)** assumptions above, especially the stake reading and public outcomes.
- The pilot is a real OpenRouter call. Approve it before I run it.
- Budget enforcement is pre-call and tested offline (`tests/test_episode.py::BudgetTests`). It has not been exercised against the live API.

## Files

- `engine.py`: rules, validation, payouts, invariants (pure).
- `render.py`: prompt rendering from engine state.
- `prompts/`: `system_board.md`, `system_noboard.md`, `turn.md`.
- `llm.py`: OpenRouter client, offline mock policy, budget caps.
- `episode.py`: one episode loop, transcript, episode summary.
- `metrics.py`: group aggregation (completed episodes only).
- `records.py`: append-only `records.jsonl` writer, and the loader that reads complete and interrupted run folders alike.
- `summarize.py`: `REPORT.md` (aggregates) and the git-ignored `results/episode_table.md`.
- `plots.py`: figures in `figures/` (run with `uv run --with matplotlib`).
- `run.py`: CLI and grid. Writes `results/<timestamp>/` with `config.json`, `metrics.json`, and `episodes/`.
- `tests/`: unit and integration tests.
