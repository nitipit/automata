import json

import pytest

from automata.cli import app


def test_codex_installer_cli_is_explicit_and_does_not_activate(tmp_path, capsys):
    target = tmp_path / "assets"
    state = tmp_path / "state"
    with pytest.raises(SystemExit) as result:
        app(
            ["codex", "install", "--target-root", str(target), "--state-root", str(state), "--json"]
        )
    assert result.value.code == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt[0]["name"] == "codex"
    assert receipt[0]["target"] == str(target)
    assert (target / "hooks.json").is_file()
    assert (target / "README.md").is_file()
    assert not (target / "token-awareness").exists()
    assert not state.exists()
    assert not (tmp_path / "config.toml").exists()
