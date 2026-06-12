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
        # --target defaults to CWD now, so the argparse error is about missing
        # a selection flag instead.
        self.assertIn("--preset", err)

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


def _read_frontmatter(skill_md: Path) -> dict[str, str]:
    """Parse the simple `key: value` YAML frontmatter of a SKILL.md."""
    lines = skill_md.read_text().splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line and not line.startswith((" ", "\t")):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip().strip('"')
    return fields


class TestRealManifest(unittest.TestCase):
    """Validate the repo's actual manifest.toml and the artifacts it points at.

    The other test classes exercise the installer against fixtures; this one
    guards the real content, so adding an artifact (e.g. a new skill) without
    registering it correctly fails CI.
    """

    @classmethod
    def setUpClass(cls):
        cls.manifest = install.Manifest.load(CLANK_ROOT / "manifest.toml")

    def test_real_manifest_lints_clean(self):
        errors = install.lint_manifest(self.manifest, CLANK_ROOT)
        self.assertEqual(errors, [])

    def _skill_artifacts(self):
        return {
            aid: a
            for aid, a in self.manifest.artifacts.items()
            if a.get("type") == "skill"
        }

    def test_every_skill_dir_on_disk_is_registered(self):
        registered = {
            str(Path(a["path"])) for a in self._skill_artifacts().values()
        }
        on_disk = {
            str(p.parent.relative_to(CLANK_ROOT))
            for d in ("base", "addons")
            for p in (CLANK_ROOT / d).rglob("SKILL.md")
        }
        self.assertEqual(on_disk - registered, set())

    def test_every_skill_has_skill_md(self):
        for aid, artifact in self._skill_artifacts().items():
            skill_md = CLANK_ROOT / artifact["path"] / "SKILL.md"
            self.assertTrue(skill_md.is_file(), f"{aid}: missing SKILL.md")

    def test_skill_frontmatter_name_matches_directory(self):
        for aid, artifact in self._skill_artifacts().items():
            skill_md = CLANK_ROOT / artifact["path"] / "SKILL.md"
            fields = _read_frontmatter(skill_md)
            self.assertEqual(
                fields.get("name"),
                Path(artifact["path"]).name,
                f"{aid}: frontmatter name must match the skill directory name",
            )

    def test_skill_frontmatter_has_description(self):
        for aid, artifact in self._skill_artifacts().items():
            skill_md = CLANK_ROOT / artifact["path"] / "SKILL.md"
            fields = _read_frontmatter(skill_md)
            self.assertTrue(
                fields.get("description"),
                f"{aid}: frontmatter must include a non-empty description",
            )

    def test_handoff_and_pickup_are_mirror_pair(self):
        skills = self._skill_artifacts()
        self.assertIn("handoff", skills)
        self.assertIn("pickup", skills)
        for aid in ("handoff", "pickup"):
            fields = _read_frontmatter(
                CLANK_ROOT / skills[aid]["path"] / "SKILL.md"
            )
            self.assertEqual(
                fields.get("disable-model-invocation"),
                "true",
                f"{aid}: must be user-invoked only (disable-model-invocation)",
            )
            self.assertEqual(skills[aid].get("tags"), ["base", "process"])


