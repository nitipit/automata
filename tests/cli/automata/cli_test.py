import json
from pathlib import Path

import pytest

from automata.cli import app


def test_cli_character_compose_keeps_selected_components_on_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "character",
                "compose",
                "--personality",
                "automata",
                "--language",
                "thai",
                "--behavior",
                "co-pilot",
            ]
        )

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "# Personality: automata" in captured.out
    assert "# Language: base" in captured.out
    assert "# Language: thai" in captured.out
    assert "# Behavior: base" in captured.out
    assert "# Behavior: co-pilot" in captured.out
    assert "# Additional Instructions" in captured.out
    assert ".agents/var/skills/automata-agents-md/" in captured.out
    assert captured.out.index("# Personality: automata") < captured.out.index("# Language: base")


def test_cli_character_compose_overrides_agents_instruction_path(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "character",
                "compose",
                "--personality",
                "automata",
                "--agents-md",
                "custom/agent-instructions",
            ]
        )

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "# Additional Instructions" in output
    assert "`custom/agent-instructions/`" in output
    assert ".agents/var/skills/automata-agents-md/" not in output
    assert "discover and read its existing `.md` files" in output
    assert "absent or contains no Markdown files, continue without them" in output
    assert "not a skill package; do not assume a `SKILL.md` exists" in output


def test_cli_character_compose_rejects_empty_selection(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        app(["character", "compose"])

    assert str(exc_info.value) == "Select at least one character component"
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_cli_installs_bundled_skill_without_source_root(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    target_root = tmp_path / "dest"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "skills",
                "install",
                "--target-root",
                str(target_root),
                "--skill",
                "automata-setup",
            ]
        )

    assert exc_info.value.code == 0
    assert "Installed automata-setup" in capsys.readouterr().out
    assert (target_root / "automata-setup" / "SKILL.md").is_file()


def test_cli_installs_selected_comma_separated_skills(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    source_root = tmp_path / "source"
    make_skill(source_root / "my-skill")
    make_skill(source_root / "other-skill")

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "skills",
                "install",
                "--source-root",
                str(source_root),
                "--target-root",
                str(tmp_path / "dest"),
                "--skill",
                "my-skill,other-skill",
            ]
        )

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "Installed my-skill" in output
    assert "Installed other-skill" in output
    assert (tmp_path / "dest" / "my-skill" / "SKILL.md").exists()
    assert (tmp_path / "dest" / "other-skill" / "SKILL.md").exists()


def test_cli_skills_install_prints_json(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    make_skill(source_root / "my-skill")

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "skills",
                "install",
                "--source-root",
                str(source_root),
                "--target-root",
                str(tmp_path / "dest"),
                "--skill",
                "my-skill",
                "--json",
            ]
        )

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert '"name": "my-skill"' in output
    assert '"mode": "copy"' in output


def test_cli_installs_bundled_timer(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    target_root = tmp_path / ".agents" / "tools"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "tools",
                "install",
                "--target-root",
                str(target_root),
                "--tool",
                "timer",
            ]
        )

    assert exc_info.value.code == 0
    assert "Installed timer" in capsys.readouterr().out
    assert (target_root / "timer" / "timer.py").exists()


def test_cli_installs_bundled_codex_bridge_extension(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    target_root = tmp_path / ".pi" / "extensions"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "pi-extension",
                "install",
                "--target-root",
                str(target_root),
                "--extension",
                "codex-bridge",
            ]
        )

    assert exc_info.value.code == 0
    assert "Installed codex-bridge" in capsys.readouterr().out
    assert (target_root / "codex-bridge.ts").is_file()


def test_cli_exports_json_summary(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    output = tmp_path / "automata-core"

    with pytest.raises(SystemExit) as exc_info:
        app(
            [
                "plugin",
                "export",
                "--name",
                "automata-core",
                "--profile",
                "core",
                "--output",
                str(output),
                "--json",
            ]
        )

    assert exc_info.value.code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["name"] == "automata-core"
    assert summary["profile"] == "core"
    assert (output / "plugin.json").is_file()


def make_skill(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text("# Test Skill\n")
    return path
