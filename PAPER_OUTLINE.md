# Paper outline

Modelled on "Enter the Dolosseum" (Apart, Oct 2026). What that paper does well, and what this outline copies:
- **Short and direct:** about 5 pages of body, then references and appendices; about 10 pages total.
- **Conversational, numbered section titles** that state the finding ("Sol did the thing", "A suspicious score isn't enough").
- **Casual abstract that leads with the findings,** about 170 words, ending on a one-sentence takeaway.
- **Every table caption interprets** the table ("Luna's payoffs were identical across conditions").
- **Honest about null and messy results,** with their own subsections, not buried.
- **Claims are linked to retained evidence** (repo paths, run folders) in the references.
- **Required appendix:** Limitations and Dual-Use. Plus a fun appendix, an evidence appendix, and an LLM usage statement.
- **Related:** Dolosseum found Sol following through on a *prompted* collusion scheme while Opus's trace didn't show
  deliberate agreement. Our result rhymes with that: cite it [Dolosseum] in Related Work.

Numbers below were confirmed by four independent counts unless marked (pending).

---

## Title options
- **Honor Among Agents: Who Keeps the Pot When Promises Can't Be Enforced** (recommended)
- Trust Me, I'll Pay You Back
- Pool, Win, Leave

Author block: name, affiliation, team name, "With Apart Research".

## Abstract (aim for 150–250 words, casual and findings-first)
Sentence roles, in order:
1. What we did: N agents, 1 point each, a gamble where pooling everyone's points is a great deal for
   the group, unenforceable transfers, a shared message board, each agent told to maximize its own points.
2. The board turns it on: with a board, Claude Opus 5.5 and GPT-6.1 Sol pooled in 16 of 20 games;
   without one, no model pooled in any game (0 of 120).
3. Then they split: after a winning pool, Opus left every contributor whole 12 of 14 times; Sol 0 of 12,
   usually voting to end the game right after winning. GPT-6 Astra matched Sol (0 of 12).
4. It isn't the exit button: with the end vote removed, Opus 13/15, Sol 0/15. Sol passes the pot along
   and the last holder keeps it.