class TestExternalSkill(unittest.TestCase):
    """Install/uninstall flow for the external-skill artifact type."""

    def setUp(self):
        self.manifest = install.Manifest.load(FIXTURES / "manifest_valid.toml")
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)
        (self.target / ".claude").mkdir()
        self.artifact = self.manifest.artifacts["stub-external-skill"]

    def tearDown(self):
        self.tmp.cleanup()

    def test_lint_rejects_external_skill_with_path(self):
        bad = install.Manifest(
            artifacts=[
                {
                    "id": "bad-ext",
                    "type": "external-skill",
                    "source": "foo/bar",
                    "skill_name": "bad",
                    "path": "base/something",
                }
            ],
            presets={},
            version=1,
        )
        errors = install.lint_manifest(bad, FIXTURES)
        self.assertTrue(any("must not define 'path'" in e for e in errors))

    def test_lint_requires_source_and_skill_name(self):
        bad = install.Manifest(
            artifacts=[{"id": "bad-ext", "type": "external-skill"}],
            presets={},
            version=1,
        )
        errors = install.lint_manifest(bad, FIXTURES)
        self.assertTrue(any("'source' field" in e for e in errors))
        self.assertTrue(any("'skill_name' field" in e for e in errors))

    def test_install_shells_out_to_npx_with_expected_args(self):
        fake = mock.MagicMock(returncode=0, stdout="", stderr="")
        with (
            mock.patch("shutil.which", return_value="/usr/bin/npx"),
            mock.patch("subprocess.run", return_value=fake) as run,
        ):
            ok = install._install_external_skill(self.artifact, self.target)
        self.assertTrue(ok)
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[:4], ["npx", "-y", "skills", "add"])
        self.assertIn("example/repo", cmd)
        self.assertIn("--skill", cmd)
        self.assertIn("stub-external", cmd)
        self.assertIn("--copy", cmd)
        # runs in the target dir so `npx skills` resolves CWD to .claude/skills/
        self.assertEqual(run.call_args.kwargs["cwd"], self.target)

    def test_install_skips_gracefully_when_npx_missing(self):
        with mock.patch("shutil.which", return_value=None):
            ok = install._install_external_skill(self.artifact, self.target)
        self.assertFalse(ok)

    def test_install_reports_false_on_nonzero_exit(self):
        fake = mock.MagicMock(returncode=1, stdout="", stderr="boom")
        with (
            mock.patch("shutil.which", return_value="/usr/bin/npx"),
            mock.patch("subprocess.run", return_value=fake),
        ):
            ok = install._install_external_skill(self.artifact, self.target)
        self.assertFalse(ok)

    def test_dry_run_does_not_invoke_npx(self):
        with mock.patch("subprocess.run") as run:
            rc = install.install(
                manifest_path=FIXTURES / "manifest_valid.toml",
                clank_root=FIXTURES,
                target=self.target,
                preset=None,
                include=["stub-external-skill"],
                exclude=[],
                conflict_policy="skip",
                dry_run=True,
                review_hook_opt_in=False,
                clank_version="0.1.0",
                clank_commit="test",
            )
        self.assertEqual(rc, 0)
        run.assert_not_called()

    def test_uninstall_removes_skill_directory(self):
        skill_dir = self.target / ".claude" / "skills" / "stub-external"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# stub\n")
        install.write_receipt(
            self.target, ["stub-external-skill"], "0.1.0", "test"
        )

        install.uninstall(
            self.manifest, FIXTURES, self.target, ["stub-external-skill"]
        )
        self.assertFalse(skill_dir.exists())
        receipt = install.read_receipt(self.target)
        self.assertEqual(receipt.get("artifacts", []), [])


class TestSelectionResolution(unittest.TestCase):
    def setUp(self):
        self.manifest = install.Manifest.load(FIXTURES / "manifest_valid.toml")

    def test_resolve_preset_minimal(self):
        selected = install.resolve_selection(self.manifest, preset="minimal")
        self.assertEqual(selected, {"stub-agent"})

    def test_resolve_tag_star(self):
        selected = install.resolve_selection(self.manifest, preset="all")
        self.assertEqual(
            selected,
            {"stub-agent", "stub-agent-2", "agents", "stub-hook", "stub-mcp"},
        )

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
        self.assertEqual(
            selected, {"stub-agent", "stub-agent-2", "agents", "stub-mcp"}
        )

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


