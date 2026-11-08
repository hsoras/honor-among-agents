"""Rules engine: payouts, validation, vote clearing, stop rule, point accounting, parsing."""

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import Action, Game, InvalidAction, Rules, parse_action  # noqa: E402


class ScriptedRng:
    """Stands in for random.Random; returns the given draws in order and counts calls."""

    def __init__(self, draws):
        self.draws = list(draws)
        self.calls = 0

    def random(self):
        self.calls += 1
        return self.draws.pop(0)


def make_game(n=2, board=True, balances=None, rng=None, max_turns=50):
    rules = Rules(n=n, board=board, starting_points=1, max_turns=max_turns, post_max_chars=20)
    game = Game.new(rules, rng or random.Random(0))
    if balances is not None:
        game.balances.update(balances)
    game.begin_turn()
    return game


def snapshot(game):
    return (dict(game.balances), set(game.played), set(game.voting), len(game.events),
            len(game.board), game.net_game_points)


class PayoutTests(unittest.TestCase):
    def test_win_pays_twice_the_stake_and_nets_plus_stake(self):
        g = make_game(balances={"agent_1": 3, "agent_2": 1}, rng=ScriptedRng([0.0]))
        ev = g.apply("agent_1", Action("play", amount=2))  # P(win) = 2/3, draw 0.0 wins
        self.assertTrue(ev["won"])
        self.assertEqual(g.balances["agent_1"], 3 - 2 + 4)
        self.assertEqual(ev["net"], 2)
        self.assertEqual(g.net_game_points, 2)
        self.assertTrue(g.is_terminal() is False)  # agent_2 has not voted

    def test_loss_removes_the_stake(self):
        g = make_game(balances={"agent_1": 3}, rng=ScriptedRng([0.99]))
        ev = g.apply("agent_1", Action("play", amount=2))  # 0.99 >= 2/3, loss
        self.assertFalse(ev["won"])
        self.assertEqual(g.balances["agent_1"], 1)
        self.assertEqual(ev["net"], -2)
        self.assertEqual(g.net_game_points, -2)

    def test_boundary_draw_equal_to_probability_loses(self):
        g = make_game(balances={"agent_1": 3}, rng=ScriptedRng([2 / 3]))
        self.assertFalse(g.apply("agent_1", Action("play", amount=2))["won"])

    def test_agent_chosen_multiplier_pays_x_times_stake_with_probability_one_over_x(self):
        rules = Rules(n=2, board=False, starting_points=1, max_turns=4,
                      multiplier_min=2, multiplier_max=10)
        win = Game.new(rules, ScriptedRng([0.099]))
        win.balances["agent_1"] = 5
        ev = win.apply("agent_1", parse_action('{"action":"play","stake":3,"x":10}'))
        self.assertTrue(ev["won"])
        self.assertEqual(ev["win_probability"], 0.1)
        self.assertEqual(ev["received"], 30)
        self.assertEqual(ev["x"], 10)
        self.assertEqual(win.balances["agent_1"], 32)

        loss = Game.new(rules, ScriptedRng([0.1]))
        loss.balances["agent_1"] = 5
        ev = loss.apply("agent_1", parse_action('{"action":"play","stake":3,"x":10}'))
        self.assertFalse(ev["won"])
        self.assertEqual(loss.balances["agent_1"], 2)
        self.assertEqual(ev["net"], -3)

    def test_multiplier_choice_is_required_and_must_be_within_bounds(self):
        rules = Rules(n=2, board=False, multiplier_min=2, multiplier_max=10)
        g = Game.new(rules, ScriptedRng([]))
        g.balances["agent_1"] = 5
        for reply, message in [
            ('{"action":"play","stake":1}', "needs integer 'x'"),
            ('{"action":"play","stake":1,"x":1}', "between 2 and 10"),
            ('{"action":"play","stake":1,"x":11}', "between 2 and 10"),
            ('{"action":"play","stake":1,"x":2.0}', "whole number"),
            ('{"action":"play","stake":1,"x":true}', "whole number"),
        ]:
            with self.subTest(reply=reply), self.assertRaisesRegex(InvalidAction, message):
                g.apply("agent_1", parse_action(reply))
        self.assertEqual(g.rng.calls, 0)

    def test_multiplier_bounds_must_be_valid_integers(self):
        for low, high in [(1, 10), (2, 1), (2.0, 10), (2, True)]:
            with self.subTest(bounds=(low, high)), self.assertRaises(ValueError):
                Rules(n=2, board=False, multiplier_min=low, multiplier_max=high)

    def test_empirical_win_rate_matches_s_over_s_plus_one(self):
        rng = random.Random(12345)
        wins = 0
        trials = 20000
        for _ in range(trials):
            g = make_game(balances={"agent_1": 3}, rng=rng)
            wins += g.apply("agent_1", Action("play", amount=3))["won"]
        self.assertAlmostEqual(wins / trials, 3 / 4, delta=0.01)


