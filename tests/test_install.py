"""Tests for install.py."""

import subprocess
import sys
import unittest
from pathlib import Path

CLANK_ROOT = Path(__file__).resolve().parent.parent
INSTALL_PY = CLANK_ROOT / "install.py"
sys.path.insert(0, str(CLANK_ROOT))
import install  # noqa: E402,F401


FIXTURES = CLANK_ROOT / "tests" / "fixtures"


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


class TestManifestLoading(unittest.TestCase):
    def test_load_valid_manifest(self):
        m = install.Manifest.load(FIXTURES / "manifest_valid.toml")
        self.assertEqual(m.version, 1)
        self.assertIn("stub-agent", m.artifacts)
        self.assertIn("stub-hook", m.artifacts)
        self.assertEqual(m.artifacts["stub-agent"]["type"], "agent")
        self.assertIn("minimal", m.presets)
        self.assertEqual(m.presets["minimal"], ["stub-agent"])


class TestManifestLint(unittest.TestCase):
    def test_valid_manifest_lints_clean(self):
        m = install.Manifest.load(FIXTURES / "manifest_valid.toml")
        errors = install.lint_manifest(m, FIXTURES)
        self.assertEqual(errors, [])

    def test_duplicate_ids_rejected(self):
        m = install.Manifest.load(FIXTURES / "manifest_bad_dup_id.toml")
        errors = install.lint_manifest(m, FIXTURES)
        self.assertTrue(any("duplicate" in e for e in errors))

    def test_missing_path_rejected(self):
        m = install.Manifest.load(FIXTURES / "manifest_bad_missing_path.toml")
        errors = install.lint_manifest(m, FIXTURES)
        self.assertTrue(any("does not exist" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
