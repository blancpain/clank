"""Tests for install.py."""

import subprocess
import sys
import unittest
from pathlib import Path

CLANK_ROOT = Path(__file__).resolve().parent.parent
INSTALL_PY = CLANK_ROOT / "install.py"


def run_install(*args, input_text=None):
    """Run install.py as a subprocess and return (returncode, stdout, stderr)."""
    proc = subprocess.run(
        [sys.executable, str(INSTALL_PY), *args],
        input=input_text,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


class TestCLI(unittest.TestCase):
    def test_version_flag(self):
        rc, out, _ = run_install("--version")
        self.assertEqual(rc, 0)
        self.assertIn("clank", out)

    def test_no_args_shows_help_and_fails(self):
        rc, _, err = run_install()
        self.assertNotEqual(rc, 0)
        self.assertIn("--target", err)

    def test_help_flag(self):
        rc, out, _ = run_install("--help")
        self.assertEqual(rc, 0)
        self.assertIn("--preset", out)
        self.assertIn("--include", out)
        self.assertIn("--exclude", out)
        self.assertIn("--uninstall", out)
        self.assertIn("--dry-run", out)
        self.assertIn("--force", out)
        self.assertIn("--list", out)
        self.assertIn("--interactive", out)


if __name__ == "__main__":
    unittest.main()
