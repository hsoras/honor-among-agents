# Run log

Exploration stage. No directional prediction or user hypothesis was supplied; do not add one retrospectively. Log every attempt, including failures, and keep the raw episode values beside any three-run summaries.

| Date | Run / command | Model × condition × N × reps | Result / run directory | Keep or discard; reason |
|---|---|---|---|---|
| — | No run recorded in this log. The existing spend ledger's $0.0031 entry is a prior accidental live check, not a run of this planned comparison. | — | — | Excluded from analysis; no matching run artifacts in this experiment directory. |

## Planned grid (not run)

- Models: `deepseek/deepseek-v4.1-flash-1017`, `z-ai/glm-5.3-flash`.
- Conditions: board + transfers; no board + transfers.
- Homogeneous group sizes: N = 2, 4, 8.
- Three episodes per model × condition × size: 36 episodes in total.
- Existing pairing: the same seed for board/no-board episodes at each model, size, and replicate.
- No hypothesis or directional prediction is preregistered. Summarize individual points, group total and average, concentration, plays/stakes, transfers, posts, votes, and completion status descriptively.
- Paid-run estimate is not restated here as an assurance: price listings are provider/routing dependent and the current catalog/provider figures disagree for GLM. No paid calls were made during documentation or price verification.

## 2026-11-08: output cap, shared budget, records, figures (no new paid runs)

- Output cap raised to 16384 per call (`--max-tokens` to override). Episodes now record token totals, reasoning tokens, and length-limited replies. Recorded evidence: DeepSeek replies were mostly reasoning (about 93-97% of completion tokens in the completed runs so far), and 1 of 15 replies in one cell hit the 8192 cap.
- Budget ledger is now re-read and updated under a file lock per reservation and settlement. Earlier code let concurrent processes overwrite each other's spend. Caps are unchanged ($0.10 per episode, $5 total).
- New `records.jsonl` (append-only) per run. Stopped runs halt new calls and account for every planned episode. Crashes are recorded and the grid continues.
- `summarize.py` rewritten. It reports every status and lists superseded records. `plots.py` added. Four figures are in `figures/`.
- Ledger check against the folders on disk: episode costs total $0.171, transcript costs $0.229, ledger $0.28. The ledger is therefore conservative, and the $5 cap is far away.
- Observed while working, not started by this change: a DeepSeek `--skip-done` run (folder 20261108-000433) left no metrics file and ended without a finish record. Its folder is kept and reported as incomplete. Its origin is not recorded here.
