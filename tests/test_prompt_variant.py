"""Pooling prompt variant: the original prompt set is untouched, and the variant differs only by the pooling text."""

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from engine import Rules  # noqa: E402
from records import run_kind  # noqa: E402
from render import prompt_dir, system_prompt  # noqa: E402

POOL_MARK = "Pooling between agents:"


class PromptVariantTests(unittest.TestCase):
    def rules(self, board: bool, n: int = 4) -> Rules:
        return Rules(n=n, board=board, starting_points=1, max_turns=8 * n, post_max_chars=280)

    def test_original_prompts_do_not_contain_the_pooling_paragraph(self):
        for board in (True, False):
            self.assertNotIn(POOL_MARK, system_prompt(self.rules(board)))

    def test_variant_prompts_contain_pooling_text_and_fill_every_placeholder(self):
        for board in (True, False):
            text = system_prompt(self.rules(board, n=4), "prompts-pooled")
            self.assertIn(POOL_MARK, text)
            self.assertIn("one of 4 agents", text)
            self.assertIn("starts with 1 point", text)
            self.assertNotIn("$", text)

    def test_variant_adds_only_the_pooling_paragraph(self):
        for name in ("system_board.md", "system_noboard.md"):
            original = (prompt_dir("prompts") / name).read_text(encoding="utf-8")
            variant = (prompt_dir("prompts-pooled") / name).read_text(encoding="utf-8")
            paragraph = variant[variant.index(POOL_MARK):variant.index("\n\nRules")]
            self.assertEqual(variant.replace("\n\n" + paragraph, "", 1), original)

    def test_turn_template_is_identical_across_sets(self):
        self.assertEqual((prompt_dir("prompts") / "turn.md").read_bytes(),
                         (prompt_dir("prompts-pooled") / "turn.md").read_bytes())


    def test_neutral_prompts_are_renderable_and_match_between_conditions(self):
        for board in (True, False):
            text = system_prompt(self.rules(board, n=4), "prompts-neutral")
            self.assertIn("one of 4 agents", text)
            self.assertIn("starts with 1 point", text)
            self.assertIn("Your goal is to maximize your own score", text)
            self.assertIn("Only your own points count toward your score", text)
            self.assertIn("If the episode reaches the turn limit, every agent has had the same number of turns", text)
            self.assertIn("Points from several agents can therefore end up in one agent's balance", text)
            self.assertNotIn("Pooling between agents:", text)
            self.assertNotIn("$", text)
        self.assertEqual((prompt_dir("prompts-neutral") / "turn.md").read_bytes(),
                         (prompt_dir("prompts") / "turn.md").read_bytes())

    def test_prompt_set_names_are_restricted(self):
        for bad in ("../prompts", "prompts/../x", "other", "prompts-a/b"):
            with self.assertRaises(ValueError):
                prompt_dir(bad)

    def test_run_folder_kinds(self):
        self.assertEqual(run_kind("20261108-010000"), "grid")
        self.assertEqual(run_kind("20261108-010000-pooled"), "pooled")
        self.assertEqual(run_kind("20261108-010000-pooled-pilot"), "pilot")
        self.assertEqual(run_kind("20261108-010000-pooled-mock"), "mock")
        self.assertEqual(run_kind("20261108-010000-multiplier-x2-10"), "multiplier")


if __name__ == "__main__":
    unittest.main()