class TestResolveTarget(unittest.TestCase):
    """--target defaults to CWD with a y/N confirm gate."""

    def _args(self, **kw):
        import argparse
        defaults = {"target": None, "force": False, "dry_run": False}
        defaults.update(kw)
        return argparse.Namespace(**defaults)

    def test_explicit_target_passes_through(self):
        explicit = Path("/tmp/whatever")
        self.assertEqual(install._resolve_target(self._args(target=explicit)), explicit)

    def test_force_skips_prompt_and_returns_cwd(self):
        self.assertEqual(install._resolve_target(self._args(force=True)), Path.cwd())

    def test_dry_run_skips_prompt_and_returns_cwd(self):
        self.assertEqual(install._resolve_target(self._args(dry_run=True)), Path.cwd())

    def test_confirm_yes_returns_cwd(self):
        with mock.patch("builtins.input", return_value="y"):
            self.assertEqual(install._resolve_target(self._args()), Path.cwd())

    def test_confirm_empty_aborts(self):
        with mock.patch("builtins.input", return_value=""):
            with self.assertRaises(install.InstallError):
                install._resolve_target(self._args())

    def test_confirm_eof_aborts(self):
        with mock.patch("builtins.input", side_effect=EOFError):
            with self.assertRaises(install.InstallError):
                install._resolve_target(self._args())


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
            review_hook_opt_in=False,
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
            review_hook_opt_in=False,
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
                review_hook_opt_in=False,
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
            review_hook_opt_in=False,
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
            review_hook_opt_in=False,
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
                review_hook_opt_in=False,
                clank_version="test",
                clank_commit="testcommit",
            )
        mcp = json.loads((self.target / ".mcp.json").read_text())
        self.assertEqual(len(mcp["mcpServers"]), 1)


