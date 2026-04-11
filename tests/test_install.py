"""Tests for install.py."""

import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


class TestSelectionResolution(unittest.TestCase):
    def setUp(self):
        self.manifest = install.Manifest.load(FIXTURES / "manifest_valid.toml")

    def test_resolve_preset_minimal(self):
        selected = install.resolve_selection(self.manifest, preset="minimal")
        self.assertEqual(selected, {"stub-agent"})

    def test_resolve_tag_star(self):
        selected = install.resolve_selection(self.manifest, preset="all")
        self.assertEqual(selected, {"stub-agent", "stub-hook"})

    def test_resolve_include_only(self):
        selected = install.resolve_selection(self.manifest, include=["stub-hook"])
        self.assertEqual(selected, {"stub-hook"})

    def test_resolve_preset_plus_include(self):
        selected = install.resolve_selection(
            self.manifest, preset="minimal", include=["stub-hook"]
        )
        self.assertEqual(selected, {"stub-agent", "stub-hook"})

    def test_resolve_preset_minus_exclude(self):
        selected = install.resolve_selection(
            self.manifest, preset="all", exclude=["stub-hook"]
        )
        self.assertEqual(selected, {"stub-agent"})

    def test_resolve_unknown_preset_raises(self):
        with self.assertRaises(ValueError):
            install.resolve_selection(self.manifest, preset="nonexistent")

    def test_resolve_unknown_include_raises(self):
        with self.assertRaises(ValueError):
            install.resolve_selection(self.manifest, include=["nonexistent"])


class TestSafetyChecks(unittest.TestCase):
    def test_nonexistent_target_raises(self):
        with self.assertRaises(install.InstallError):
            install.check_target(Path("/nonexistent/path/to/target"))

    def test_target_is_clank_itself_raises(self):
        with self.assertRaises(install.InstallError) as ctx:
            install.check_target(CLANK_ROOT)
        self.assertIn("clank itself", str(ctx.exception))

    def test_valid_target_creates_claude_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            install.check_target(target)
            self.assertTrue((target / ".claude").is_dir())

    def test_nonexistent_target_with_existing_parent_is_created(self):
        # First-time `curl | sh` installs into a fresh project dir: the
        # user shouldn't have to mkdir beforehand. check_target should
        # create the target when its parent is a directory.
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "new-project"
            self.assertFalse(target.exists())
            install.check_target(target)
            self.assertTrue(target.is_dir())
            self.assertTrue((target / ".claude").is_dir())

    def test_nonexistent_target_in_dry_run_is_not_created(self):
        # Dry-run must not touch the filesystem, even for the auto-create
        # path. The notice is printed to stderr; nothing gets written.
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "preview-only"
            install.check_target(target, dry_run=True)
            self.assertFalse(target.exists())


class TestCopyArtifact(unittest.TestCase):
    def setUp(self):
        self.manifest = install.Manifest.load(FIXTURES / "manifest_valid.toml")
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)
        (self.target / ".claude").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_copy_agent_file(self):
        install.copy_artifact(
            self.manifest.artifacts["stub-agent"],
            FIXTURES,
            self.target,
            on_conflict=lambda dst: "overwrite",
        )
        dst = self.target / ".claude/agents/stub-agent.md"
        self.assertTrue(dst.exists())
        self.assertIn("Stub body", dst.read_text())

    def test_copy_hook_is_executable(self):
        install.copy_artifact(
            self.manifest.artifacts["stub-hook"],
            FIXTURES,
            self.target,
            on_conflict=lambda dst: "overwrite",
        )
        dst = self.target / ".claude/hooks/stub-hook.sh"
        self.assertTrue(dst.exists())
        self.assertTrue(dst.stat().st_mode & 0o111)

    def test_skip_on_conflict(self):
        dst = self.target / ".claude/agents/stub-agent.md"
        dst.parent.mkdir(parents=True)
        dst.write_text("preexisting content")
        install.copy_artifact(
            self.manifest.artifacts["stub-agent"],
            FIXTURES,
            self.target,
            on_conflict=lambda dst: "skip",
        )
        self.assertEqual(dst.read_text(), "preexisting content")

    def test_overwrite_on_conflict(self):
        dst = self.target / ".claude/agents/stub-agent.md"
        dst.parent.mkdir(parents=True)
        dst.write_text("preexisting content")
        install.copy_artifact(
            self.manifest.artifacts["stub-agent"],
            FIXTURES,
            self.target,
            on_conflict=lambda dst: "overwrite",
        )
        self.assertIn("Stub body", dst.read_text())


