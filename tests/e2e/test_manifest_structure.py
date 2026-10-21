"""Plugin + marketplace manifest structure validation.

Offline. Catches structural defects that break plugin loading without
any code change (e.g. hook schema regression, version drift between
manifests, broken hook script paths).
"""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

import pytest

from conftest import REPO_ROOT


PLUGIN_NAMES = ["sumtube", "media-downloader"]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_marketplace_json_well_formed():
    mk = _read_json(REPO_ROOT / ".claude-plugin" / "marketplace.json")
    assert mk.get("name"), "marketplace.json missing required 'name'"
    assert mk.get("owner"), "marketplace.json missing required 'owner'"
    plugins = mk.get("plugins", [])
    listed = {p.get("name") for p in plugins}
    assert listed == set(PLUGIN_NAMES), (
        f"marketplace.json plugin list drift: expected {PLUGIN_NAMES}, got {listed}"
    )
    for p in plugins:
        src = p.get("source")
        assert src, f"plugin {p.get('name')!r} missing 'source'"
        assert isinstance(src, str) and src.startswith("./"), (
            f"plugin source must be a relative path string starting with './'; got {src!r}"
        )
        target = REPO_ROOT / src
        assert target.is_dir(), f"plugin source path does not resolve: {target}"


@pytest.mark.parametrize("plugin", PLUGIN_NAMES)
def test_plugin_json_present_and_valid(plugin):
    pj = REPO_ROOT / "plugins" / plugin / ".claude-plugin" / "plugin.json"
    assert pj.is_file(), f"missing required plugin manifest: {pj}"
    data = _read_json(pj)
    assert data.get("name") == plugin, f"plugin.json name mismatch: {data.get('name')} vs {plugin}"
    version = data.get("version")
    assert isinstance(version, str) and re.fullmatch(r"\d+\.\d+\.\d+", version), (
        f"plugin.json version must be semver MAJOR.MINOR.PATCH, got {version!r}"
    )


@pytest.mark.parametrize("plugin", PLUGIN_NAMES)
def test_plugin_skill_present(plugin):
    skill_md = REPO_ROOT / "plugins" / plugin / "skills" / plugin / "SKILL.md"
    assert skill_md.is_file(), f"missing SKILL.md at conventional path: {skill_md}"


@pytest.mark.parametrize("plugin", PLUGIN_NAMES)
def test_plugin_command_present(plugin):
    cmd = REPO_ROOT / "plugins" / plugin / "commands" / f"{plugin}.md"
    assert cmd.is_file(), f"missing slash-command file: {cmd}"


@pytest.mark.parametrize("plugin", PLUGIN_NAMES)
def test_plugin_hooks_schema(plugin):
    """hooks.json must follow the nested-event schema and reference scripts that exist.

    Regression: day-one bug where hooks.json had a flat
    {"hooks": {"SessionStart": [{type, command}]}} structure missing
    the inner `hooks: [...]` array, causing both plugins to fail to load.
    """
    hooks_json = REPO_ROOT / "plugins" / plugin / "hooks" / "hooks.json"
    if not hooks_json.is_file():
        pytest.skip(f"{plugin} has no hooks.json")

    data = _read_json(hooks_json)
    events = data.get("hooks", {})
    assert events, f"{hooks_json}: empty 'hooks' object"

    for event_name, entries in events.items():
        assert isinstance(entries, list) and entries, (
            f"{hooks_json}: event {event_name!r} must be a non-empty list"
        )
        for entry in entries:
            inner = entry.get("hooks")
            assert isinstance(inner, list) and inner, (
                f"{hooks_json}: each {event_name!r} entry must have an inner 'hooks' array. "
                f"regression: day-one schema bug."
            )
            for hook in inner:
                assert hook.get("type") == "command", (
                    f"{hooks_json}: hook type must be 'command', got {hook.get('type')!r}"
                )
                cmd = hook.get("command", "")
                assert "${CLAUDE_PLUGIN_ROOT}" in cmd, (
                    f"{hooks_json}: hook command must use ${{CLAUDE_PLUGIN_ROOT}} (not a relative path), got {cmd!r}"
                )
                # Regression: `${CLAUDE_PLUGIN_ROOT}` must be quoted so paths
                # with spaces (e.g. ~/Public Projects/) don't word-split when
                # the hook command is invoked via bash.
                assert '"${CLAUDE_PLUGIN_ROOT}' in cmd or "'${CLAUDE_PLUGIN_ROOT}" in cmd, (
                    f"{hooks_json}: ${{CLAUDE_PLUGIN_ROOT}} must be wrapped in quotes "
                    f"to survive paths with spaces, got {cmd!r}"
                )
                # Resolve script reference and confirm it exists. Tokenise the
                # raw command (with the placeholder still in place) so paths
                # containing spaces in REPO_ROOT don't get shattered, then
                # substitute the plugin root per-token.
                plugin_root = REPO_ROOT / "plugins" / plugin
                tokens = [
                    t.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_root))
                    for t in shlex.split(cmd)
                ]
                script_path = next(
                    (Path(t) for t in tokens if t.endswith(".sh") or t.endswith(".py")),
                    None,
                )
                if script_path is not None:
                    assert script_path.is_file(), (
                        f"{hooks_json}: hook references missing script: {script_path}"
                    )


def test_changelog_present():
    changelog = REPO_ROOT / "CHANGELOG.md"
    assert changelog.is_file(), "CHANGELOG.md should exist at repo root"