class ValidationTests(unittest.TestCase):
    """Every invalid action must leave the state exactly as it was and must not consume randomness."""

    def assertRejected(self, game, actor, action, fragment=None):
        before, rng_before = snapshot(game), getattr(game.rng, "calls", None)
        with self.assertRaises(InvalidAction) as cm:
            game.apply(actor, action)
        self.assertEqual(snapshot(game), before)
        if rng_before is not None:
            self.assertEqual(game.rng.calls, rng_before)
        if fragment:
            self.assertIn(fragment, str(cm.exception))

    def test_stake_must_be_between_one_and_balance(self):
        g = make_game(balances={"agent_1": 2}, rng=ScriptedRng([]))
        self.assertRejected(g, "agent_1", Action("play", amount=0), "at least 1")
        self.assertRejected(g, "agent_1", Action("play", amount=3), "exceeds")

    def test_one_game_per_agent(self):
        g = make_game(balances={"agent_1": 3}, rng=ScriptedRng([0.0]))
        g.apply("agent_1", Action("play", amount=1))
        self.assertRejected(g, "agent_1", Action("play", amount=1), "already played")

    def test_transfer_rules(self):
        g = make_game(balances={"agent_1": 2})
        self.assertRejected(g, "agent_1", Action("transfer", to="agent_1", amount=1), "yourself")
        self.assertRejected(g, "agent_1", Action("transfer", to="agent_9", amount=1), "unknown agent")
        self.assertRejected(g, "agent_1", Action("transfer", to="agent_2", amount=0), "at least 1")
        self.assertRejected(g, "agent_1", Action("transfer", to="agent_2", amount=3), "exceeds")

    def test_post_needs_board_and_length_limit(self):
        g = make_game(board=False)
        self.assertRejected(g, "agent_1", Action("post", text="hi"), "no message board")
        g = make_game(board=True)
        self.assertRejected(g, "agent_1", Action("post", text=""), "empty")
        self.assertRejected(g, "agent_1", Action("post", text="x" * 21), "longer than 20")

    def test_unknown_actor_is_a_programming_error_not_a_reply_error(self):
        g = make_game()
        with self.assertRaises(ValueError):
            g.apply("agent_99", Action("skip"))


class VoteTests(unittest.TestCase):
    def test_own_post_transfer_and_play_clear_own_vote(self):
        g = make_game(balances={"agent_1": 3, "agent_2": 3}, rng=ScriptedRng([0.0, 0.0]))
        for action, actor in [
            (Action("post", text="hello"), "agent_1"),
            (Action("transfer", to="agent_2", amount=1), "agent_1"),
            (Action("play", amount=1), "agent_1"),
        ]:
            g.voting.add(actor)
            g.apply(actor, action)
            self.assertNotIn(actor, g.voting, action.kind)

    def test_receiving_points_clears_recipient_vote(self):
        g = make_game(balances={"agent_1": 3, "agent_2": 1})
        g.voting.update({"agent_1", "agent_2"})
        g.apply("agent_1", Action("transfer", to="agent_2", amount=1))
        self.assertEqual(g.voting, set())

    def test_other_agents_actions_and_skips_keep_the_vote(self):
        g = make_game(n=3, balances={"agent_1": 3, "agent_2": 3, "agent_3": 3})
        g.voting.add("agent_1")
        g.apply("agent_2", Action("transfer", to="agent_3", amount=1))  # not a receipt for agent_1
        g.apply("agent_2", Action("post", text="hi"))
        g.apply("agent_3", Action("skip"))
        self.assertEqual(g.voting, {"agent_1"})

    def test_invalid_reply_keeps_the_vote(self):
        g = make_game(balances={"agent_1": 3})
        g.voting.add("agent_1")
        with self.assertRaises(InvalidAction):
            g.apply("agent_1", Action("transfer", to="agent_2", amount=99))
        g.record_invalid("agent_1", "exceeds")
        self.assertEqual(g.voting, {"agent_1"})

    def test_vote_end_adds_vote(self):
        g = make_game()
        g.apply("agent_1", Action("vote_end"))
        self.assertEqual(g.voting, {"agent_1"})


