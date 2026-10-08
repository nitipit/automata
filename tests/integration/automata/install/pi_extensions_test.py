from pathlib import Path

import pytest

from automata.install.pi_extensions import (
    PiExtensionInstallError,
    bundled_pi_extension_root,
    install_pi_extensions,
    list_pi_extensions,
)


def test_bundled_pi_extension_root_is_under_pi_runtime() -> None:
    root = bundled_pi_extension_root()
    assert root.parts[-3:] == ("runtimes", "pi", "extensions")
    assert not root.joinpath("message-router").exists()
    assert not root.parent.parent.parent.joinpath("extensions").exists()


def test_install_pi_extensions_copies_bundled_codex_bridge(tmp_path: Path) -> None:
    target_root = tmp_path / ".pi" / "extensions"

    results = install_pi_extensions(target_root=target_root, extension_names=["codex-bridge"])

    assert [result.name for result in results] == ["codex-bridge"]
    assert (target_root / "codex-bridge.ts").is_file()


def test_install_pi_extensions_copies_bundled_skill_activity(tmp_path: Path) -> None:
    target_root = tmp_path / ".pi/extensions"
    results = install_pi_extensions(target_root=target_root, extension_names=["skill-activity"])

    assert [result.name for result in results] == ["skill-activity"]
    for name in ("index.ts", "store.py", "README.md"):
        installed = target_root / "skill-activity" / name
        assert installed.read_bytes() == (Path(results[0].source) / name).read_bytes()
    assert not (tmp_path / ".agents").exists()


@pytest.mark.parametrize("mode", ["copy", "symlink"])
def test_install_fast_mode_bundle(tmp_path: Path, mode: str) -> None:
    target = tmp_path / "extensions"
    results = install_pi_extensions(
        target_root=target, extension_names=["fast-mode"], mode=mode
    )
    assert [result.name for result in results] == ["fast-mode"]
    source = bundled_pi_extension_root() / "fast-mode"
    for name in ("index.ts", "README.md"):
        assert (target / "fast-mode" / name).read_bytes() == (source / name).read_bytes()
    assert (target / "fast-mode").is_symlink() == (mode == "symlink")
    assert not (tmp_path / ".agents").exists()


def test_install_pi_extensions_copies_bundled_context_status(tmp_path: Path) -> None:
    target_root = tmp_path / ".pi" / "extensions"

    results = install_pi_extensions(target_root=target_root, extension_names=["context-status"])

    assert [result.name for result in results] == ["context-status"]
    assert (target_root / "context-status.ts").is_file()
    assert not (target_root / "context-awareness.ts").exists()


def test_install_pi_extensions_copies_message_timestamps_with_updated_context_status(tmp_path):
    target = tmp_path / "extensions"
    results = install_pi_extensions(
        target_root=target, extension_names=["message-timestamps", "context-status"]
    )
    assert {r.name for r in results} == {"message-timestamps", "context-status"}
    root = bundled_pi_extension_root()
    for name in ("message-timestamps", "context-status"):
        assert (target / f"{name}.ts").read_bytes() == (root / f"{name}.ts").read_bytes()
    assert "Runtime local time:" not in (target / "context-status.ts").read_text()


def test_install_pi_extensions_copies_bundled_token_awareness(tmp_path: Path) -> None:
    target = tmp_path / "extensions"
    results = install_pi_extensions(target_root=target, extension_names=["token-awareness"])
    assert [result.name for result in results] == ["token-awareness"]
    assert (target / "token-awareness.ts").read_bytes() == (
        bundled_pi_extension_root() / "token-awareness.ts"
    ).read_bytes()
    assert not (tmp_path / ".agents").exists()


def test_install_pi_extensions_copies_bundled_context_compaction(tmp_path: Path) -> None:
    target_root = tmp_path / ".pi" / "extensions"

    results = install_pi_extensions(target_root=target_root, extension_names=["context-compaction"])

    assert [result.name for result in results] == ["context-compaction"]
    assert (target_root / "context-compaction.ts").is_file()


def test_retired_router_selection_fails_before_install(tmp_path: Path) -> None:
    target = tmp_path / "extensions"
    with pytest.raises(PiExtensionInstallError, match="Source Pi extension does not exist"):
        install_pi_extensions(target_root=target, extension_names=["message-router"])
    assert not target.exists()


def test_default_install_excludes_retired_control_without_uninstalling(tmp_path: Path) -> None:
    target = tmp_path / "extensions"
    retired = target / "thinking-control" / "index.ts"
    retired.parent.mkdir(parents=True)
    retired.write_text("// existing user installation\n")
    expected = {
        "codex-bridge", "context-compaction", "context-status", "fast-mode",
        "message-timestamps", "pi-sessions", "skill-activity", "token-awareness",
    }
    assert set(list_pi_extensions(bundled_pi_extension_root())) == expected
    results = install_pi_extensions(target_root=target)
    assert {result.name for result in results} == expected
    assert retired.read_text() == "// existing user installation\n"
    for result in results:
        source, installed = Path(result.source), Path(result.target)
        if source.is_file():
            assert installed.read_bytes() == source.read_bytes()
        else:
            for file in source.rglob("*"):
                if file.is_file():
                    assert (installed / file.relative_to(source)).read_bytes() == file.read_bytes()


def test_retired_control_selection_fails_before_install(tmp_path: Path) -> None:
    target = tmp_path / "extensions"
    with pytest.raises(PiExtensionInstallError, match="Source Pi extension does not exist"):
        install_pi_extensions(
            target_root=target, extension_names=["context-compaction", "thinking-control"]
        )
    assert not target.exists()


def test_install_pi_extensions_copies_bundled_pi_sessions(tmp_path: Path) -> None:
    target_root = tmp_path / ".pi" / "extensions"

    results = install_pi_extensions(target_root=target_root, extension_names=["pi-sessions"])

    assert [result.name for result in results] == ["pi-sessions"]
    assert (target_root / "pi-sessions.ts").is_file()
