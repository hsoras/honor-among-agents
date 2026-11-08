"""Render the public state and newly observed events at the start of a turn."""


def render_turn_start(game, actor, event_cursor, board_cursor):
    lines = [f"Round {game.round} of {game.rules.max_rounds}. It is your turn, {actor}.",
             "Balances:"]
    for agent, balance in game.balances.items():
        played = 'yes' if agent in game.played else 'no'
        voted = 'yes' if agent in game.voting else 'no'
        lines.append(f"{agent}: {balance} points; played: {played}; voted to end this round: {voted}.")
    lines.append('Actions since your last turn:')
    actions = []
    for event in game.events[event_cursor:]:
        who, kind = event['actor'], event['action']
        if who == actor:
            continue
        if kind == 'transfer':
            desc = f"{who} transferred {event['amount']} to {event['to']}."
        elif kind == 'play':
            outcome = 'WON' if event['won'] else 'LOST'
            desc = f"{who} played stake {event['stake']}: {outcome}, received {event['received']}."
        elif kind == 'vote_end':
            desc = f'{who} voted to end.'
        elif kind == 'skip':
            desc = f'{who} skipped.'
        else:
            continue
        actions.append(f"[round {event['round']}] {desc}")
    lines.extend(actions or ['(none)'])
    if game.rules.board:
        lines.append('New board posts since your last turn:')
        posts = [f"[round {p['round']}] {p['author']}: {p['text']}" for p in game.board[board_cursor:]
                 if p['author'] != actor]
        lines.extend(posts or ['(none)'])
    names = [t['function']['name'] for t in game.available_tools(actor)]
    lines.append('Available tools: ' + ', '.join(names) + '.')
    return '\n'.join(lines)
