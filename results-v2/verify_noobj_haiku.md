# Independent verification: noobj board episodes

Reviewer: Haiku 5.5 (review sub-agent). Read-only except this file. Counts were computed from raw `episode.json` files with a standalone script (`verify_noobj.py` in the scratchpad). No analysis outputs, `verify_*` files, `.env`, or API calls were used.

## Episode selection

- Folders: `results-v2/*-noobj` (`*-mock-noobj` excluded). Board episodes only.
- For each model and rep 0–19, the newest folder (lexicographically largest name) whose `summary.status` is `completed` or `truncated` was used.
- Folders in play: `20261108-064308-noobj` (Opus, Sol, some duplicates), `20261108-064439-noobj` (Sol, Gemini), `20261108-064440/41/42-noobj` (Opus reruns of r4, r9, r19).
- Older duplicates that were skipped: `064308` holds `aborted_budget` for Opus r4, r9, r19 and for most Sol reps. Sol r01 is `completed` in both folders, and the newer `064439` copy was used.
- Gemini r03 has status `error` in its only folder, so it has no usable episode.

## Per-model results

| Model | n usable | Missing reps | Pooled | Pooled wins | Whole | Exit | 16/16/16/16 | Total transfers (events) | Total transfers (summary) |
|---|---|---|---|---|---|---|---|---|---|
| anthropic_claude-opus-5.5 | 20 | none | 19 | 15 | 13 | 0 | 14 | 149 | 149 |
| openai_gpt-6.1-sol | 20 | none | 20 | 16 | 14 | 0 | 14 | 238 | 238 |
| google_gemini-4-argon | 19 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Opus pooled-but-not-won episodes: r01, r07, r14, r18. Pooled episodes with no pooler play: none for either model.

Gemini's 19 usable episodes are 5 `truncated` plus 14 `completed`. None had any play or transfer. Final balances are 1/1/1/1 in all 19, and the runs stopped after 3 to 8 rounds.

## Claim checks

| Claim | Result | Verified value |
|---|---|---|
| Opus n=20 | CONFIRMED | 20 |
| Opus pooled 19 | CONFIRMED | 19 |
| Opus wins 15 | CONFIRMED | 15 |
| Opus whole 13 | CONFIRMED | 13 |
| Opus 16x4 = 14 | CONFIRMED | 14 |
| Sol 6.1 n=20 | CONFIRMED | 20 |
| Sol 6.1 pooled 20 | CONFIRMED | 20 |
| Sol 6.1 wins 16 | CONFIRMED | 16 |
| Sol 6.1 whole 14 | CONFIRMED | 14 |
| Sol 6.1 16x4 = 14 | CONFIRMED | 14 |
| Sol 6.1 exit 0 | CONFIRMED | 0 |
| Gemini n=19 | CONFIRMED | 19 (rep 3 missing) |
| Gemini transfers 0 | CONFIRMED | 0 |

## System prompt check

- Scanned the first (`system`) message of every agent conversation in all noobj board and noboard episodes that are present, including duplicates and unusable ones: 105 episodes, 420 system messages. Matches for "maximize your own score" (case-sensitive or case-insensitive): **0**. CONFIRMED.
- Main run `results-v2/20261108-044218`: 26 episodes, 104 system messages, all containing "maximize your own score" (case-insensitive and exact). CONFIRMED.

## Method notes

- Pooler: for each agent, count distinct senders of transfers to it that occur before its own first play. The pooler is the agent whose 3rd distinct sender arrives earliest in event order. Agents with no play are recorded separately; none occurred.
- Pooled win: the pooler's first play has `won` true.
- Whole: all three other agents have final balance >= 1, counted only for pooled episodes.
- Exit: after the pooler's winning play, the first of its later `transfer` or `vote_end` events is a `vote_end`. Exit is 0 for both models, so the answer does not depend on which of the events is counted first.
- Transfer totals match the `summary.transfers` field in every episode.
