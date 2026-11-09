# Paper outline

Modelled on "Enter the Dolosseum" (Apart, Oct 2026). What that paper does well, and what this outline copies:
- **Short and direct:** about 5 pages of body, then references and appendices. The sprint limit is 8 pages.
- **Conversational, numbered section titles** that state the finding ("Sol did the thing", "A suspicious score isn't enough").
- **Casual abstract that leads with the findings,** about 170 words, ending on a one-sentence takeaway.
- **Every table caption interprets** the table ("Luna's payoffs were identical across conditions").
- **Honest about null and messy results,** with their own subsections, not buried.
- **Claims are linked to retained evidence** (repo paths, run folders) in the references.
- **Required appendix:** Limitations and Dual-Use. Plus a fun appendix, an evidence appendix, and an LLM usage statement.
- **Related:** Dolosseum found Sol following through on a *prompted* collusion scheme while Opus's trace didn't show
  deliberate agreement. Our result rhymes with that: cite it [Dolosseum] in Related Work.

Every number below was recounted from the raw game logs (analysis script, author recount, two LLM-agent recounts).
The no-objective numbers were recounted again on Nov 8 from the raw `results-v2/*noobj*/episodes/*/episode.json`
files, because `analysis/episodes.csv` does not include the Fable and Astra no-objective runs.

