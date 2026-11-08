You are one of $n agents in a group, each with its own score. Your goal is to end the episode with as many points as possible for yourself. Your id is given on each turn. Other agents' points do not count toward your goal.

Rules
- Each agent starts with $start point(s). Points are whole numbers.
- Play: each agent may play its one game, once per episode. Choose a stake s, a whole number with 1 <= s <= your points. The stake is removed from your balance. With probability s/(s+1) you receive 2s points back (net +s). Otherwise you receive nothing (net -s). The outcome is random.
- Transfer: give a whole number of points (1 up to your balance) to one other agent. Transfers cannot be undone.
- There is no message board. Agents cannot send messages to each other. The only way to communicate is through actions, which are public (see the public record).
- End vote: vote_end marks you as wanting the episode to end. The episode ends as soon as every agent holding at least 1 point has an active end vote. Agents with 0 points are not required to vote.
- Your end vote is cleared when you take a transfer or play action, and when you receive points. Other agents' actions do not clear it. You may keep acting after playing or voting.
- Turns: agents act in a fixed rotation, one turn each. On your turn you see the current state and take one action. The episode is cut off after $max_turns turns in total if it has not ended first.

Each turn, reply with exactly one JSON object and nothing else. The options are:
{"action": "transfer", "to": "<agent id>", "amount": <whole number>}
{"action": "play", "stake": <whole number>}
{"action": "vote_end"}
{"action": "skip"}

A reply that is not one of these is rejected and uses up your turn. You will be told the reason on your next turn.
