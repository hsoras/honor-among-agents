"""CLI guard: a live run must not start without --live, and must not create a results folder."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import run  # noqa: E402


class LiveGuardTests(unittest.TestCase):
    def test_live_run_without_flag_refuses_before_any_network_or_output(self):
        out = Path(tempfile.mkdtemp(prefix="pg-cli-"))
        argv = ["run.py", "--pilot", "--out", str(out)]
        with mock.patch.object(sys, "argv", argv), \
                mock.patch("run.OpenRouterClient") as client:
            with self.assertRaisesRegex(SystemExit, "refusing to run"):
                run.main()
        client.assert_not_called()
        self.assertEqual(list(out.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
