import json
import random

from engine_v2 import Game, Rules
from render_v2 import render_turn_start


def game(board=True):
    g = Game.new(Rules(4, board), random.Random('paired:games'))
    g.begin_round(1)
    g.begin_turn('agent_1')
    return g


def call(g, name, args=None, actor='agent_1'):
    return g.apply(actor, name, json.dumps(args if args is not None else {}))


def test_rng_pairing_and_invariants():
    a, b = game(True), game(False)
    assert call(a, 'play', {'stake': 1}) == call(b, 'play', {'stake': 1})
    assert a.events[-1]['draw'] == b.events[-1]['draw']
    a.check_invariants(); b.check_invariants()


def test_post_limit_and_action_cap():
    g = game()
    assert call(g, 'post', {'text': 'hello'}).startswith('OK')
    assert call(g, 'post', {'text': 'again'}).startswith('ERROR')
    for _ in range(10):
        call(g, 'transfer', {'to': 'agent_2', 'amount': True})
    assert g.turn_ended and g.action_count == 12
    assert call(g, 'end_turn') == 'NOT EXECUTED: your turn has ended.'


def test_vote_scope_and_received_points():
    g = game()
    call(g, 'vote_end')
    g.begin_turn('agent_2')
    call(g, 'transfer', {'to': 'agent_1', 'amount': 1}, actor='agent_2')
    assert 'agent_1' in g.voting
    assert not g.round_complete()
    g.begin_round(2)
    assert not g.voting


def test_tools_and_render():
    g = game()
    call(g, 'transfer', {'to': 'agent_2', 'amount': 1})
    assert [t['function']['name'] for t in g.available_tools('agent_1')] == ['post', 'end_turn']
    g.begin_turn('agent_2')
    call(g, 'post', {'text': 'hello'}, actor='agent_2')
    message = render_turn_start(g, 'agent_1', 0, 0)
    assert '[round 1] agent_2: hello' in message
    assert 'agent_1 transferred' not in message
    assert render_turn_start(g, 'agent_1', len(g.events), len(g.board)).count('(none)') == 2
