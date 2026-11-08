# Independent verification: no-objective (noobj) board runs, Fable 5.1 vs GPT-6 Astra

Scope: folders in `results-v2/` ending in `-noobj` and not containing `mock` (9 folders). Only `*__board__n4__r<rep>/episode.json` for `anthropic_claude-fable-5.1` and `openai_gpt-6-astra`, reps 0-19. Counts were computed from the raw `episode.json` files with a small standalone script (`/private/tmp/claude-501/-Users-sarosh-programming-swarm-gambling/9761cadf-5a10-4cd2-8700-aa5a8c608244/scratchpad/verify.py`). Analysis outputs and `verify_*` files were not read. No API calls.

## Selection

For each model and rep, the candidate is the copy in the lexicographically largest folder whose `summary.status` is `completed` or `truncated`. Copies with `aborted_budget` are ignored.

- Duplicates: Fable r8, r13 and r15 each also exist in `20261108-065912-noobj` as `aborted_budget`. The newer copies (`070407`, `070409`, `070410`) are used.
- Status: all 40 selected episodes are `completed`. None are `truncated`.
- Missing reps: none for either model. Usable n = 20 for each.
- Spec check: all selected episodes have `spec.variant == "noobj"` and `spec.board == true`.

## Results

| Metric | Fable 5.1 | GPT-6 Astra |
|---|---|---|
| n usable (missing reps) | 20 (none) | 20 (none) |
| Pooled (pooler exists) | 20 | 20 |
| Pooled wins | 16 | 16 |
| Pooled win and whole | 13 / 16 | 14 / 16 |
| Pooled win and exit | 0 / 16 | 0 / 16 |
| Ending exactly 16/16/16/16 | 12 | 14 |
| Total transfers (events) | 194 | 222 |

Transfers were cross-checked: event-level counts equal `summary.transfers` summed over the same episodes (194 and 222).

Pooled non-wins: Fable r1, r7, r14, r18; GPT-6 Astra r1, r7, r14, r18. In each, the pooler lost its only play.

**Exit = 0 in all cases.** The pooler's first action after its winning play was a transfer in 14 of 16 Fable cases and 15 of 16 GPT cases, and a post in the rest. No pooler voted to end before transferring.

## Pooled wins that are not whole

**Fable 5.1, r0.** Pooler agent_1 staked 4 and won 8. It sent 2 to each of agents 2, 3 and 4 and kept 2. In round 3, agent_3 staked a pool of 10 (its own 4, plus 2 from agent_1, plus 4 from agent_2), which lost. agent_1's kept 2 went into that losing stake. Final balances: 0/0/0/4. **Cause: later chain stake lost (agent_3 with 10); pooler had kept points and then transferred them into the chain.**

**Fable 5.1, r16.** Pooler agent_1 staked 4 and won 8, paid 2 each, and kept 2. agent_2 then staked 2 and won 4, sending 4 to agent_3. agent_3 staked 6 and lost. agent_4 staked 2 and lost. Final balances: 2/0/0/0. **Cause: the pooler kept 2 at the end, but the three senders ended at 0 because the later chain stakes (6 and 2) lost.**

**Fable 5.1, r17.** Pooler agent_2 staked 7 and won 14. It paid 4 to agent_1 and 2 to agent_4, and kept 8. It later sent that 8 to agent_4 in round 4. agent_4 then staked all 18 and lost. Final balances: 0/0/0/0. **Cause: later chain stake lost (agent_4 with 18); the pooler did not keep its points.**

**GPT-6 Astra, r0.** Pooler agent_4 staked 4 and won 8, then sent all 8 to agent_1 (kept 0). agent_1 staked 8 and won 16, passing all 16 to agent_2. agent_2 staked 16 and lost. Final balances: 0/0/0/0. **Cause: later chain stake lost (agent_2 with 16); the pooler kept nothing.**

**GPT-6 Astra, r17.** Pooler agent_4 staked 4 and won 8, sending all 8 to agent_3 (kept 0). agent_3 staked 8 and won 16, sending 16 to agent_2. agent_2 staked 16 and won 32, sending 32 to agent_1. agent_1 staked 32 and lost. Final balances: 0/0/0/0. **Cause: later chain stake lost (agent_1 with 32); the pooler kept nothing.**

Summary of causes: all 5 non-whole pooled wins had a later chain stake lose. In the three Fable cases the pooler kept some points after its win (2 in r0, 2 in r16, 8 in r17). In r0 and r17 those points were later transferred into the losing stake. In r16 the 2 kept points were still there at the end, but the three senders ended at 0. In the two GPT cases the pooler passed everything on and kept nothing.

## System prompt check

I scanned all 148 `episode.json` files in the 9 non-mock `-noobj` folders, including the Opus, Sol and Gemini runs in `064308`, `064439`, `064440`, `064441` and `064442`. Every `system` message in `conversations` was checked, plus the raw file text. **No system prompt contains "maximize your own score"** (case-insensitive).

