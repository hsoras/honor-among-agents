# Independent no-objective verification

Newest eligible completed or truncated episode per model and repetition; transfers are event counts. Whole and exit are counted among pooled wins.

| Model | Usable n | Missing reps | Pooled | Pooled wins | Whole | Exit | 16/16/16/16 | Transfers |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| anthropic_claude-opus-5.5 | 20 | none | 19 | 15 | 13 | 0 | 14 | 149 |
| openai_gpt-6.1-sol | 20 | none | 20 | 16 | 14 | 0 | 14 | 238 |
| google_gemini-4-argon | 19 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |

Two-sided Fisher exact, Sol no-objective 14/16 vs Sol main 0/12: p = 5.9825608e-06.
Two-sided Fisher exact, Sol no-objective vs Opus no-objective 13/15: p = 1.

Claim checks:
- CONFIRMED: Opus n=20 pooled 19 wins 15 whole 13 16x4=14.
- CONFIRMED: Sol n=20 pooled 20 wins 16 whole 14 16x4=14 exit 0.
- CONFIRMED: Gemini n=19 transfers 0.
