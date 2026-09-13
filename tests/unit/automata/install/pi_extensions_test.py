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


def make_extension(path: Path) -> Path:
    path.parent.mkdir(parents=True)
    path.write_text("export default function () {}\n")
    return path