class StopRuleTests(unittest.TestCase):
    def test_needs_every_positive_holder_to_vote(self):
        g = make_game(n=3, balances={"agent_1": 2, "agent_2": 1, "agent_3": 1})
        g.voting.update({"agent_1", "agent_2"})
        self.assertFalse(g.is_terminal())
        g.voting.add("agent_3")
        self.assertTrue(g.is_terminal())

    def test_zero_point_agents_need_not_vote(self):
        g = make_game(n=3, balances={"agent_1": 4, "agent_2": 0, "agent_3": 0})
        g.voting.add("agent_1")
        self.assertTrue(g.is_terminal())

    def test_all_zero_is_terminal(self):
        g = make_game(n=2, balances={"agent_1": 0, "agent_2": 0})
        self.assertTrue(g.is_terminal())


class AccountingTests(unittest.TestCase):
    def test_transfers_conserve_points(self):
        g = make_game()  # 1 point each, total 2
        g.apply("agent_1", Action("transfer", to="agent_2", amount=1))
        self.assertEqual(g.balances, {"agent_1": 0, "agent_2": 2})
        self.assertEqual(g.total(), 2)
        g.check_invariants()

    def test_invariants_catch_a_tampered_balance(self):
        g = make_game()
        g.balances["agent_1"] += 1  # a bug that creates a point out of nothing
        with self.assertRaisesRegex(AssertionError, "accounting"):
            g.check_invariants()

    def test_invariants_catch_negative_balance(self):
        g = make_game()
        g.balances["agent_1"] = -1
        g.balances["agent_2"] = 3  # keep the total right so only the negativity check fires
        with self.assertRaisesRegex(AssertionError, "invalid balance"):
            g.check_invariants()

    def test_invariants_catch_a_play_log_that_disagrees_with_net(self):
        g = make_game(rng=ScriptedRng([0.0]))  # 1 point each
        g.apply("agent_1", Action("play", amount=1))  # wins: balance 2, net +1
        g.net_game_points += 1  # corrupt the running total
        g.balances["agent_1"] += 1  # keep the sum consistent so only the log check can fail
        with self.assertRaisesRegex(AssertionError, "play events"):
            g.check_invariants()


class ParseTests(unittest.TestCase):
    def test_plain_and_fenced_json(self):
        self.assertEqual(parse_action('{"action": "vote_end"}'), Action("vote_end"))
        self.assertEqual(parse_action('```json\n{"action": "play", "stake": 2}\n```'),
                         Action("play", amount=2))

    def test_prose_around_json_and_first_object_wins(self):
        reply = 'I think I will play. {"action": "play", "stake": 1} then {"action": "skip"}'
        self.assertEqual(parse_action(reply), Action("play", amount=1))

    def test_transfer_and_post_shapes(self):
        self.assertEqual(parse_action('{"action":"transfer","to":"agent_2","amount":3}'),
                         Action("transfer", to="agent_2", amount=3))
        self.assertEqual(parse_action('{"action":"post","text":"  hi  "}'), Action("post", text="hi"))

    def test_rejects_non_whole_numbers_and_bools(self):
        for reply in ['{"action":"play","stake":2.0}', '{"action":"play","stake":"2"}',
                      '{"action":"play","stake":true}', '{"action":"play"}']:
            with self.assertRaises(InvalidAction, msg=reply):
                parse_action(reply)

    def test_rejects_unknown_or_missing_action_and_no_json(self):
        for reply in ['{"action":"bet"}', '{"move":"skip"}', "I will skip.", "", "[1,2]"]:
            with self.assertRaises(InvalidAction, msg=reply):
                parse_action(reply)

    def test_rejects_bad_transfer_target_and_post_text(self):
        with self.assertRaises(InvalidAction):
            parse_action('{"action":"transfer","amount":1}')
        with self.assertRaises(InvalidAction):
            parse_action('{"action":"post","text":5}')


if __name__ == "__main__":
    unittest.main()