class TestSettingsMerge(unittest.TestCase):
    def test_merge_into_empty(self):
        target = {}
        fragment = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": "/a.sh"}],
                    }
                ]
            }
        }
        result = install.merge_settings(target, fragment)
        self.assertEqual(result["hooks"]["PreToolUse"][0]["matcher"], "Bash")
        self.assertEqual(
            result["hooks"]["PreToolUse"][0]["hooks"][0]["command"], "/a.sh"
        )

    def test_merge_append_to_existing_matcher(self):
        target = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": "/existing.sh"}],
                    }
                ]
            }
        }
        fragment = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": "/new.sh"}],
                    }
                ]
            }
        }
        result = install.merge_settings(target, fragment)
        cmds = [h["command"] for h in result["hooks"]["PreToolUse"][0]["hooks"]]
        self.assertEqual(cmds, ["/existing.sh", "/new.sh"])

    def test_merge_dedupes_by_command(self):
        target = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": "/a.sh"}],
                    }
                ]
            }
        }
        fragment = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": "/a.sh"}],
                    }
                ]
            }
        }
        result = install.merge_settings(target, fragment)
        hooks = result["hooks"]["PreToolUse"][0]["hooks"]
        self.assertEqual(len(hooks), 1)

    def test_merge_new_matcher(self):
        target = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": "/a.sh"}],
                    }
                ]
            }
        }
        fragment = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Edit|Write",
                        "hooks": [{"type": "command", "command": "/b.sh"}],
                    }
                ]
            }
        }
        result = install.merge_settings(target, fragment)
        self.assertEqual(len(result["hooks"]["PreToolUse"]), 2)

    def test_merge_permissions_allow_union(self):
        target = {"permissions": {"allow": ["Bash(ls:*)"]}}
        fragment = {"permissions": {"allow": ["Bash(git status)", "Bash(ls:*)"]}}
        result = install.merge_settings(target, fragment)
        self.assertEqual(
            sorted(result["permissions"]["allow"]),
            ["Bash(git status)", "Bash(ls:*)"],
        )


class TestReceipt(unittest.TestCase):
    def test_write_and_read_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / ".claude").mkdir()
            install.write_receipt(
                target,
                artifacts=["stub-agent", "stub-hook"],
                clank_version="0.1.0",
                clank_commit="abc123",
            )
            receipt = install.read_receipt(target)
            self.assertEqual(
                sorted(receipt["artifacts"]),
                ["stub-agent", "stub-hook"],
            )
            self.assertEqual(receipt["clank_version"], "0.1.0")
            self.assertEqual(receipt["clank_commit"], "abc123")
            self.assertIn("installed_at", receipt)

    def test_read_receipt_missing_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / ".claude").mkdir()
            receipt = install.read_receipt(target)
            self.assertEqual(receipt, {"artifacts": []})


class TestUninstall(unittest.TestCase):
    def setUp(self):
        self.manifest = install.Manifest.load(FIXTURES / "manifest_valid.toml")
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)
        (self.target / ".claude").mkdir()
        for aid in ["stub-agent", "stub-hook"]:
            install.copy_artifact(
                self.manifest.artifacts[aid],
                FIXTURES,
                self.target,
                on_conflict=lambda dst: "overwrite",
            )
        frag = json.loads(
            (FIXTURES / "base/settings.fragments/stub-hook.json").read_text()
        )
        target_settings = install.merge_settings({}, frag)
        (self.target / ".claude/settings.json").write_text(
            json.dumps(target_settings, indent=2)
        )
        install.write_receipt(self.target, ["stub-agent", "stub-hook"], "0.1.0", "test")

    def tearDown(self):
        self.tmp.cleanup()

    def test_uninstall_removes_file(self):
        install.uninstall(self.manifest, FIXTURES, self.target, ["stub-agent"])
        self.assertFalse((self.target / ".claude/agents/stub-agent.md").exists())

    def test_uninstall_updates_receipt(self):
        install.uninstall(self.manifest, FIXTURES, self.target, ["stub-agent"])
        receipt = install.read_receipt(self.target)
        self.assertEqual(receipt["artifacts"], ["stub-hook"])

    def test_uninstall_strips_settings_fragment(self):
        install.uninstall(self.manifest, FIXTURES, self.target, ["stub-hook"])
        settings = json.loads((self.target / ".claude/settings.json").read_text())
        bash_hooks = [
            e
            for e in settings.get("hooks", {}).get("PreToolUse", [])
            if e.get("matcher") == "Bash"
        ]
        all_cmds = []
        for e in bash_hooks:
            all_cmds.extend(h["command"] for h in e.get("hooks", []))
        self.assertNotIn("$CLAUDE_PROJECT_DIR/.claude/hooks/stub-hook.sh", all_cmds)


class TestFullInstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_install_preset_minimal_clean(self):
        install.install(
            manifest_path=FIXTURES / "manifest_valid.toml",
            clank_root=FIXTURES,
            target=self.target,
            preset="minimal",
            include=[],
            exclude=[],
            conflict_policy="overwrite",
            dry_run=False,
            stop_hook_opt_in=False,
            clank_version="test",
            clank_commit="testcommit",
        )
        self.assertTrue((self.target / ".claude/agents/stub-agent.md").exists())
        receipt = install.read_receipt(self.target)
        self.assertEqual(receipt["artifacts"], ["stub-agent"])

    def test_install_over_existing_preserves_unrelated(self):
        (self.target / ".claude").mkdir()
        preexisting = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Read",
                        "hooks": [{"type": "command", "command": "/unrelated.sh"}],
                    }
                ]
            },
            "permissions": {"allow": ["Bash(echo hi)"]},
            "enabledPlugins": {"existing-plugin": True},
        }
        (self.target / ".claude/settings.json").write_text(
            json.dumps(preexisting, indent=2)
        )

        install.install(
            manifest_path=FIXTURES / "manifest_valid.toml",
            clank_root=FIXTURES,
            target=self.target,
            preset="test-both",
            include=[],
            exclude=[],
            conflict_policy="overwrite",
            dry_run=False,
            stop_hook_opt_in=False,
            clank_version="test",
            clank_commit="testcommit",
        )

        settings = json.loads((self.target / ".claude/settings.json").read_text())
        read_entry = next(
            e for e in settings["hooks"]["PreToolUse"] if e["matcher"] == "Read"
        )
        self.assertEqual(read_entry["hooks"][0]["command"], "/unrelated.sh")
        self.assertIn("Bash(echo hi)", settings["permissions"]["allow"])
        self.assertEqual(settings["enabledPlugins"]["existing-plugin"], True)
        bash_entry = next(
            e for e in settings["hooks"]["PreToolUse"] if e["matcher"] == "Bash"
        )
        cmds = [h["command"] for h in bash_entry["hooks"]]
        self.assertIn("$CLAUDE_PROJECT_DIR/.claude/hooks/stub-hook.sh", cmds)

    def test_install_idempotent(self):
        for _ in range(2):
            install.install(
                manifest_path=FIXTURES / "manifest_valid.toml",
                clank_root=FIXTURES,
                target=self.target,
                preset="test-both",
                include=[],
                exclude=[],
                conflict_policy="overwrite",
                dry_run=False,
                stop_hook_opt_in=False,
                clank_version="test",
                clank_commit="testcommit",
            )
        settings = json.loads((self.target / ".claude/settings.json").read_text())
        bash_entry = next(
            e for e in settings["hooks"]["PreToolUse"] if e["matcher"] == "Bash"
        )
        cmds = [h["command"] for h in bash_entry["hooks"]]
        self.assertEqual(len(cmds), len(set(cmds)))


class TestInteractivePicker(unittest.TestCase):
    def setUp(self):
        self.manifest = install.Manifest.load(FIXTURES / "manifest_valid.toml")

    def test_toggle_and_continue(self):
        user_input = iter(["1", "c", "", "c", "c", "c"])

        def fake_input(_prompt=""):
            return next(user_input)

        selected = install.interactive_pick(
            self.manifest, input_fn=fake_input, output=io.StringIO()
        )
        self.assertIn("stub-agent", selected)

    def test_all_then_none(self):
        # Within each category: "a" adds all, "n" removes all, "c" continues.
        # With 2 categories populated in the fixture (agents, hooks) we do
        # (a, n, c) for Agents → empty; then (a, n, c) for Hooks → still empty.
        user_input = iter(["a", "n", "c", "a", "n", "c"])

        def fake_input(_prompt=""):
            return next(user_input)

        selected = install.interactive_pick(
            self.manifest, input_fn=fake_input, output=io.StringIO()
        )
        self.assertEqual(selected, set())


class TestFzfPick(unittest.TestCase):
    def setUp(self):
        self.manifest = install.Manifest.load(FIXTURES / "manifest_valid.toml")

    def test_returns_none_when_fzf_not_on_path(self):
        # When fzf isn't installed, fzf_pick returns None so main() can
        # fall back to the stdlib numbered picker.
        with mock.patch("install.shutil.which", return_value=None):
            self.assertIsNone(install.fzf_pick(self.manifest))

    def test_parses_selected_ids_from_fzf_output(self):
        # fzf emits one line per selection, padded to the input format
        # (id in first column). fzf_pick should parse the first whitespace
        # token on each line as the artifact ID.
        fake_stdout = (
            "stub-agent                      agent       a stub agent\n"
            "stub-hook                       hook        a stub hook\n"
        )
        fake_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=fake_stdout, stderr=""
        )
        with mock.patch("install.shutil.which", return_value="/usr/bin/fzf"), \
                mock.patch("subprocess.run", return_value=fake_result):
            picked = install.fzf_pick(self.manifest)
        self.assertEqual(picked, {"stub-agent", "stub-hook"})

    def test_raises_on_user_abort(self):
        # fzf exit code 130 = user hit ESC / Ctrl-C. Should raise
        # InstallError rather than silently installing nothing.
        fake_result = subprocess.CompletedProcess(
            args=[], returncode=130, stdout="", stderr=""
        )
        with mock.patch("install.shutil.which", return_value="/usr/bin/fzf"), \
                mock.patch("subprocess.run", return_value=fake_result):
            with self.assertRaises(install.InstallError) as ctx:
                install.fzf_pick(self.manifest)
            self.assertIn("aborted", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