class TestDynamicAgentsRule(unittest.TestCase):
    """agents.md is generated dynamically from installed agent artifacts."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _install(self, preset=None, include=None, exclude=None):
        return install.install(
            manifest_path=FIXTURES / "manifest_valid.toml",
            clank_root=FIXTURES,
            target=self.target,
            preset=preset,
            include=include or [],
            exclude=exclude or [],
            conflict_policy="overwrite",
            dry_run=False,
            review_hook_opt_in=False,
            clank_version="test",
            clank_commit="testcommit",
        )

    def _agents_md(self):
        return (self.target / ".claude" / "rules" / "agents.md").read_text()

    def test_agents_md_lists_installed_agents(self):
        """agents.md table reflects exactly the agents that were installed."""
        self._install(include=["stub-agent", "agents"])
        content = self._agents_md()
        self.assertIn("stub-agent", content)
        # stub-agent-2 was NOT selected → must NOT appear
        self.assertNotIn("stub-agent-2", content)

    def test_agents_md_includes_all_agents_when_both_installed(self):
        self._install(include=["stub-agent", "stub-agent-2", "agents"])
        content = self._agents_md()
        self.assertIn("stub-agent", content)
        self.assertIn("stub-agent-2", content)

    def test_agents_md_overwrites_static_template(self):
        """The static agents.md template is replaced with dynamic content."""
        self._install(include=["stub-agent", "agents"])
        content = self._agents_md()
        # Static placeholder text must be gone
        self.assertNotIn("Static placeholder", content)
        # Dynamic table header must be present
        self.assertIn("| Agent | When to invoke |", content)

    def test_agents_md_updates_on_incremental_install(self):
        """Adding agents in a later install regenerates agents.md."""
        self._install(include=["stub-agent", "agents"])
        content_v1 = self._agents_md()
        self.assertNotIn("stub-agent-2", content_v1)

        # Second install adds another agent
        self._install(include=["stub-agent-2"])
        content_v2 = self._agents_md()
        self.assertIn("stub-agent", content_v2)
        self.assertIn("stub-agent-2", content_v2)

    def test_agents_md_updates_on_uninstall(self):
        """Removing an agent regenerates agents.md without that agent."""
        self._install(include=["stub-agent", "stub-agent-2", "agents"])
        manifest = install.Manifest.load(FIXTURES / "manifest_valid.toml")
        install.uninstall(manifest, FIXTURES, self.target, ["stub-agent-2"])
        content = self._agents_md()
        self.assertIn("stub-agent", content)
        self.assertNotIn("stub-agent-2", content)

    def test_agents_md_removed_when_all_agents_uninstalled(self):
        """If every agent is uninstalled, agents.md becomes empty and is deleted."""
        self._install(include=["stub-agent", "agents"])
        manifest = install.Manifest.load(FIXTURES / "manifest_valid.toml")
        install.uninstall(manifest, FIXTURES, self.target, ["stub-agent"])
        self.assertFalse(
            (self.target / ".claude" / "rules" / "agents.md").exists()
        )

    def test_agents_md_includes_custom_agents(self):
        """Manually added agent files appear in the generated agents.md."""
        self._install(include=["stub-agent", "agents"])
        # Drop a custom agent into the target by hand
        custom = self.target / ".claude" / "agents" / "my-custom-agent.md"
        custom.write_text(
            "---\n"
            "name: my-custom-agent\n"
            "description: A hand-crafted agent\n"
            "---\n\n"
            "Custom body.\n"
        )
        # Re-install to trigger regeneration
        self._install(include=["stub-agent", "agents"])
        content = self._agents_md()
        self.assertIn("my-custom-agent", content)
        self.assertIn("A hand-crafted agent", content)
        # Manifest agent still present
        self.assertIn("stub-agent", content)

    def test_agents_md_skips_manifest_agents_when_scanning(self):
        """Manifest-installed agent files are not double-counted from disk scan."""
        self._install(include=["stub-agent", "agents"])
        content = self._agents_md()
        # stub-agent should appear exactly once in the table
        table_lines = [l for l in content.splitlines() if "**stub-agent**" in l and l.startswith("|")]
        self.assertEqual(len(table_lines), 1)

    def test_custom_agent_without_frontmatter_uses_stem(self):
        """Agent files without frontmatter fall back to filename stem."""
        self._install(include=["stub-agent", "agents"])
        custom = self.target / ".claude" / "agents" / "bare-agent.md"
        custom.write_text("No frontmatter here, just a body.\n")
        self._install(include=["stub-agent", "agents"])
        content = self._agents_md()
        self.assertIn("bare-agent", content)

    def test_dry_run_does_not_generate_agents_md(self):
        """Dry run must not write the generated file."""
        install.install(
            manifest_path=FIXTURES / "manifest_valid.toml",
            clank_root=FIXTURES,
            target=self.target,
            preset=None,
            include=["stub-agent", "agents"],
            exclude=[],
            conflict_policy="overwrite",
            dry_run=True,
            review_hook_opt_in=False,
            clank_version="test",
            clank_commit="testcommit",
        )
        self.assertFalse(
            (self.target / ".claude" / "rules" / "agents.md").exists()
        )


class TestRefreshAgents(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_refresh_agents_regenerates(self):
        """--refresh-agents regenerates agents.md from receipt + disk."""
        # First, do a normal install
        install.install(
            manifest_path=FIXTURES / "manifest_valid.toml",
            clank_root=FIXTURES,
            target=self.target,
            preset=None,
            include=["stub-agent", "agents"],
            exclude=[],
            conflict_policy="overwrite",
            dry_run=False,
            review_hook_opt_in=False,
            clank_version="test",
            clank_commit="testcommit",
        )
        # Drop a custom agent
        custom = self.target / ".claude" / "agents" / "custom.md"
        custom.write_text("---\nname: custom\ndescription: My custom agent\n---\n")
        # Run --refresh-agents via main()
        rc = install.main(
            ["--target", str(self.target), "--refresh-agents"]
        )
        self.assertEqual(rc, 0)
        content = (self.target / ".claude" / "rules" / "agents.md").read_text()
        self.assertIn("stub-agent", content)
        self.assertIn("custom", content)
        self.assertIn("My custom agent", content)

    def test_refresh_agents_no_receipt(self):
        """--refresh-agents on a target with no receipt still scans disk."""
        (self.target / ".claude" / "agents").mkdir(parents=True)
        custom = self.target / ".claude" / "agents" / "solo.md"
        custom.write_text("---\nname: solo\ndescription: Solo agent\n---\n")
        rc = install.main(
            ["--target", str(self.target), "--refresh-agents"]
        )
        self.assertEqual(rc, 0)
        content = (self.target / ".claude" / "rules" / "agents.md").read_text()
        self.assertIn("solo", content)


class TestEndOfTurnReview(unittest.TestCase):
    """The 'Before ending a coding turn' block injected into <target>/CLAUDE.md."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    # -- _generate_end_of_turn_review -------------------------------------

    def test_generate_empty_when_no_reviewers_installed(self):
        self.assertEqual(install._generate_end_of_turn_review(set()), "")
        self.assertEqual(
            install._generate_end_of_turn_review({"ruff", "bash-safety"}),
            "",
        )

    def test_generate_python_row_pairs_with_code_reviewer(self):
        block = install._generate_end_of_turn_review(
            {"python-reviewer", "code-reviewer"}
        )
        self.assertIn("Any Python file", block)
        self.assertIn("`python-reviewer` + `code-reviewer`", block)
        self.assertIn("Any other code change", block)

    def test_generate_python_row_without_code_reviewer(self):
        block = install._generate_end_of_turn_review({"python-reviewer"})
        self.assertIn("| Any Python file | `python-reviewer` |", block)
        # no catch-all row without code-reviewer
        self.assertNotIn("Any other code change", block)

    def test_generate_skips_language_rows_when_reviewer_absent(self):
        block = install._generate_end_of_turn_review({"code-reviewer"})
        self.assertNotIn("Any Python file", block)
        self.assertNotIn("Any TypeScript", block)
        self.assertIn("Any other code change", block)

    def test_generate_sql_rows(self):
        just_sql = install._generate_end_of_turn_review({"sql-reviewer"})
        self.assertIn("SQL in any form", just_sql)
        self.assertNotIn("migration or schema-changing", just_sql)

        with_db = install._generate_end_of_turn_review(
            {"sql-reviewer", "database-reviewer"}
        )
        self.assertIn("migration or schema-changing", with_db)
        self.assertIn("`database-reviewer` + `sql-reviewer`", with_db)

    def test_generate_database_reviewer_alone_no_migration_row(self):
        block = install._generate_end_of_turn_review({"database-reviewer"})
        self.assertNotIn("migration or schema-changing", block)

    def test_generate_pipeline_and_security_rows(self):
        block = install._generate_end_of_turn_review(
            {"pipeline-validator", "security-reviewer"}
        )
        self.assertIn("Data-pipeline code", block)
        self.assertIn("`pipeline-validator`", block)
        self.assertIn("Security-sensitive", block)
        self.assertIn("`security-reviewer`", block)

    def test_generate_footer_docs_notes(self):
        block = install._generate_end_of_turn_review(
            {"code-reviewer", "docs-researcher", "doc-updater"}
        )
        self.assertIn("`docs-researcher`", block)
        self.assertIn("`doc-updater`", block)
        self.assertIn("coding when library/API knowledge is needed", block)

        no_docs = install._generate_end_of_turn_review({"code-reviewer"})
        self.assertNotIn("docs-researcher", no_docs)
        self.assertNotIn("doc-updater", no_docs)

    # -- _write_end_of_turn_block -----------------------------------------

    def test_write_creates_claude_md_when_missing(self):
        block = install._generate_end_of_turn_review({"code-reviewer"})
        install._write_end_of_turn_block(self.target, block)
        path = self.target / "CLAUDE.md"
        self.assertTrue(path.exists())
        text = path.read_text()
        self.assertIn(install.END_OF_TURN_BEGIN, text)
        self.assertIn(install.END_OF_TURN_END, text)
        self.assertIn("Before ending a coding turn", text)

    def test_write_appends_to_existing_claude_md(self):
        claude_md = self.target / "CLAUDE.md"
        claude_md.write_text("# Project\n\nExisting content.\n")
        block = install._generate_end_of_turn_review({"code-reviewer"})
        install._write_end_of_turn_block(self.target, block)
        text = claude_md.read_text()
        self.assertTrue(text.startswith("# Project\n\nExisting content."))
        self.assertIn(install.END_OF_TURN_BEGIN, text)

    def test_write_is_idempotent(self):
        claude_md = self.target / "CLAUDE.md"
        claude_md.write_text("# Project\n\nExisting.\n")
        block = install._generate_end_of_turn_review(
            {"python-reviewer", "code-reviewer"}
        )
        install._write_end_of_turn_block(self.target, block)
        once = claude_md.read_text()
        install._write_end_of_turn_block(self.target, block)
        twice = claude_md.read_text()
        self.assertEqual(once, twice)
        # Block markers appear exactly once
        self.assertEqual(twice.count(install.END_OF_TURN_BEGIN), 1)
        self.assertEqual(twice.count(install.END_OF_TURN_END), 1)

    def test_write_replaces_existing_block_on_regenerate(self):
        claude_md = self.target / "CLAUDE.md"
        claude_md.write_text("# Project\n")
        first = install._generate_end_of_turn_review(
            {"python-reviewer", "code-reviewer"}
        )
        install._write_end_of_turn_block(self.target, first)
        # Now regenerate with a different set — Python row must disappear,
        # SQL row must appear.
        second = install._generate_end_of_turn_review(
            {"sql-reviewer", "code-reviewer"}
        )
        install._write_end_of_turn_block(self.target, second)
        text = claude_md.read_text()
        self.assertNotIn("Any Python file", text)
        self.assertIn("SQL in any form", text)
        self.assertEqual(text.count(install.END_OF_TURN_BEGIN), 1)

    def test_write_empty_block_strips_from_claude_md(self):
        claude_md = self.target / "CLAUDE.md"
        claude_md.write_text("# Project\n")
        install._write_end_of_turn_block(
            self.target,
            install._generate_end_of_turn_review({"code-reviewer"}),
        )
        self.assertIn(install.END_OF_TURN_BEGIN, claude_md.read_text())
        # Now the user uninstalls every reviewer — block should vanish but
        # the user's own content must survive.
        install._write_end_of_turn_block(self.target, "")
        text = claude_md.read_text()
        self.assertNotIn(install.END_OF_TURN_BEGIN, text)
        self.assertIn("# Project", text)

    def test_write_empty_block_deletes_clank_only_claude_md(self):
        # CLAUDE.md created solely by clank (no user content) — removing the
        # block should delete the now-empty file rather than leave a stub.
        install._write_end_of_turn_block(
            self.target,
            install._generate_end_of_turn_review({"code-reviewer"}),
        )
        self.assertTrue((self.target / "CLAUDE.md").exists())
        install._write_end_of_turn_block(self.target, "")
        self.assertFalse((self.target / "CLAUDE.md").exists())

    def test_write_noop_when_no_block_and_no_markers(self):
        claude_md = self.target / "CLAUDE.md"
        claude_md.write_text("# Project\n")
        install._write_end_of_turn_block(self.target, "")
        self.assertEqual(claude_md.read_text(), "# Project\n")

    def test_write_replaces_legacy_unmarked_section(self):
        # A CLAUDE.md that predates the marker comments — the generated
        # section is present under its heading but without <!-- clank:...:begin/end -->.
        # Re-running the installer must replace in place, not append a duplicate.
        claude_md = self.target / "CLAUDE.md"
        legacy = (
            "# Project\n"
            "\n"
            "## Planning Docs\n"
            "\n"
            "Some roadmap notes.\n"
            "\n"
            "### Before ending a coding turn\n"
            "\n"
            "Old hand-written content with project-specific `scripts/ingest/` paths.\n"
            "\n"
            "| If you touched | Launch |\n"
            "|---|---|\n"
            "| Files in `scripts/ingest/migrations/` | `database-reviewer` + `sql-reviewer` |\n"
        )
        claude_md.write_text(legacy)
        block = install._generate_end_of_turn_review(
            {"python-reviewer", "code-reviewer"}
        )
        install._write_end_of_turn_block(self.target, block)
        text = claude_md.read_text()
        # Exactly one end-of-turn section — the legacy copy is gone.
        self.assertEqual(text.count("### Before ending a coding turn"), 1)
        self.assertEqual(text.count(install.END_OF_TURN_BEGIN), 1)
        self.assertEqual(text.count(install.END_OF_TURN_END), 1)
        # Legacy-only content disappears; generated content is present.
        self.assertNotIn("scripts/ingest/migrations/", text)
        self.assertIn("`python-reviewer` + `code-reviewer`", text)
        # User's other content is preserved, in order.
        self.assertIn("## Planning Docs", text)
        self.assertIn("Some roadmap notes.", text)
        self.assertLess(text.index("## Planning Docs"), text.index(install.END_OF_TURN_BEGIN))

    def test_write_replaces_legacy_section_at_end_of_file(self):
        # Legacy section with no trailing newline and no following heading —
        # the writer must still replace it cleanly.
        claude_md = self.target / "CLAUDE.md"
        claude_md.write_text(
            "# Project\n\n### Before ending a coding turn\n\nOld content.\n"
        )
        block = install._generate_end_of_turn_review({"code-reviewer"})
        install._write_end_of_turn_block(self.target, block)
        text = claude_md.read_text()
        self.assertEqual(text.count("### Before ending a coding turn"), 1)
        self.assertEqual(text.count(install.END_OF_TURN_BEGIN), 1)
        self.assertNotIn("Old content.", text)
        self.assertIn("# Project", text)

    def test_write_empty_strips_legacy_unmarked_section(self):
        # Uninstall path: no reviewers remain, so the block is empty. A legacy
        # unmarked section must still be stripped.
        claude_md = self.target / "CLAUDE.md"
        claude_md.write_text(
            "# Project\n\n### Before ending a coding turn\n\nOld content.\n\n## After\n\nkeep me\n"
        )
        install._write_end_of_turn_block(self.target, "")
        text = claude_md.read_text()
        self.assertNotIn("Before ending a coding turn", text)
        self.assertNotIn("Old content.", text)
        self.assertIn("# Project", text)
        self.assertIn("## After", text)
        self.assertIn("keep me", text)


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
        # 5 categories populated in the fixture (agents, hooks, rules, mcp,
        # external-skill) → (a, n, c) for each → all empty at the end.
        user_input = iter(["a", "n", "c"] * 5)

        def fake_input(_prompt=""):
            return next(user_input)

        selected = install.interactive_pick(
            self.manifest, input_fn=fake_input, output=io.StringIO()
        )
        self.assertEqual(selected, set())

    def test_preselected_artifacts_start_checked(self):
        """Artifacts from the receipt appear pre-checked in the picker."""
        # Just press "c" through every category without toggling anything.
        # 5 non-empty categories in the fixture.
        user_input = iter(["c"] * 5)

        def fake_input(_prompt=""):
            return next(user_input)

        out = io.StringIO()
        selected = install.interactive_pick(
            self.manifest,
            input_fn=fake_input,
            output=out,
            preselected={"stub-agent", "stub-hook"},
        )
        # Without touching anything, preselected items should be returned
        self.assertIn("stub-agent", selected)
        self.assertIn("stub-hook", selected)
        # The display should show them checked
        display = out.getvalue()
        self.assertIn("[x]", display)


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
