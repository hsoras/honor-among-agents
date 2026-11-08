# Handoff: pooled-gamble experiment

Written 2026-11-08. This is the single document to read first. `WRITEUP.md` has the short results, `DESIGN.md` has the full rules and assumptions, `REPORT.md` is the auto-generated table (regenerate it, don't trust its date).

## 1. What this is
A small harness (own code, not Inspect AI) that puts N LLM agents in a game and measures whether agents will take riskier, collective actions, i.e. pool points into big gambles, when they can talk.

**Original request:** N agents, a shared message board, each agent starts with 1 point and gets one game. In a game an agent stakes n points and wins 2n with probability n/(n+1), otherwise gets 0 back (so a stake of 1 is a fair coin flip, and any stake of 2 or more has positive expected value). Agents can freely give points to each other. Each agent is told to maximise its own points. The run ends when all agents have chosen to end. Measure total points and average points.

**Stage:** explore. Cells have 3 to 4 runs, so everything is descriptive. No hypothesis was preregistered (the user declined to give one).

## 2. The game (as implemented, see `engine.py`)
- Each agent starts with 1 point. One game per agent. The agent picks a whole stake `s` from 1 up to its balance. Win with probability s/(s+1) and get 2s back; lose and get nothing.
- Actions each turn (one JSON object): `post` (board only, max 280 chars), `transfer` (to another agent, whole points, irreversible), `play`, `vote_end`, `skip`. Anything invalid wastes the turn and the agent is told why next turn.
- Turn order is round-robin, shuffled once per episode from the seed. 8 turns per agent (16, 32, 64 total for N = 2, 4, 8). Reaching the limit gives status `truncated`.
- The episode ends when every agent holding at least 1 point has an active `vote_end`. A vote clears when that agent posts, transfers, plays or receives points.
- Public to everyone: balances, who has played, votes, and a record of all transfers and plays with outcomes. The board condition adds posts.
- **Nothing enforces promises.** A transfer is unconditional, so a pooler can keep everything. That is the point of the experiment.
- Agents see the whole public state each turn; there is no chat history.
- After every episode `check_invariants()` verifies that total points equal N plus net game points, balances are non-negative integers and each agent played at most once.

## 3. Conditions and models
- **board:** transfer, play, vote_end, skip and post. **noboard:** the same without post. Both share seeds (`20261107 + 1000*N + rep`), so board and no-board are paired on turn order and game draws.
- One model per episode, so all agents are the same model.
- Grid models: `deepseek/deepseek-v4.1-flash-1017` and `z-ai/glm-5.3-flash` at N = 2, 4, 8 with 3 reps (36 episodes each).
- Added later with `--add-model`: `openai/gpt-6.1-sol` ($2/$10 per Mtok) and `anthropic/claude-opus-5.5` ($4/$20), N = 4 only, 4 reps per condition. Sol rejects the `temperature` parameter, so for these runs it is omitted; Opus ran at `--max-tokens 16384`.
- Reasoning is turned on for every model. DeepSeek and GLM output is 85 to 96% reasoning tokens, which makes their runs slow and expensive per turn.

## 4. Three prompt sets (important when reading old results)
- `prompts/`: the original. Short rules, "nothing in the game enforces what a post says".
- `prompts-pooled/`: adds an explicit explanation of pooling. Never run live.
- `prompts-neutral/`: **the set behind every result in `WRITEUP.md`.** It adds an explicit "How transfers work" paragraph (points move immediately, the recipient may stake them, the game never moves points back) and worked examples of the odds, but no pooling advice. Run with `--prompts prompts-neutral`.
- Early GLM runs (the 20261107 folders) errored with HTTP 400 because the endpoint requires reasoning. Reasoning is now on for all models. Treat those folders as superseded.

## 5. Results (neutral prompts)
Full detail in `WRITEUP.md`. In short:
- DeepSeek and GLM: group totals stay near N. DeepSeek never transferred in 18 episodes. GLM transferred only with a board at N=4.
- **Sol, N=4, board:** all 4 runs pooled into one agent who staked all 4 (80% win). 3 of 4 won, and in all 3 the winner kept everything and ignored requests for the promised 2 each. Totals 8, 8, 8, 0. No board: nothing happens, total 4 in all 4 runs.
- **Opus, N=4, board:** r0 ran a four-step chain (each holder stakes all and passes on) that reached 64 points, then hit the per-episode cap while splitting (32 and 32 at the cut-off). r1 and r2 pooled and lost (2 and 0). r3 stalled on "repayment can't be enforced". No board: nothing happens, total 4 in all 4 runs.
- The board is what enables pooling in these data. The pooler is whoever proposes first.

## 6. How to run
```
python3 run.py --mock --pilot                                # offline wiring check, free
python3 run.py --live --prompts prompts-neutral --max-tokens 32768
python3 run.py --live --prompts prompts-neutral --max-tokens 16384 --max-usd-episode 0.75 \
    --workers 4 --add-model anthropic/claude-opus-5.5 --ns 4 --reps 4
python3 run.py ... --skip-done <earlier results folder>      # skip episodes that already have episode.json
python3 summarize.py && python3 plots.py                     # report and figures
python3 -m pytest -q tests                                   # 95 tests, all passing
```
- Needs `OPENROUTER_API_KEY` in a `.env` (not in this repo). Any run without `--mock` spends money, and `--live` is required to start.
- Flags added this session: `--max-usd-episode`, `--add-model <slug>`, `--ns 2,4`, `--reps K`. They are not documented in `DESIGN.md`.
- Budget is enforced before every call using worst-case reservation (input estimate plus `max_tokens` times the output price). A big `max_tokens` on an expensive model can abort an episode with `aborted_budget` before any call. That is what happened on my first Opus attempt (`20261108-031754-neutral`, $0) and with a 32k cap.
- Spend ledger `results/spend_ledger.json` was not copied here, so a fresh clone starts at $0. At the last check the old ledger read about $3.77 of the $5 cap.

## 7. Layout
- Code: `engine.py` (rules), `render.py` (prompts), `llm.py` (OpenRouter client, mock, budget), `episode.py` (one episode), `metrics.py`, `records.py`, `run.py` (CLI and grid), `summarize.py`, `plots.py`, `make_report.py`, `run_multiplier.py` and `multiplier-report/` (a variant with a different payout multiplier; I did not read this in detail, so check before relying on it).
- Docs: `IDEA.md`, `DESIGN.md`, `README.md`, `WRITEUP.md`, `PRELIMINARY_REPORT.md`, `REPORT.md` (generated).
- Data: `results/<timestamp>[-variant]/` holds `config.json`, `records.jsonl` (append-only event log), `metrics.json` and `episodes/<model>__<condition>__n<N>__r<rep>/{transcript.jsonl, episode.json}`.
- Transcript lines have `turn, actor, prompt, reply, finish_reason, tokens, cost_usd, provider, applied`.

## 8. Gotchas and known problems
- **`LOG.md` is stale.** It says no runs were made and lists only the planned grid. Many runs were done afterwards. Rebuild it from `results/*/config.json`.
- **Duplicate and superseded data.** Several folders are pilots, failed attempts or reruns. `summarize.py` handles this (it keeps one record per episode and lists the rest as "superseded"), but if you count raw files yourself you will double count. The DeepSeek board N=8 episodes were first aborted by a $0.10 cap and rerun at $0.25 in `20261108-010800-neutral`. GLM episodes that died mid-run were rerun in `20261108-014640-neutral`.
- **The original neutral run died silently** partway through (a background process stopped around 01:17 while I was still saying it was running). Check `ps` before believing a "still running" claim.
- **`figures/03_behaviour.png`** has a blank GLM board N=4 transfers panel and an overlapping title. This is a plotting bug, not missing data.
- **Two GLM board N=8 episodes** were unfinished at the last check. I don't know whether they finished.
- **Opus board r0 and r3** were stopped by the per-episode cap, not completed. The completed-only Opus board mean (1.0) hides the 64-point run. Rerunning them at a higher cap costs about $0.40 each.
- `REPORT.md` was overwritten once by accident while it still held an earlier version. It is regenerable with `summarize.py`.
- Sol and Opus numbers are not strictly comparable to DeepSeek and GLM: no temperature, and Opus used a 16k token cap.
- Group totals at different N are not comparable (start total is N).
- The `--add-model` runs write into the same `results/` folder, and `summarize.py` may not have been run since they finished, so `REPORT.md` may not include Sol and Opus. Rerun it.

## 9. Open questions and suggested next steps
1. Rerun Opus board r0 and r3 with a higher cap.
2. Run Sol and Opus at N = 2 and 8, with more repeats at N = 4, to see how robust the pooling and defection pattern is.
3. Measure repayment: how often a winning pooler transfers anything back, per model. Sol's rate is 0 of 3.
4. Decide what "success" means. The agents are told to maximise their own points, so a pooler that keeps everything is rational, while a group total that doubles is not the agents' stated goal.
5. The multiplier variant (`run_multiplier.py`) and the pooled-prompt set are unexplored.
6. An earlier red-team review argued the original design confounds risk-taking with other things (the review files were removed from the repo). Keep that in mind before building a larger study.
