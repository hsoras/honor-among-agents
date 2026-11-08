# Pooled gamble: board, transfers, and individual play

**Stage: Explore.** This is a small descriptive comparison intended to surface behaviors and useful follow-up questions. There is no preregistered directional hypothesis: the user explicitly declined to supply one. Do not retrofit a prediction after seeing results. Three runs per cell are exploratory, not enough to support a general claim.

**Priority:** Preparing this bounded comparison is a useful next step toward choosing a hackathon idea; the small grid can reveal whether the setup produces interpretable behaviors before investing in a larger study.

## Question

For homogeneous groups of LLM agents pursuing their own final-point score, how does adding a shared message board to a setting with transfers change play, transfers, individual outcomes, and group outcomes, compared with the same setting without a board?

## Conditions and scale

- **Board + transfers:** agents can post to a shared board, transfer points, play their one game, vote to end, or skip.
- **No board + transfers:** same actions, game, public action record, turn structure, and end rule, but no posts. Public actions remain available as indirect signals.
- Each episode contains a single model only (homogeneous group), with group size **N = 2, 4, or 8**. Each agent starts with 1 point and has an individual objective: maximize their own final points; other agents' points do not count toward that objective.
- Three runs per model × condition × size. The current run configuration names two model IDs, for 36 planned episodes total, paired by size/rep seed across conditions.
- Up to 8 turns per agent; a turn is one action. See `DESIGN.md` and `prompts/` for the implemented mechanics and exact instructions.

## Outcomes to inspect

Report episode-level results and descriptive cell summaries. Keep **individual** and **collective** outcomes distinct:

- Group final-point **total** and **average per agent**, plus gain over the starting total. These are descriptive consequences of individually motivated actions, not the agents' stated objective.
- Distribution of individual final points; number of agents ending at zero (“ruined”); largest holder's share of group points as a simple **risk-concentration** measure. Interpret concentration only when the total is nonzero.
- Play count, stakes (including stakes ≥2), wins, transfers and transferred volume, board posts, end votes, invalid actions, turns, completion/truncation/failure, calls, and cost.
- Whole-point values are provisional simulation units, not calibrated money or utility. Preserve exact integer outcomes; show means with the underlying three episode values so averaging does not conceal discrete outcomes.
- End votes are actions, not a direct measure of agreement or welfare. Record their timing/count and whether the episode completed under the implemented rule.

## Reading the comparison

The shared seed pairs board and no-board episodes on the turn-order shuffle and game draws for the same model, N, and replicate. This helps make the condition contrast easier to inspect; it does not control model sampling randomness, which is not guaranteed reproducible. Model and condition should be summarized separately.

Important controls and caveats:

1. Transfers and the public record of actions exist in both conditions. The contrast estimates the added effect of explicit posts in this harness, not communication versus no communication.
2. The no-board condition still permits signaling through transfers, plays, votes, and skips. Conversely, board posts do not enforce commitments or truthful statements.
3. Models are homogeneous within an episode, not mixed. A model difference is not a causal effect of model family: only two selected models are represented.
4. Sizes change both social scale and turn budget (8 turns per agent), so size comparisons also change the maximum number of actions. Three replicates per cell leave substantial sampling uncertainty.
5. Individual-score instructions can conflict with collective total. Group total/average must not be described as the agents' objective or as evidence of collective preference.
6. The game payoff is stochastic and the number of plays may differ by condition. A larger group total may reflect game outcomes, concentration in a successful player, or more play; inspect all three rather than inferring cooperation from totals alone.
7. End votes can be delayed or cleared by subsequent actions under the code's rules. Truncated episodes are reported separately; do not silently treat them as completed episodes.
8. API routing can select different inference providers over time. Provider, actual billed usage/cost, model ID, prompt hashes, and run configuration should be retained with each run. The public price check below is a dated snapshot, not a guaranteed charge.

These data can describe what this harness elicited. They cannot establish real-world swarm behavior, stable model dispositions, or a general effect of message boards.

## Current model IDs and public pricing check (2026-11-07)

The current OpenRouter catalog exposes these IDs:

| Model | OpenRouter ID | Public model-list price per 1M tokens (input / output) |
|---|---|---:|
| DeepSeek V4.1 Flash 1017 | `deepseek/deepseek-v4.1-flash-1017` | $0.006 / $0.50 |
| Z.ai GLM 5.3 Flash | `z-ai/glm-5.3-flash` | $0.0335 / $0.083 |

OpenRouter's current provider pages list cheapest visible standard endpoint rates of **Relace, $0.006/$0.50** for DeepSeek and **Relace, $0.0379/$0.0798** for GLM, per 1M input/output tokens. These page figures do not fully agree with the catalog's GLM model-level price, and DeepSeek's page headline also uses a different model-level price ($0.006/$0.50) than some provider rows. Treat these as observations, not a universal quote; pinning a provider and checking at run time is necessary for exact pricing. A public API fetch of the endpoint detail was attempted but the local network could not resolve `openrouter.ai`; provider-specific data was therefore verified from OpenRouter's public webpages, not by a successful direct API request. No paid model calls were made for this check.

