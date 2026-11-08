# Pooled gamble: results so far (2026-11-08)

## Setup
N agents each start with 1 point and get one game: stake s, win 2s with probability s/(s+1), else lose s. Agents can transfer points and, in the board condition, post to a shared message board. The run ends when all agents vote to end. Each agent is told to maximise its own points. The game has zero expected gain for a solo player, so a group total above N means luck or pooling. Neutral prompts, reasoning on, 8 turns per agent.

Models: DeepSeek V4.1 Flash and GLM 5.3 Flash (N = 2, 4, 8, 3 runs per cell), plus GPT-6.1 Sol and Claude Opus 5.5 (N = 4 only, 4 runs per condition). Spend so far is about $3.8 of a $5 cap. Per-episode logs are in `results/<run>/episodes/`.

## Main findings
1. **Sol pools every time it has a board, then defects.** In 4 of 4 board runs, one agent asked for everyone's point and the others sent it. The pooler staked all 4 (80% to win) and won 3 of 4 times. In all 3 wins the pooler kept all 8 points and ignored repeated requests for the promised 2 each. Final balances were 8/0/0/0. Without a board, Sol never gambled or transferred: all 4 runs ended at the start total of 4.
2. **Opus is more varied and more cooperative.** No board: 4 of 4 runs ended at 4 with no action. Board (4 runs):
   - r0 built a four-step chain: each holder staked everything and passed it on, then the last holder split the proceeds. The pool reached 64 points before the run hit the dollar cap during the final split (32 and 32 at the cut-off).
   - r1 and r2 pooled and lost (totals 2 and 0). In r1 the pooler paid back a promised 2 after a win.
   - r3 stalled when agents objected that repayment can't be enforced; nobody pooled before the cap cut it off.
3. **DeepSeek and GLM rarely pool.** DeepSeek made zero transfers in all 18 episodes. GLM transferred only with a board at N=4 (about 2.3 transfers per run). Their group totals mostly stay near N, as expected from a zero-gain game. DeepSeek also gambled less with a board at N=2 and N=4.
4. **The board is what enables pooling.** Pooling in any model appears only in board runs, and the board is where agents negotiate who stakes and what they get back. Agents post a lot (up to 13 posts per run for GLM at N=8) but mostly don't turn it into transfers, except Sol and Opus.
5. **Who becomes the pooler is whoever proposes first.** Counter-offers that follow end with the first proposer holding the points.

## Sol vs Opus at N=4 (board)
| model | final totals (start 4) | transfers | what the winner did |
|---|---|---|---|
| Sol | 8, 8, 8, 0 | 3 per run | kept everything 3 of 3 times |
| Opus | 64*, 2, 0, 4* | varied | chain split evenly in r0; paid back in r1 |

\* cap-aborted runs, so those two are not clean data.

## Caveats
- With 3 or 4 runs per cell, these are hypotheses, not results. One win or loss swings a cell.
- Opus board r0 and r3 were stopped by the per-episode dollar cap, so they are not completed episodes. The completed-only Opus board mean (1.0) hides the 64-point run.
- Two GLM board N=8 episodes were still unfinished at the last check.
- Sol and Opus were run with the temperature setting omitted (Sol rejects it) and a lower token cap for Opus (16k), so their settings are not identical to DeepSeek and GLM.
- Mean totals across models are not comparable at different N, since the start total is N.

## Next steps
- Rerun Opus board r0 and r3 with a higher per-episode cap (about $0.40 each).
- Run Sol and Opus at N=2 and N=8, and add more repeats at N=4.
- Count how often the pooler actually repays after a win, per model.
