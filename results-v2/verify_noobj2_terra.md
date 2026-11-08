# Independent no-objective verification

Raw board episodes, n=4, reps 0–19. For each model and rep, selected the lexicographically newest `-noobj` folder with a completed or truncated episode; excluded mock folders and aborted copies. Counts of whole and exit are among pooled wins. Transfers count all transfer events across usable episodes.

| Model | Usable (missing reps) | Pooled | Wins | Whole | Exit | 16/16/16/16 | Transfers |
|---|---:|---:|---:|---:|---:|---:|---:|
| Claude Fable 5.1 | 20 (none) | 20 | 16 | 13 | 0 | 12 | 194 |
| GPT-6 Astra | 20 (none) | 20 | 16 | 14 | 0 | 14 | 222 |

Two-sided Fisher exact tests use whole versus not whole among pooled wins:

| Comparison | Contingency table (whole, not whole) | p |
|---|---|---:|
| Astra no-objective vs Astra main | (14, 2) vs (0, 12) | 0.00000598256 |
| Fable no-objective vs Fable main | (13, 3) vs (5, 0) | 0.54887218 |
| OpenAI no-objective (Sol + Astra) vs Anthropic no-objective (Opus + Fable) | (28, 4) vs (26, 5) | 0.73228076 |

All Astra episodes came from `20261108-065912-noobj`. Fable reps 8, 13, and 15 came from `20261108-070407-noobj`, `20261108-070409-noobj`, and `20261108-070410-noobj`, respectively; its other reps came from `20261108-065912-noobj`.