Sources: [OpenRouter public model catalog API](https://openrouter.ai/api/v1/models) (IDs and model-list prices), [DeepSeek V4.1 Flash 1017 providers](https://openrouter.ai/deepseek/deepseek-v4.1-flash-1017/providers), [GLM 5.3 Flash providers](https://openrouter.ai/z-ai/glm-5.3-flash/providers). Checked 2026-11-07. Prices may change.

## Run status

Harness exists and is described in `DESIGN.md`; no experiment run is logged here yet. This README does not authorize or initiate paid calls. The prior spend ledger records $0.0031 from an earlier accidental live check; that is not a result for this comparison. See `LOG.md` for run history and planned grid status.

## Reproduction entry points

```sh
uv run experiments/pooled-gamble/run.py --mock --pilot --out <dir>  # offline wiring check only
uv run experiments/pooled-gamble/run.py --pilot --live --out <dir>  # paid live pilot
uv run experiments/pooled-gamble/run.py --live --out <dir>          # paid full grid
```

Mock results are not model evidence. Live runs use OpenRouter. The existing harness requires explicit `--live` and enforces its configured budgets; check the current provider routing and price assumptions before any run. Each results directory records configuration, prompt hashes, episode transcripts, and metrics. Keep existing results and the spend ledger; never overwrite them.

## Second setup: agent-chosen multiplier

`run_multiplier.py` is a separate game variant. Each agent still chooses a whole-point stake `s`, and now also chooses an integer multiplier `x` from the configured inclusive bounds (default **2–10**). For each play, the agent receives `x*s` points with probability `1/x`, or receives zero with probability `1 - 1/x`; the stake is always removed first. Thus a win nets `(x-1)*s` points and a loss nets `-s`. Each agent may play once. The expected net change is zero for every allowed `x` and stake, before considering any value the agent assigns to risk.

The selected multiplier is required in the play JSON as `"x"`, validated against the bounds, recorded in the game event and public action history, and summarized as `multiplier_choices` and `mean_multiplier` per episode. The original `run.py` keeps its existing stake-dependent game. Variant run folders have a `multiplier-x<min>-<max>` suffix to keep them distinct from original runs; the shared budget ledger and explicit live-call guard still apply.

```sh
uv run experiments/pooled-gamble/run_multiplier.py --mock --pilot              # offline only
uv run experiments/pooled-gamble/run_multiplier.py --pilot --live              # paid live pilot
uv run experiments/pooled-gamble/run_multiplier.py --live --x-min 2 --x-max 10 # paid full grid
```

Bounds can be changed with `--x-min` and `--x-max`; they must be integers satisfying `2 <= x-min <= x-max`. The live pilot and grid have not been launched for this variant.

## Data tracking, output cap, and figures (2026-11-08)

- **Output cap.** The default per-call `max_tokens` is now **16384** (was 8192). Reasoning tokens count against it. Override per invocation with `--max-tokens N` (256 to 65536). Each episode records its cap, token totals, reasoning tokens, and the number of replies cut off by the cap (`finish_reason == "length"`).
- **Append-only records.** New run folders contain `records.jsonl`. It logs `run_started`, `episode_started`, `episode_finished` (with the episode summary), `episode_crashed`, `episode_not_started`, and `run_finished`. Each line is fsynced as it happens. An episode with a start but no finish record was interrupted, and the report says so.
- **Stopped and crashed runs.** Ctrl-C or an unexpected error halts new calls. Calls already reserved finish and settle. Every planned episode gets exactly one outcome (finished, crashed, or not started). `metrics.json` is written with `run.complete` set accordingly. An episode bug is recorded as `crashed` and the rest of the grid continues.
- **Shared budget.** The ledger (`results/spend_ledger.json`) is re-read and updated under an exclusive file lock on every reservation and settlement, so concurrent processes cannot overwrite each other's spend. Caps are unchanged: $0.10 per episode, $5 total, and the call cap. If the ledger cannot be read or written, the budget fails closed. A settlement that cannot be written halts the budget after the paid call, keeping the worst-case charge.

```sh
uv run experiments/pooled-gamble/summarize.py                       # REPORT.md (aggregates only, committed)
uv run --with matplotlib experiments/pooled-gamble/plots.py         # figures/*.png (committed)
```

`summarize.py` writes `results/episode_table.md`, which holds the exact per-episode values and is git-ignored. Completed episodes are the only ones averaged. Truncated, aborted-by-budget, error, crashed, and unfinished episodes appear in their own columns and in an "unfinished" table. Duplicate attempts are listed as superseded. Pilot, mock, and multiplier-variant folders are listed and excluded.

Figures show completed episodes only. Each panel prints completed/planned counts per cell. Figure 4's histogram uses only runs at the largest per-call cap present. Blue and orange are the validated two-series pair from the dataviz palette (`scripts/validate_palette.js`, both modes pass).

Raw run data (`results/`, including per-run `config.json` and `metrics.json`) is git-ignored. Only code, `REPORT.md`, `figures/`, and these docs are committed.
