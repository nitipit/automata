from pathlib import Path

from automata.install.pi_extensions import install_pi_extensions


def test_install_pi_extensions_copies_bundled_codex_bridge(tmp_path: Path) -> None:
    target_root = tmp_path / ".pi" / "extensions"

    results = install_pi_extensions(target_root=target_root, extension_names=["codex-bridge"])

    assert [result.name for result in results] == ["codex-bridge"]
    assert (target_root / "codex-bridge.ts").is_file()


def test_install_pi_extensions_copies_bundled_context_status(tmp_path: Path) -> None:
    target_root = tmp_path / ".pi" / "extensions"

    results = install_pi_extensions(target_root=target_root, extension_names=["context-status"])

    assert [result.name for result in results] == ["context-status"]
    assert (target_root / "context-status.ts").is_file()
    assert not (target_root / "context-awareness.ts").exists()


def test_install_pi_extensions_copies_bundled_context_compaction(tmp_path: Path) -> None:
    target_root = tmp_path / ".pi" / "extensions"

    results = install_pi_extensions(target_root=target_root, extension_names=["context-compaction"])

    assert [result.name for result in results] == ["context-compaction"]
    assert (target_root / "context-compaction.ts").is_file()


def test_install_pi_extensions_copies_bundled_agent_browser_bridge(tmp_path: Path) -> None:
    target_root = tmp_path / ".pi" / "extensions"

    results = install_pi_extensions(target_root=target_root, extension_names=["agent-router"])

    assert [result.name for result in results] == ["agent-router"]
    for file in ("index.ts", "transport.ts", "protocol.ts"):
        assert (target_root / "agent-router" / file).is_file()
    assert not (target_root / "agent-browser-bridge.ts").exists()
    assert not (tmp_path / ".agents" / "var").exists()


def test_install_pi_extensions_copies_bundled_pi_sessions(tmp_path: Path) -> None:
    target_root = tmp_path / ".pi" / "extensions"

    results = install_pi_extensions(target_root=target_root, extension_names=["pi-sessions"])

    assert [result.name for result in results] == ["pi-sessions"]
    assert (target_root / "pi-sessions.ts").is_file()