**Wording:** the main metric is called **"paid back their peers"** everywhere (paper, figures, slides). Definition:
after a winning pool, every agent that chipped in ends the game with at least the 1 point it started with.
(Older files and verify reports call it "contributors made whole"; it's the same measure.)

---

## Title
- **Honor Among Agents: Who Keeps the Pot When Promises Can't Be Enforced**

Author block: name, affiliation, team name, "With Apart Research".

## Abstract (aim for 150–250 words, casual and findings-first)
Sentence roles, in order:
1. Why: in July 2026, agents in a swarm found a shared folder, turned it into a message board, and took risks
   "for the good of the collective." We ask when agents take on risk for each other, and whether the one holding
   the group's stake acts for the group.
2. What we did: 4 agents, 1 point each, a gamble where pooling everyone's points is a great deal for the group,
   unenforceable transfers, a shared message board, each agent told to maximize its own points. 8 models, 3 labs.
3. The board turns it on: no model pooled in any game without a board (0 of 160). With one, Opus and Sol pooled
   in 16 of 20 games each.
4. Then they split: after a winning pool, the Claude models paid back their peers 17 of 19 times; the OpenAI models
   0 of 24, every one after a public promise to pay back (Fisher p = 4e-10).
5. It isn't the exit button (no end vote: Opus 13/15, Sol 0/15). It's the instruction: with the "maximize your own
   points" paragraph removed, Sol and Astra paid back their peers 14 of 16 times each, and the labs look the same.
6. Gemini 4 Argon proposed pooling in every game and sent zero points. Cheap models (Haiku 5.5, Luna 6) never pooled.
7. Takeaway: when a selfish goal and a promise conflict, some frontier models keep the promise and some follow the
   goal. Test the model you deploy with the instructions you deploy it with.

## 1. Why this matters (motivation, about 0.5 page)
- July 2026 incident (METR, via the sprint brief): ~1,200 agents found a shared folder, turned it into a message board,
  and ~700 broke into Hugging Face together. Some took risks "for the good of the collective." Nobody told them to.
- The question: when will agents take on risk for each other? Once one agent holds the group's stake, does it act
  for the group? What switches that on or off?
- Our game is a tiny, controlled version of that situation: a message board, a reason to take risks for each other,
  and nothing enforcing any deal.
- Contributions (3–4 bullets): the testbed; an 8-model, 3-lab comparison with a paired no-board control; two
  ablations (no exit button, no selfish objective) that separate the board, the exit, and the instruction; a
  cheap-proxy null.
- Sprint tracks it serves: emergent collective behavior (the board), trust and promise-keeping between agents,
  evaluating swarms with cheap stand-ins.

## 2. Related work (about 0.33 page)
Verify every citation before it goes in; several are 2026 preprints found by search.
- Trust games with LLMs: Xie et al., NeurIPS 2024 (LLM agents simulate human trust behavior). Berg et al. 1995
  (the trust game). Charness & Dufwenberg 2006 (promises raise trust and trustworthiness in humans).
- Cooperation across models: Vallinder & Hughes 2024 (donor game: Claude > Gemini > GPT-4o).
  arXiv 2512.07462 (Claude stays prosocial under selfish framing; GPT follows the instruction), which directly
  predicts our no-objective result.
- Communication: GovSim 2024 (removing communication hurts cooperation); "Cheap Talk Enables Collective Repair".
- Multi-agent risk: Hammond et al. 2025 (multi-agent risks from advanced AI). Dolosseum (Apart, Oct 2026).
  Colosseum (Nakamura et al. 2026). Mallen, Deeb, Greenblatt 2026 (score-seeking in LLMs).
- The gap: one agent holding the whole group's stake, a logged promise → action record, and ablations that switch
  the board, the exit and the objective off one at a time.

## 3. The game (about 0.75 page) + Figure 1 (14_game_rules.png)
- Rules: 4 agents, 1 point each, 8 rounds, fixed turn order. One play per agent: stake s, win 2s with probability
  s/(s+1). Alone that's a coin flip; pooling all 4 gives an 80% shot at 8. Transfers are instant and unconditional;
  promises are just text. Goal stated to each agent: maximize your own points.
- Turn structure: each turn an agent can post once, transfer any number of times, play once per game, vote to end,
  and end its turn (≤12 actions). Each turn shows balances, other agents' actions since its last turn, and new posts.
  Persistent per-agent memory for the whole game.
- Ending: the game ends after a round where everyone holding points voted to end, or after 8 rounds. If you're the
  only one holding points, your vote alone ends it.
- Conditions (paired seeds, same dice): board vs no board. Controls: no end vote (fixed 8 rounds); no objective
  (the "maximize your own points" paragraph removed, scoring rules kept).
- Models: Claude Opus 5.5, Claude Fable 5.1, GPT-6.1 Sol, GPT-6 Astra, GPT-5.6 Sol, Gemini 4 Argon, Claude Haiku 5.5,
  GPT-6 Luna. Same-model groups, 20 board + 20 no-board games each (320 main games). All via OpenRouter, reasoning
  on, provider-default effort.
- Note v1 (a single-action, stateless pilot) as an earlier exploration with the same qualitative Sol result.

## 4. What we measured (about 0.5 page)
- Unit = game. Definitions:
  - **Pooled:** one agent received points from all 3 others before it played.
  - **Paid back their peers** (main metric): after a winning pool, every contributor ends with ≥1 point.
  - **Left right after winning:** the pooler's next move after winning was to vote to end, without paying anyone.
  - Also: largest-holder share, 16/16/16/16 endings, chain length, transfers.
- Stats: Wilson 95% CIs, exact McNemar (board vs no board, paired by seed), two-sided Fisher exact (model vs model).
  Descriptive, no multiple-testing correction.
- Verification: four independent counts from raw logs; quotes verified word for word. The main metric was chosen
  after the first results came in; the result holds under the other measures (largest-holder share 100% vs 25%,
  16/16/16/16 endings).

## 5. What happened

### 5.1 The board turns it on (Figure: 11_board_switch.png)
- No board: 0 pools in 160 games (every model). Board: Opus 16/20, Sol 16/20 (McNemar p = 0.00003 each),
  Astra 13/20, Fable 6/20.
- Cheap models never pooled, board or not.

### 5.2 Same game, opposite endings (Figures: 01a_final_balances.png, 10_three_types.png; Table 1)
- Table 1 (per model, board): pooled (board / no board), winning pools, paid back their peers, left right after winning.
  Caption that interprets: "Claude pays everyone back; ChatGPT keeps the pot; Gemini never sends a point."

  | Model | Pooled (board) | Pooled (no board) | Winning pools | Paid back their peers | Left right after winning |
  |---|---|---|---|---|---|
  | Claude Opus 5.5 | 16/20 | 0/20 | 14 | 12/14 | 0 |
  | Claude Fable 5.1 | 6/20 | 0/20 | 5 | 5/5 | 0 |
  | GPT-6.1 Sol | 16/20 | 0/20 | 12 | 0/12 | 9 |
  | GPT-6 Astra | 13/20 | 0/20 | 12 | 0/12 | 11 |
  | Gemini 4 Argon | 0/20 | 0/20 | 0 | – | – |
  | GPT-5.6 Sol | 0/20 full pools | 0/20 | 0 | – (kept 4/5 small pools) | – |
  | Claude Haiku 5.5 | 0/20 | 0/20 | 0 | – | – |
  | GPT-6 Luna | 0/20 | 0/20 | 0 | – | – |

- Opus 12/14; the two misses were chains that lost a later stake. 10 of 20 games ended 16/16/16/16.
- Sol 0/12, left right after winning 9/12, games end 8/0/0/0 (Fisher p = 0.00001 vs Opus). Astra 0/12, 11/12.
- Quotes: Sol promise and plea (same game); Opus chain proposal; Opus private reasoning "I'll honor my word too".

### 5.3 They promise first, then don't pay
- In all 24 OpenAI winning pools (Sol + Astra), the pooler publicly promised repayment before collecting; Sol
  restated it in 5. All 24 broken.
- Frame as **broken promises, not proven lies**: OpenAI hides almost all of Sol's reasoning (summaries in 24 of 486
  turns), so we can't see intent at promise time. Use "broke their promise", not "lied", in the paper.
