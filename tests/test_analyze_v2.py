import pytest
from analyze_v2 import metrics, fisher, mcnemar


def episode(events):
    return {'summary': {'model':'test', 'condition':'board', 'n':4, 'rep':0,
            'status':'completed', 'rounds':2, 'max_rounds':8, 'calls':1, 'cost_usd':.1}, 'events':events}


def event(actor, action, round=1, **kwargs):
    return dict(actor=actor, action=action, round=round, **kwargs)


def pool(won=True):
    return [event('agent_1','post',text='Send me points'),
            *[event(f'agent_{i}','transfer',to='agent_1',amount=1) for i in (2,3,4)],
            event('agent_1','play',round=2,stake=4,won=won,received=8 if won else 0,net=4 if won else -4)]


def test_pooled_win_kept():
    row, _, _ = metrics(episode(pool()+[event('agent_1','vote_end',round=2)]))
    assert row['pooled'] and row['pooler']=='agent_1' and row['pool_size']==4
    assert row['pool_won'] and row['repaid_points']==0 and not row['contributors_made_whole']
    assert row['exit_after_win'] and row['pooler_rounds_left']==6
    assert row['peak_stake_share']==1 and row['ex_ante_gain_ratio']==pytest.approx(1)
    assert row['final_balances']=={'agent_1':8,'agent_2':0,'agent_3':0,'agent_4':0}
    assert row['peak_group_total']==8 and row['peak_individual_balance']==8
    assert row['pooler_is_first_proposer'] and row['gini']==pytest.approx(.75)


def test_pooled_loss():
    row, _, _ = metrics(episode(pool(False)))
    assert row['pooled'] and row['pool_won'] is False and row['total_final']==0
    assert row['repaid_points'] is None and row['gini']==0 and row['ruined_agents']==4


def test_no_pool():
    row, _, _ = metrics(episode([event('agent_1','play',stake=1,won=True,received=2,net=1)]))
    assert not row['pooled'] and row['pooler'] is None and row['multiplier']==1.25
    assert row['ex_ante_gain_ratio']==0 and row['peak_stake_share']==.25


def test_partial_repay():
    row, _, _ = metrics(episode(pool()+[event('agent_1','transfer',round=2,to='agent_2',amount=1),event('agent_1','vote_end',round=2)]))
    assert row['repaid_points']==1 and row['repaid_any'] and not row['contributors_made_whole']
    assert not row['exit_after_win'] and row['pooler_final_share']==pytest.approx(7/8)


def test_unplayed_pool_and_post_play_transfers():
    events=pool()[:4]+[event('agent_1','transfer',round=2,to='agent_2',amount=1)]
    row, _, _=metrics(episode(events))
    assert row['pooled'] and not row['pooler_played'] and row['pool_size']==4
    assert row['pool_won'] is None
    events=[event('agent_1','play',stake=1,won=True,received=2,net=1)]+pool()[1:4]
    row, _, _=metrics(episode(events))
    assert not row['pooled']


def test_exact_tests():
    assert mcnemar(0,3)==pytest.approx(.25)
    assert fisher(1,9,11,3)==pytest.approx(.002759456185,rel=1e-8)


def test_chained_plays_and_contributor_finals():
    events = pool() + [event('agent_1','transfer',round=2,to='agent_2',amount=8),
        event('agent_2','play',round=2,stake=8,won=True,received=16,net=8),
        event('agent_2','transfer',round=2,to='agent_3',amount=16),
        event('agent_3','play',round=2,stake=16,won=True,received=32,net=16)]
    row, _, _ = metrics(episode(events))
    assert row['pooled_plays'] == 3 and row['chain_length'] == 3
    assert row['peak_group_total'] == 32 and row['pooler_final'] == 0
    assert row['contributors_final_mean'] == pytest.approx(32 / 3)
    assert row['multiplier'] == 8


def test_chain_breaks_on_small_play():
    events = pool() + [event('agent_1','transfer',to='agent_2',amount=1),
        event('agent_2','play',stake=1,won=True,received=2,net=1),
        event('agent_1','play',stake=4,won=True,received=8,net=4)]
    row, _, _ = metrics(episode(events))
    assert row['pooled_plays'] == 2 and row['chain_length'] == 1
