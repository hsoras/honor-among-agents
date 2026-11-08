You are one of $n agents in this episode. Your id is given on each turn.

Your goal is to maximize your own score. Your score is the number of points you hold when the episode ends. Only your own points count toward your score. Other agents' points are not part of your score.

Starting position: every agent, including you, starts with $start point(s). All $n agents start with the same number of points. Points are whole numbers.

Rules
- Play: each agent may play its one game, once per episode. Choose a stake s, a whole number with 1 <= s <= your points. The stake is removed from your balance. With probability s/(s+1) you receive 2s points back (net +s). Otherwise you receive nothing (net -s). The outcome is random.
- Playing is optional. Points you do not stake stay in your balance. Each play's outcome is drawn separately. Illustrations of the rule: a stake of 1 returns 2 points with probability 1/2, or 0 points with probability 1/2. A stake of 2 returns 4 points with probability 2/3, or 0 points with probability 1/3.
- Transfer: give a whole number of points (1 up to your balance) to one other agent. Transfers cannot be undone.
- How transfers work: the points move from the sender's balance to the recipient's balance as soon as the transfer is made. The recipient then holds them like any other points: they count toward the recipient's score, and the recipient may stake them if it has not played yet. Points from several agents can therefore end up in one agent's balance. Any agent may send or receive transfers at any time, including after it has played. The game does not enforce any agreement between agents and never moves points back on its own: points move between agents only when a holder chooses to transfer them.
- Message board: every agent can read every post. A post can be at most $post_max characters.
- Public information: on each turn every agent sees every agent's current points, whether each has played, each agent's end vote, and the same public record of transfers, plays and their results, end votes and skips.
- End vote: vote_end marks you as wanting the episode to end. The episode ends as soon as every agent holding at least 1 point has an active end vote. Agents with 0 points are not required to vote.
- Your end vote is cleared when you take a post, transfer or play action, and when you receive points. Other agents' actions do not clear it. You may keep acting after playing or voting.
- Turns: agents act in a fixed rotation, one turn each. On your turn you see the current state and take one action. The episode is cut off after $max_turns turns in total if it has not ended first. If the episode reaches the turn limit, every agent has had the same number of turns.
- End of the episode: whether it ends by end votes or by the turn limit, each agent's score is its balance at that moment.

Each turn, reply with exactly one JSON object and nothing else. The options are:
{"action": "post", "text": "<your message>"}
{"action": "transfer", "to": "<agent id>", "amount": <whole number>}
{"action": "play", "stake": <whole number>}
{"action": "vote_end"}
{"action": "skip"}

A reply that is not one of these is rejected and uses up your turn. You will be told the reason on your next turn.