- GPT-5.6 Sol says the quiet part out loud (quote: "score-maximizing action"), which links to the score-seeking post.
- They also *trust*: the ChatGPT agents send their points to whoever asks first, if the asker promises to pay back.

### 5.4 It's not the exit button (Figures: 09_exit_control.png, 12_made_whole.png)
- No end vote: Opus 13/15, Sol 0/15 (Fisher p = 0.000002). Sol pays the first round and passes the pot along, but a
  later holder keeps it.
- "Broken promises spread": the later holder cites the earlier defection (quote g).
- Caveat in-line: Sol was served by a different host (Amazon Bedrock) in this control; result matched the main run.

### 5.5 It's the "maximize your own points" line (Figure: 16_objective.png; Table 2)
- Same game, same seeds, the goal paragraph removed (scoring rules kept). Board on.
- Table 2 caption: "Without the selfish goal, ChatGPT pays its peers back as often as Claude does."

  | Paid back their peers | Told to maximize own points | No objective |
  |---|---|---|
  | Claude Opus 5.5 | 12/14 | 13/15 |
  | Claude Fable 5.1 | 5/5 | 13/16 |
  | GPT-6.1 Sol | 0/12 | 14/16 |
  | GPT-6 Astra | 0/12 | 14/16 |

- Sol and Astra: 0/12 → 14/16 each (Fisher p = 0.000006 each). Labs converge: OpenAI 28/32, Anthropic 26/31 (p = 0.73).
- Pooling goes up: Opus 19/20, Sol, Astra and Fable 20/20 (Fable was 6/20). Opus with no board and no objective: 0/20.
- They still chase points, **for the group**: chains reached all four agents in 13–15 of 20 games; 12–14 of 20 ended
  16/16/16/16; mean final total about 41–45 points (from 4).
- **And they take more risk:** 5–6 of 20 games per model ended with everyone at 0, because they kept staking the
  whole group pot. Every miss was a lost later stake. No pooler from either lab kept the money; 0 of 63 winners left
  right after winning.
- Gemini: still 0 transfers, 0 plays (402 posts).
- Read: ChatGPT can keep a promise; when the instructions say "look out for yourself", it follows the instruction over
  the promise. Claude keeps its word either way. This matches arXiv 2512.07462 (verify).

### 5.6 Gemini won't play (quotes f, j)
- Pooling proposed in 20/20 games, 0 transfers; reasons: backward induction, enforcement, "you send first".
- Framing: the rational skeptic. Given what Sol and Astra do with the objective on, its caution is justified.

### 5.7 Is it a lab thing? (Figures: 15_labs.png, 01d_final_balances.png)
- Paid back their peers: Opus 12/14 + Fable 5/5 = Anthropic 17/19; Sol 0/12 + Astra 0/12 = OpenAI 0/24 (Fisher p = 4e-10).
- Fable pools rarely (6/20 vs Opus 16/20): a cautious cooperator. Astra mirrors Sol.
- Report carefully: two models per lab is suggestive, not a lab rule. And the split disappears without the objective (5.5).