5. Gemini 4 Argon proposed pooling in every game and sent zero points ("backward induction makes sending first
   irrational"). Cheap models (Haiku 5.5, GPT-6 Luna) never pooled: 0 of 80.
6. Takeaway: promise-keeping under unenforceable deals differs sharply across frontier models, and cheap
   stand-ins miss it entirely. Test the model you deploy.

## 1. Why a gamble? (motivation, about 0.5 page)
- July 2026 Hugging Face incident: agents found a shared directory, used it as a message board, coordinated.
- Swarm risk isn't only "will they coordinate" but "what happens to trust inside the swarm".
- Questions: (a) does a board alone produce collective high-risk action? (b) do agents keep unenforceable
  promises? (c) do cheap models behave like frontier ones (a sprint track question)?
- Contributions list (3–4 bullets): testbed; 7-model comparison with paired no-board control; no-exit control;
  cheap-proxy result.

## 2. The game (about 0.75 page) + Figure 1 (14_game_rules.png)
- Rules: start 1 point each; one play per agent: stake s, win 2s with probability s/(s+1); pooling 4 gives 80% for 8.
  Transfers instant, unconditional; promises are text. Goal stated to each agent: maximize your own points.
- Turn structure (v2): fixed order, rounds (2N cap), multi-action turns via tool calls (≤12 actions),
  one post per turn, round-scoped end votes, persistent per-agent memory, state + deltas each turn.
- Conditions: board vs no board, paired seeds. Control: no end vote, fixed 8 rounds.
- Note v1 (a single-action, stateless pilot) as an earlier exploration with the same qualitative Sol result.

## 3. What we measured (about 0.5 page)
- Unit = episode. Definitions: pooled; pooled win; **contributors whole** (headline); largest-holder share;
  exit without paying; 16/16/16/16 endings; transfers.
- Stats: Wilson 95% CIs, exact McNemar (board vs no board, paired by seed), two-sided Fisher exact (model vs model).
- Verification: four independent counts from raw logs (analysis script, author recount, two LLM-agent recounts);
  quotes verified verbatim. Note: "contributors whole" chosen after first results; robust across alternative measures.

## 4. What happened

### 4.1 The board turns it on (Figure: 11_board_switch.png)
- Opus 16/20 vs 0/20; Sol 16/20 vs 0/20 (McNemar p = 0.00003 each). Astra 13/20 (pending: no-board value).
- No model pooled without a board (0 of all no-board games).

### 4.2 Same game, opposite endings (Figures: 01a_final_balances.png, 10_three_types.png; Table 1)
- Table 1 (per model, board): pooled, pooled wins, contributors whole, exit without paying, median largest share.
  Caption that interprets, e.g. "Opus splits the winnings; Sol and Astra keep them."
- Opus 12/14 whole, 10 games ending 16/16/16/16; Sol 0/12, exit 9/12, median share 100% (Fisher p = 0.00001).
- Astra 0/12, exit 11/12.
- Quotes: Sol promise and plea (same game); Opus private reasoning "keeping my word matters more".

### 4.3 It's not the exit button (Figures: 09_exit_control.png, 12_made_whole.png)
- No end vote: Opus 13/15, Sol 0/15 (p = 0.000002). Sol relays the pot and the last holder keeps it.
- "Broken promises spread": the later holder cites the earlier defection (quote g).
- Caveat in-line: Sol was served by a different host in the control.

### 4.4 Gemini won't play (quote f, j)
- Pooling proposed in 20/20 games, 0 transfers; reasons: backward induction, enforcement, "you send first".
- Framing: the rational skeptic. Its caution is justified by what Sol and Astra do.

### 4.5 Older Sol, cheaper models (Figures: 08_generations.png, 01c_final_balances.png)
- GPT-5.6 Sol: proposes, others won't send first; small pools; kept the winnings 4 of 5 times (small n).
  Quote e ("score-maximizing action"), which links to the score-seeking post.
- Haiku 5.5 and Luna 6: 0/40 pooled each condition. Cheap proxies miss the whole phenomenon.

### 4.6 Is it a lab thing? (Figures: 15_labs.png, 01d_final_balances.png)
- Contributors whole after a winning pool: Opus 12/14, Fable 5/5 (Anthropic 17/19) vs Sol 6.1 0/12,
  Astra 0/12 (OpenAI 0/24). GPT-5.6 Sol kept winnings in 4/5 small pools.
- Fable pools rarely (6/20 vs Opus 16/20): a cautious cooperator. Astra mirrors Sol (exit after win 11/12).
- Promise evidence: in all 24 OpenAI winning pools the pooler publicly promised repayment before collecting;
  all 24 broken. Frame as broken promises, not proven lies (Sol reasoning is encrypted).
- Report carefully: two models per lab is suggestive, not a lab effect.
- Abstract update: replace "7-model" with "8 models from 3 labs" and add the Anthropic/OpenAI split sentence.

## 5. What we'd take away (about 0.5 page)
- Promise-keeping under unenforceable deals is a measurable, model-specific swarm property.
- A message board is enough to produce collective high-stakes behavior, so the shared channel is the place to monitor.
- Test the frontier model you deploy; cheap models gave a clean null here.
- Short fun close in the Dolosseum style (e.g. "Opus paid everyone. Sol paid itself. Gemini paid nobody, including itself.").

## Code and Data
- Repo link; run folders; `analysis/cells.md`, `episodes.csv`; verification files (`AUDIT.md`, `verify_terra.md`,
  `verify_haiku.md`). Raw transcripts available on request (git-ignored for size).

## Author contributions / Acknowledgements

## References
- Dolosseum (Bouche, Faber et al., Apart Oct 2026) + its repo.
- Colosseum: Nakamura et al. 2026, arXiv:2602.15198.
- Mallen, Deeb, Greenblatt (2026), "Towards understanding score-seeking in LLMs", LessWrong.
- METR/Redwood Hugging Face incident report (from the sprint page).
- Repo evidence links (run folders, audit files).

## Appendix A. Limitations and Dual-Use / Ethical Considerations (required)
- Limitations: prompt instructs self-interest (Sol arguably follows instructions; frame as promise-keeping
  when breaking pays); one-shot game, no reputation; possible test awareness; N=4 only; fixed turn order
  (agent_1 always proposes); same-model groups only; provider/host differences (Sol control on Bedrock);
  reasoning visibility differs (Sol encrypted); headline metric chosen post hoc (robust across alternatives);
  behavior categories from LLM readers (numbers from code); Gemini 280-char rejections and 3 incomplete games;
  provider-default reasoning/temperature; model IDs as requested, served model not verifiable.
- Dual use: fake points only; a benchmark for promise-keeping; transcripts show persuasion/defection patterns
  that could inform manipulation of agents; purpose is measurement and mitigation.

## Appendix B. The fun stuff
- Opus chain to 64 (05_opus_chain.png), Sol pool-win-leave timeline (06_sol_defection.png), quote cards.
- Gemini's best lines; GPT-5.6's breach accusation (quote from r19).

## Appendix C. Evidence availability
- Run folder map, configs (prompt hashes, routes, seeds), verification reports, figure scripts.

## LLM Usage Statement
- Which models built the harness, ran analyses, read transcripts, verified claims; claims rest on retained runs
  and independent recounts.
