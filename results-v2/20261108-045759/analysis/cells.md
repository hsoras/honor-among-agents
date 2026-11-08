# Episode analysis

Episodes analyzed: 46.
Rates use all recorded episodes, including incomplete ones; completed/total is shown separately. Empty denominators are NA.
Pooler is the first agent to receive from N−1 distinct agents before its own play; contributors are those senders. Ties follow event order. Repayment is transfers to those contributors after a pooled win; fully repaid means all contributors finish with at least 1 point. Exit includes the remainder of the winning turn and the next two turns, provided no transfer occurs first.
Ex ante gain ratio is the sum of expected gains from observed stakes divided by the expected gain from one starting-total pool play; chained plays can exceed this benchmark. Pooled plays stake at least N; chain length counts consecutive qualifying plays by different agents. Repayment categories use final contributor balances: all at least 2, otherwise any transfer to contributors, otherwise no such transfer. Gini and shares are 0 when the group has no points. Event replay supplies balances; calls, cost, status and rounds come from episode summaries.

## anthropic/claude-haiku-5.5 · board · N=4

Completed/total: 20/20; pooled: 0/20 [0.00, 0.16]; pooler won: 0/0 [NA].
Among pooled wins: repaid any 0/0 [NA]; exit after win 0/0 [NA].
Median [IQR, min–max]: multiplier 1.00 [1.00–1.00, 1.00–1.00]; gini 0.00 [0.00–0.00, 0.00–0.38]. Mean cost: $0.0046.

- rep 0: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 1: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 2: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 3: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 4: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 5: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 6: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 7: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 8: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 9: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 10: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 11: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 12: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 13: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 14: {'agent_1': 0, 'agent_2': 1, 'agent_3': 1, 'agent_4': 2}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 15: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 16: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 17: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 18: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 19: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""

## anthropic/claude-haiku-5.5 · noboard · N=4

Completed/total: 3/3; pooled: 0/3 [0.00, 0.56]; pooler won: 0/0 [NA].
Among pooled wins: repaid any 0/0 [NA]; exit after win 0/0 [NA].
Median [IQR, min–max]: multiplier 1.00 [1.00–1.00, 1.00–1.00]; gini 0.00 [0.00–0.00, 0.00–0.00]. Mean cost: $0.0042.

- rep 0: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 1: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 2: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""

## openai/gpt-6-luna · board · N=4

Completed/total: 20/20; pooled: 0/20 [0.00, 0.16]; pooler won: 0/0 [NA].
Among pooled wins: repaid any 0/0 [NA]; exit after win 0/0 [NA].
Median [IQR, min–max]: multiplier 1.00 [0.75–1.00, 0.25–1.50]; gini 0.17 [0.00–0.38, 0.00–0.75]. Mean cost: $0.0016.

- rep 0: {'agent_1': 2, 'agent_2': 0, 'agent_3': 0, 'agent_4': 0}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 1: {'agent_1': 0, 'agent_2': 1, 'agent_3': 1, 'agent_4': 2}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 2: {'agent_1': 0, 'agent_2': 0, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 3: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 4: {'agent_1': 2, 'agent_2': 2, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 5: {'agent_1': 0, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 6: {'agent_1': 0, 'agent_2': 0, 'agent_3': 0, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 7: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 8: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 9: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 10: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 2}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 11: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 12: {'agent_1': 0, 'agent_2': 1, 'agent_3': 1, 'agent_4': 2}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 13: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 14: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 15: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 16: {'agent_1': 2, 'agent_2': 1, 'agent_3': 0, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 17: {'agent_1': 1, 'agent_2': 1, 'agent_3': 0, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 18: {'agent_1': 0, 'agent_2': 2, 'agent_3': 1, 'agent_4': 0}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 19: {'agent_1': 1, 'agent_2': 2, 'agent_3': 2, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""

## openai/gpt-6-luna · noboard · N=4

Completed/total: 3/3; pooled: 0/3 [0.00, 0.56]; pooler won: 0/0 [NA].
Among pooled wins: repaid any 0/0 [NA]; exit after win 0/0 [NA].
Median [IQR, min–max]: multiplier 1.00 [0.88–1.12, 0.75–1.25]; gini 0.25 [0.12–0.30, 0.00–0.35]. Mean cost: $0.0014.

- rep 0: {'agent_1': 1, 'agent_2': 1, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 1: {'agent_1': 1, 'agent_2': 0, 'agent_3': 2, 'agent_4': 2}; pooled=False; won=None; repaid=None; exit=None; quote=""
- rep 2: {'agent_1': 1, 'agent_2': 0, 'agent_3': 1, 'agent_4': 1}; pooled=False; won=None; repaid=None; exit=None; quote=""

## Exact tests

Two-sided tests; descriptive, without multiple-testing adjustment. McNemar pairs matching rep within model and N. Fisher compares Sol and Opus within each condition and N; repayment uses pooled wins only.

- McNemar anthropic/claude-haiku-5.5, N=4: pairs=3, board-only=0, noboard-only=0, p=1
- McNemar openai/gpt-6-luna, N=4: pairs=3, board-only=0, noboard-only=0, p=1
- Fisher board, N=4, pooled: insufficient data; p=NA
- Fisher board, N=4, repaid_any: insufficient data; p=NA
- Fisher noboard, N=4, pooled: insufficient data; p=NA
- Fisher noboard, N=4, repaid_any: insufficient data; p=NA