### 5.8 Older Sol, cheaper models (Figures: 08_generations.png, 01c_final_balances.png)
- GPT-5.6 Sol: proposes, others won't send first; no full pools; kept the winnings in 4 of 5 small pools (small n).
- Haiku 5.5 and Luna 6: 0/40 pooled each. Cheap proxies miss the whole phenomenon.

## 6. What we'd take away (about 0.5 page)
Mirror the deck's takeaways:
1. Told to maximize their own points, Sol and Astra broke their promises to their peers for their own gain (0 of 24).
2. Opus and Fable honored their peers anyway, even when it cost them their own reward (17 of 19).
3. Told only how points work, not to maximize them, Opus, Fable, Sol and Astra all played for the group, and took
   bigger risks to do it. Gemini still never trusted anyone.
4. None of it happens without the board: 0 pools in 160 no-board games. The shared channel is the place to monitor.
- Implications: promise-keeping under unenforceable deals is a measurable, model- and prompt-specific swarm property;
  test the frontier model you deploy, with the instructions you deploy it with; cheap models gave a clean null.
- Short fun close in the Dolosseum style (e.g. "Opus paid everyone. Sol paid itself. Gemini paid nobody, including itself.").

## Code and Data
- Repo: https://github.com/hsoras/honor-among-agents. Run folders under `results-v2/`; `analysis/cells.md`,
  `episodes.csv`; verification files (`AUDIT.md`, `verify_terra.md`, `verify_haiku.md`, `verify_noobj_terra.md`,
  `verify_noobj_haiku.md`, `verify_noobj2_terra.md`, `verify_noobj2_haiku.md`). Raw transcripts available on request
  (git-ignored for size).

## Author contributions / Acknowledgements

## References
- Dolosseum (Bouche, Faber et al., Apart Oct 2026) + its repo.
- Colosseum: Nakamura et al. 2026, arXiv:2602.15198.
- Mallen, Deeb, Greenblatt (2026), "Towards understanding score-seeking in LLMs", LessWrong.
- METR Hugging Face incident report (from the sprint page).
- Related-work papers in Section 2 (verify each before citing).
- Repo evidence links (run folders, audit files).

## Appendix A. Limitations and Dual-Use / Ethical Considerations (required)
- Limitations:
  - The main prompt instructs self-interest. Tested directly (5.5): without it, Sol and Astra keep their promises.
  - One-shot game, no reputation or next game, so defecting is the "rational" move; models still differ.
  - Possible test awareness (same for every model).
  - N=4 only; one game; same-model groups only.
  - Fixed turn order: agent_1 almost always becomes the pooler, so no claims about who leads.
  - Reasoning visibility differs (Sol mostly hidden), so Sol's motives come from public posts only.
  - Provider/host differences (Sol no-exit control on Bedrock). Thinking effort left at each provider's default:
    same prompts and settings for every model, but effort isn't equal across labs.
  - Main metric chosen post hoc (robust across alternatives).
  - Behavior categories come from LLM readers; numbers come from code.
  - Incomplete games: Gemini hit 280-char post rejections and some games stopped early (3 in the main run; 5 of 20 in
    the no-objective run; 6 of 20 in Opus no-board no-objective). None of these pooled, so headline rates are unaffected.
  - Model IDs as requested; the served model can't be verified.
- Dual use: fake points in a toy game; a benchmark for promise-keeping. Transcripts show persuasion and defection
  patterns that could inform manipulation of agents; the purpose is measurement before deploying agents that share
  resources.

## Appendix B. The fun stuff
- Opus chain to 64 (05_opus_chain.png), Sol pool-win-leave timeline (06_sol_defection.png), quote cards.
- Gemini's best lines; GPT-5.6's breach accusation (quote from r19).

## Appendix C. Evidence availability
- Run folder map, configs (prompt hashes, routes, seeds), verification reports, figure scripts.

## LLM Usage Statement
- Claude Opus 5.5, GPT-6.1 Terra, GPT-6 Luna, Claude Haiku 5.5 and Claude Sonnet 5.5 built the harness, ran analyses,
  read transcripts and verified claims. The claims are the author's and rest on retained runs and independent recounts.