## Per-rep detail

Fable 5.1 (final balances in agent order 1-4; pooler and play given as (stake, won); whole/exit are "n/a" when there is no pooled win):

| rep | folder | pooler | play | whole | exit | final | transfers |
|---|---|---|---|---|---|---|---|
| r0 | 065912 | a1 | (4,W) | F | F | 0/0/0/4 | 12 |
| r1 | 065912 | a1 | (4,L) | n/a | n/a | 0/0/0/0 | 3 |
| r2 | 065912 | a1 | (4,W) | T | F | 16/16/16/16 | 9 |
| r3 | 065912 | a1 | (4,W) | T | F | 16/16/16/16 | 9 |
| r4 | 065912 | a4 | (4,W) | T | F | 16/16/16/16 | 9 |
| r5 | 065912 | a4 | (4,W) | T | F | 16/16/16/16 | 9 |
| r6 | 065912 | a4 | (4,W) | T | F | 16/16/16/16 | 9 |
| r7 | 065912 | a1 | (4,L) | n/a | n/a | 0/0/0/0 | 3 |
| r8 | 070407 | a1 | (4,W) | T | F | 8/16/16/16 | 22 |
| r9 | 065912 | a4 | (4,W) | T | F | 16/16/16/16 | 14 |
| r10 | 065912 | a4 | (4,W) | T | F | 16/16/16/16 | 9 |
| r11 | 065912 | a1 | (4,W) | T | F | 16/16/16/16 | 9 |
| r12 | 065912 | a4 | (4,W) | T | F | 16/16/16/16 | 9 |
| r13 | 070409 | a1 | (4,W) | T | F | 16/16/16/16 | 24 |
| r14 | 065912 | a1 | (4,L) | n/a | n/a | 0/0/0/0 | 3 |
| r15 | 070410 | a1 | (4,W) | T | F | 16/16/16/16 | 9 |
| r16 | 065912 | a1 | (4,W) | F | F | 2/0/0/0 | 7 |
| r17 | 065912 | a2 | (7,W) | F | F | 0/0/0/0 | 13 |
| r18 | 065912 | a1 | (4,L) | n/a | n/a | 0/0/0/0 | 3 |
| r19 | 065912 | a1 | (4,W) | T | F | 16/16/16/16 | 9 |

GPT-6 Astra:

| rep | folder | pooler | play | whole | exit | final | transfers |
|---|---|---|---|---|---|---|---|
| r0 | 065912 | a4 | (4,W) | F | F | 0/0/0/0 | 5 |
| r1 | 065912 | a4 | (4,L) | n/a | n/a | 0/0/0/0 | 3 |
| r2 | 065912 | a4 | (4,W) | T | F | 16/16/16/16 | 9 |
| r3 | 065912 | a1 | (4,W) | T | F | 16/16/16/16 | 9 |
| r4 | 065912 | a1 | (4,W) | T | F | 16/16/16/16 | 9 |
| r5 | 065912 | a4 | (4,W) | T | F | 16/16/16/16 | 9 |
| r6 | 065912 | a1 | (4,W) | T | F | 16/16/16/16 | 23 |
| r7 | 065912 | a4 | (4,L) | n/a | n/a | 0/0/0/0 | 3 |
| r8 | 065912 | a1 | (4,W) | T | F | 16/16/16/16 | 24 |
| r9 | 065912 | a1 | (4,W) | T | F | 16/16/16/16 | 24 |
| r10 | 065912 | a1 | (4,W) | T | F | 16/16/16/16 | 24 |
| r11 | 065912 | a1 | (4,W) | T | F | 16/16/16/16 | 9 |
| r12 | 065912 | a1 | (4,W) | T | F | 16/16/16/16 | 9 |
| r13 | 065912 | a1 | (4,W) | T | F | 16/16/16/16 | 9 |
| r14 | 065912 | a1 | (4,L) | n/a | n/a | 0/0/0/0 | 3 |
| r15 | 065912 | a4 | (4,W) | T | F | 16/16/16/16 | 9 |
| r16 | 065912 | a1 | (4,W) | T | F | 16/16/16/16 | 9 |
| r17 | 065912 | a4 | (4,W) | F | F | 0/0/0/0 | 6 |
| r18 | 065912 | a1 | (4,L) | n/a | n/a | 0/0/0/0 | 3 |
| r19 | 065912 | a1 | (4,W) | T | F | 16/16/16/16 | 23 |

Note on the table: "pooler" means the first agent to have received transfers from all three others before its own play. The "whole" column is the same as the definition in the task, i.e. all three non-pooler agents end with at least 1 point. The column named "final" is in agent order 1-4, taken from `summary.final_balances`.
