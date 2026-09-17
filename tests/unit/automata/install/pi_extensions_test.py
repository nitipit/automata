from pathlib import Path

import pytest

from automata.install.pi_extensions import PiExtensionInstallError, install_pi_extensions


def test_install_pi_extensions_supports_custom_source_root(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    make_extension(source_root / "demo.ts")

    install_pi_extensions(
        source_root=source_root,
        target_root=tmp_path / "target",
        extension_names=["demo"],
    )

    assert (tmp_path / "target" / "demo.ts").is_file()


def test_install_pi_extensions_rejects_path_like_extension_name(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    make_extension(source_root / "demo.ts")

    with pytest.raises(PiExtensionInstallError, match="Invalid Pi extension name"):
        install_pi_extensions(
            source_root=source_root,
            target_root=tmp_path / "target",
            extension_names=["../demo"],
        )


def test_install_pi_extension_bundle_copy_replace_and_symlink(tmp_path: Path) -> None:
    source = tmp_path / "source"
    make_extension(source / "router" / "index.ts")
    (source / "router" / "protocol.ts").write_text("export const version = 2;\n")
    target = tmp_path / "target"
    installed = install_pi_extensions(source_root=source, target_root=target)
    assert [entry.name for entry in installed] == ["router"]
    assert (target / "router/protocol.ts").is_file()
    (target / "router/stale.ts").write_text("stale")
    install_pi_extensions(source_root=source, target_root=target, mode="replace")
    assert not (target / "router/stale.ts").exists()
    linked = tmp_path / "linked"
    install_pi_extensions(source_root=source, target_root=linked, mode="symlink")
    assert (linked / "router").is_symlink()
    assert (linked / "router/protocol.ts").is_file()


def test_extension_bundle_layout_ambiguity_and_preflight(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    make_extension(source / "router" / "index.ts")
    make_extension(source / "router.ts")
    with pytest.raises(PiExtensionInstallError, match="Ambiguous"):
        install_pi_extensions(source_root=source, target_root=target)
    assert not target.exists()
    (source / "router.ts").unlink()
    make_extension(target / "router.ts")
    with pytest.raises(PiExtensionInstallError, match="Conflicting"):
        install_pi_extensions(source_root=source, target_root=target, mode="replace")
    assert (target / "router.ts").is_file()
    assert not (target / "router").exists()
    with pytest.raises(PiExtensionInstallError, match="does not exist"):
        install_pi_extensions(
            source_root=source,
            target_root=tmp_path / "untouched",
            extension_names=["router", "missing"],
        )
    assert not (tmp_path / "untouched").exists()


def make_extension(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("export default function () {}\n")
    return path
