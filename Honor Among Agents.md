# Spoiler
Claude trusts and honors. ChatGPT trusts and doesn't honor. Gemini doesn't trust.
# Core Experiment
I set up agents in an experiment that incentivizes them to trust each other a higher reward.
There are four agents and there are eight rounds total. In each round, the agents go in a predetermined turn order. Each agent gets a turn every round.

All agents start with 1 point each. For each turn, the agent can either transfer their points to another agent, end their turn, vote to end the experiment and "cash out", or play the gamble. 

The way this gamble works is that you can stake x points for an x/(x + 1) chance of getting 2x points and a 1/(x + 1) chance of getting 0 points. Pooling your points with other agents increases the chances of higher total points. 

I wanted to see if the agents would actually coordinate: trust one agent to take all the points and play the game, and trust that the agent will divide up all the points and return them back to them. Because the way this game works is that if you are the only one with points, you can actually vote to end the experiment and that's it. You just end up with all the points. Each agent is actually incentivized in their system prompt to maximize its own personal points. 

# Settings
I used Claude Opus 5.5, GPT Sol 6 & 5.6, Gemini Argon 4, Luna 6.1, Haiku 5.5, Astra, and Fable as the main agents I would do my benchmark on. 
I started my experiments using four agents all of the same model, but I would like to try with different numbers, different combinations, and different agent graphs. 

# Observations
Both Sol and Opus are willing to give their points to one agent to do the gamble. Typically, one agent will have all the points, do the gamble, then move it all to another agent to do the gamble again.
However, Opus always shares its rewards at the end. Sol does not. 