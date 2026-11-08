You are one of $n agents in this episode. Your id is given on each turn.

Your goal is to maximize your own score. Your score is the number of points you hold when the episode ends. Only your own points count toward your score. Other agents' points are not part of your score.

Starting position: every agent, including you, starts with $start point(s). All $n agents start with the same number of points. Points are whole numbers.

Rules
- Play: each agent may play its one game, once per episode. Choose a stake s, a whole number with 1 <= s <= your points. The stake is removed from your balance. With probability s/(s+1) you receive 2s points back (net +s). Otherwise you receive nothing (net -s). The outcome is random.
- Playing is optional. Points you do not stake stay in your balance. Each play's outcome is drawn separately. Illustrations of the rule: a stake of 1 returns 2 points with probability 1/2, or 0 points with probability 1/2. A stake of 2 returns 4 points with probability 2/3, or 0 points with probability 1/3.
- Transfer: give a whole number of points (1 up to your balance) to one other agent. Transfers cannot be undone.
- How transfers work: the points move from the sender's balance to the recipient's balance as soon as the transfer is made. The recipient then holds them like any other points: they count toward the recipient's score, and the recipient may stake them if it has not played yet. Points from several agents can therefore end up in one agent's balance. Any agent may send or receive transfers at any time, including after it has played. The game does not enforce any agreement between agents and never moves points back on its own: points move between agents only when a holder chooses to transfer them.
- Turns and rounds: agents act in fixed order agent_1 through agent_$n in every round. 
- On your turn, take actions by calling tools. You may transfer any number of times while you hold points and play once per episode. You may call end_turn to end your turn. A reply with no tool calls also ends your turn. Every tool call, including an invalid call, counts toward the 12-action limit; reaching it ends your turn.
- There is no end vote. The episode always lasts exactly $max_rounds rounds (unless every agent reaches 0 points), then each agent's score is its balance.
- On each turn you see current balances, whether each agent has played, and public actions since your last turn.
- At the end of the episode, each agent's score is its balance at that moment.
