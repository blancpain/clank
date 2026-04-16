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
        self.assertEqual(selected, {"stub-agent", "stub-hook", "stub-mcp"})

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
        self.assertEqual(selected, {"stub-agent", "stub-mcp"})

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

    def test_copy_mcp_is_executable(self):
        install.copy_artifact(
            self.manifest.artifacts["stub-mcp"],
            FIXTURES,
            self.target,
            on_conflict=lambda dst: "overwrite",
        )
        dst = self.target / ".claude/mcp/stub-mcp-wrapper.sh"
        self.assertTrue(dst.exists())
        self.assertTrue(dst.stat().st_mode & 0o111)


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


class TestMcpMerge(unittest.TestCase):
    def test_merge_into_empty(self):
        target = {}
        fragment = {
            "mcpServers": {
                "postgres": {"command": "bash", "args": [".claude/mcp/pg.sh"]}
            }
        }
        result = install.merge_mcp(target, fragment)
        self.assertEqual(result["mcpServers"]["postgres"]["command"], "bash")
        self.assertEqual(result["mcpServers"]["postgres"]["args"], [".claude/mcp/pg.sh"])

    def test_merge_preserves_existing_server(self):
        target = {
            "mcpServers": {
                "postgres": {"command": "custom", "args": ["--my-flag"]}
            }
        }
        fragment = {
            "mcpServers": {
                "postgres": {"command": "bash", "args": [".claude/mcp/pg.sh"]}
            }
        }
        result = install.merge_mcp(target, fragment)
        # Target wins on key conflict
        self.assertEqual(result["mcpServers"]["postgres"]["command"], "custom")

    def test_merge_adds_new_server(self):
        target = {
            "mcpServers": {
                "filesystem": {"command": "npx", "args": ["-y", "server-fs"]}
            }
        }
        fragment = {
            "mcpServers": {
                "postgres": {"command": "bash", "args": [".claude/mcp/pg.sh"]}
            }
        }
        result = install.merge_mcp(target, fragment)
        self.assertIn("filesystem", result["mcpServers"])
        self.assertIn("postgres", result["mcpServers"])

    def test_merge_idempotent(self):
        fragment = {
            "mcpServers": {
                "postgres": {"command": "bash", "args": [".claude/mcp/pg.sh"]}
            }
        }
        result = install.merge_mcp({}, fragment)
        result2 = install.merge_mcp(result, fragment)
        self.assertEqual(result, result2)


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

    def test_uninstall_mcp_removes_server_from_mcp_json(self):
        # Install the MCP artifact first
        install.copy_artifact(
            self.manifest.artifacts["stub-mcp"],
            FIXTURES,
            self.target,
            on_conflict=lambda dst: "overwrite",
        )
        mcp_frag = json.loads(
            (FIXTURES / "addons/sql/mcp/mcp-stub.json").read_text()
        )
        mcp_path = self.target / ".mcp.json"
        mcp_path.write_text(json.dumps(install.merge_mcp({}, mcp_frag), indent=2))
        install.write_receipt(
            self.target, ["stub-agent", "stub-hook", "stub-mcp"], "0.1.0", "test"
        )

        install.uninstall(self.manifest, FIXTURES, self.target, ["stub-mcp"])
        self.assertFalse(mcp_path.exists())  # empty .mcp.json is deleted
        self.assertFalse(
            (self.target / ".claude/mcp/stub-mcp-wrapper.sh").exists()
        )

    def test_uninstall_mcp_preserves_other_servers(self):
        # .mcp.json has both a clank-installed server and a user-added one
        mcp_frag = json.loads(
            (FIXTURES / "addons/sql/mcp/mcp-stub.json").read_text()
        )
        combined = install.merge_mcp(
            {"mcpServers": {"filesystem": {"command": "npx", "args": ["fs"]}}},
            mcp_frag,
        )
        mcp_path = self.target / ".mcp.json"
        mcp_path.write_text(json.dumps(combined, indent=2))
        install.copy_artifact(
            self.manifest.artifacts["stub-mcp"],
            FIXTURES,
            self.target,
            on_conflict=lambda dst: "overwrite",
        )
        install.write_receipt(
            self.target, ["stub-agent", "stub-hook", "stub-mcp"], "0.1.0", "test"
        )

        install.uninstall(self.manifest, FIXTURES, self.target, ["stub-mcp"])
        mcp = json.loads(mcp_path.read_text())
        self.assertIn("filesystem", mcp["mcpServers"])
        self.assertNotIn("postgres", mcp.get("mcpServers", {}))


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

    def test_install_mcp_creates_mcp_json(self):
        install.install(
            manifest_path=FIXTURES / "manifest_valid.toml",
            clank_root=FIXTURES,
            target=self.target,
            preset="test-mcp",
            include=[],
            exclude=[],
            conflict_policy="overwrite",
            dry_run=False,
            stop_hook_opt_in=False,
            clank_version="test",
            clank_commit="testcommit",
        )
        # Wrapper script is copied and executable
        wrapper = self.target / ".claude/mcp/stub-mcp-wrapper.sh"
        self.assertTrue(wrapper.exists())
        self.assertTrue(wrapper.stat().st_mode & 0o111)
        # .mcp.json is created at project root
        mcp_path = self.target / ".mcp.json"
        self.assertTrue(mcp_path.exists())
        mcp = json.loads(mcp_path.read_text())
        self.assertIn("postgres", mcp["mcpServers"])
        self.assertEqual(mcp["mcpServers"]["postgres"]["command"], "bash")

    def test_install_mcp_preserves_existing_mcp_json(self):
        (self.target / ".mcp.json").write_text(
            json.dumps(
                {"mcpServers": {"filesystem": {"command": "npx", "args": ["fs"]}}},
                indent=2,
            )
        )
        install.install(
            manifest_path=FIXTURES / "manifest_valid.toml",
            clank_root=FIXTURES,
            target=self.target,
            preset="test-mcp",
            include=[],
            exclude=[],
            conflict_policy="overwrite",
            dry_run=False,
            stop_hook_opt_in=False,
            clank_version="test",
            clank_commit="testcommit",
        )
        mcp = json.loads((self.target / ".mcp.json").read_text())
        self.assertIn("filesystem", mcp["mcpServers"])
        self.assertIn("postgres", mcp["mcpServers"])

    def test_install_mcp_idempotent(self):
        for _ in range(2):
            install.install(
                manifest_path=FIXTURES / "manifest_valid.toml",
                clank_root=FIXTURES,
                target=self.target,
                preset="test-mcp",
                include=[],
                exclude=[],
                conflict_policy="overwrite",
                dry_run=False,
                stop_hook_opt_in=False,
                clank_version="test",
                clank_commit="testcommit",
            )
        mcp = json.loads((self.target / ".mcp.json").read_text())
        self.assertEqual(len(mcp["mcpServers"]), 1)


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
        # With 3 categories populated in the fixture (agents, hooks, mcp) we do
        # (a, n, c) for each → all empty at the end.
        user_input = iter(["a", "n", "c", "a", "n", "c", "a", "n", "c"])

        def fake_input(_prompt=""):
            return next(user_input)

        selected = install.interactive_pick(
            self.manifest, input_fn=fake_input, output=io.StringIO()
        )
        self.assertEqual(selected, set())


class TestCursesPicker(unittest.TestCase):
    def setUp(self):
        self.manifest = install.Manifest.load(FIXTURES / "manifest_valid.toml")

    def test_returns_none_when_curses_unavailable(self):
        # When curses can't be imported (exotic platforms, Windows without
        # windows-curses), curses_pick returns None so main() falls back
        # to the stdlib numbered picker. We simulate by poisoning the
        # curses entry in sys.modules so `import curses` raises.
        with mock.patch.dict(sys.modules, {"curses": None}):
            self.assertIsNone(install.curses_pick(self.manifest))


if __name__ == "__main__":
    unittest.main()
