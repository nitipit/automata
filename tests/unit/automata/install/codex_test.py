"""Flat Codex installation: path selection, modes and preservation boundaries."""

import json
import shlex
import stat
from pathlib import Path

import pytest

from automata.install import codex
from automata.install.directory import DirectoryInstallError


def install(target, state, mode="copy"):
    return codex.install_codex(target_root=target, state_root=state, mode=mode)


def contents(root):
    return {name: (root / name).read_bytes() for name in codex.MANAGED_FILES}


@pytest.mark.parametrize("mode", ["copy", "replace", "symlink"])
def test_exact_root_preserves_unrelated_files_and_permissions(tmp_path, mode):
    target = tmp_path / "assets with ' quotes"
    target.mkdir(mode=0o750)
    (target / "notes").mkdir()
    unrelated = target / "notes/keep.txt"
    unrelated.write_text("keep")
    outside = tmp_path / "outside"
    outside.write_text("untouched")
    (target / "unrelated-link").symlink_to(outside)
    before = unrelated.stat()
    state = tmp_path / "private state"
    result = install(target, state, mode)
    assert result.name == "codex" and Path(result.target) == target
    assert not (target / "token-awareness").exists()
    assert not state.exists()
    assert stat.S_IMODE(target.stat().st_mode) == 0o750
    assert unrelated.read_text() == "keep" and unrelated.stat() == before
    assert (target / "unrelated-link").is_symlink()
    assert outside.read_text() == "untouched"
    source = Path(result.source)
    for name in codex.ASSET_FILES:
        assert (target / name).read_bytes() == (source / name).read_bytes()
        assert (target / name).is_symlink() == (mode == "symlink")
        assert stat.S_IMODE((target / name).stat().st_mode) == stat.S_IMODE(
            (source / name).stat().st_mode
        )
    fragment = target / "hooks.json"
    assert not fragment.is_symlink() and stat.S_IMODE(fragment.stat().st_mode) == 0o600
    for groups in json.loads(fragment.read_text())["hooks"].values():
        for hook, filename in zip(
            groups[0]["hooks"], ("token_awareness.py", "skill_activity.py"), strict=True
        ):
            assert shlex.split(hook["command"]) == [
                "python3", str(target / filename), "hook", "--state-root", str(state)
            ]
    assert not list(target.glob(".automata-codex-*"))


@pytest.mark.parametrize("mode", ["copy", "symlink"])
@pytest.mark.parametrize("kind", ["file", "dangling-link", "directory"])
def test_managed_collision_preflight_leaves_everything_untouched(tmp_path, mode, kind):
    target = tmp_path / "assets"
    target.mkdir()
    collision = target / "hooks.json"  # Last managed entry still blocks all writes.
    if kind == "file":
        collision.write_text("custom")
    elif kind == "dangling-link":
        collision.symlink_to(tmp_path / "absent")
    else:
        collision.mkdir()
    with pytest.raises(DirectoryInstallError, match="already exists"):
        install(target, tmp_path / "state", mode)
    assert set(target.iterdir()) == {collision}
    if kind == "file":
        assert collision.read_text() == "custom"
    elif kind == "dangling-link":
        assert collision.is_symlink() and not collision.exists()
    else:
        assert collision.is_dir()


def test_replace_rejects_directory_without_partial_update(tmp_path):
    target = tmp_path / "assets"
    install(target, tmp_path / "state")
    (target / "token_records.py").write_text("old")
    (target / "hooks.json").unlink()
    (target / "hooks.json").mkdir()
    (target / "hooks.json/keep").write_text("private")
    with pytest.raises(DirectoryInstallError, match="not a file"):
        install(target, tmp_path / "state", "replace")
    assert (target / "token_records.py").read_text() == "old"
    assert (target / "hooks.json/keep").read_text() == "private"


@pytest.mark.parametrize("kind", ["symlink", "dangling-link", "hardlink"])
def test_replace_does_not_write_through_managed_links(tmp_path, kind):
    target = tmp_path / "assets"
    target.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("keep outside")
    destination = target / "hooks.json"
    if kind == "hardlink":
        destination.hardlink_to(outside)
    else:
        destination.symlink_to(outside if kind == "symlink" else tmp_path / "absent")
    install(target, tmp_path / "state", "replace")
    assert outside.read_text() == "keep outside"
    assert not (tmp_path / "absent").exists()
    assert destination.is_file() and not destination.is_symlink()
    assert destination.stat().st_ino != outside.stat().st_ino


def test_replace_symlink_install_preserves_source_and_external_state(tmp_path):
    target, state = tmp_path / "assets", tmp_path / "state"
    install(target, state, "symlink")
    before = contents(target)
    source = (target / "token_records.py").resolve()
    state.mkdir()
    (state / "keep.json").write_text("saved")
    install(target, state, "replace")
    assert contents(target) == before
    assert not (target / "token_records.py").is_symlink()
    assert source.read_bytes() == before["token_records.py"]
    assert (state / "keep.json").read_text() == "saved"


@pytest.mark.parametrize("kind", ["file", "symlink", "dangling-link"])
def test_invalid_target_root_is_not_replaced(tmp_path, kind):
    target, outside = tmp_path / "assets", tmp_path / "outside"
    if kind == "file":
        target.write_text("keep")
    else:
        if kind == "symlink":
            outside.mkdir()
        target.symlink_to(outside, target_is_directory=True)
    with pytest.raises(DirectoryInstallError, match="non-symlink directory"):
        install(target, tmp_path / "state", "replace")
    if kind == "file":
        assert target.read_text() == "keep"
    else:
        assert target.is_symlink()
        assert not outside.exists() or not list(outside.iterdir())


@pytest.mark.parametrize("kind", ["equal", "nested", "alias"])
def test_state_inside_target_rejected_before_writes(tmp_path, kind):
    target = tmp_path / "assets"
    state = target if kind == "equal" else target / "state"
    if kind == "alias":
        state = tmp_path / "state-link"
        state.symlink_to(target, target_is_directory=True)
    with pytest.raises(DirectoryInstallError, match="state must be outside"):
        install(target, state)
    assert not target.exists()


def test_preparation_failure_does_not_replace_existing_files(tmp_path, monkeypatch):
    target = tmp_path / "assets"
    install(target, tmp_path / "state")
    before = contents(target)
    original = codex.shutil.copy2

    def fail_late(source, destination):
        if source.name == "setup.md":
            raise OSError("fixture copy failure")
        return original(source, destination)

    monkeypatch.setattr(codex.shutil, "copy2", fail_late)
    with pytest.raises(OSError, match="fixture copy failure"):
        install(target, tmp_path / "state", "replace")
    assert contents(target) == before
    assert set(p.name for p in target.iterdir()) == set(codex.MANAGED_FILES)


def test_flat_install_does_not_implicitly_migrate_legacy_directory(tmp_path):
    target, state = tmp_path / "assets", tmp_path / "state"
    legacy = target / "token-awareness"
    install(legacy, state)
    before = contents(legacy)
    (legacy / "private-notes").write_text("keep")
    install(target, state)
    for name in codex.ASSET_FILES:
        assert (target / name).read_bytes() == before[name]
    assert contents(legacy) == before
    assert (legacy / "private-notes").read_text() == "keep"
    assert str(legacy) not in (target / "hooks.json").read_text()
    assert not state.exists()


def test_source_overlap_is_rejected():
    source = Path(str(codex.files("automata").joinpath("runtimes", "codex")))
    for target in (source, source / "nested", source.parent):
        with pytest.raises(DirectoryInstallError, match="overlap bundled source"):
            install(target, source.parent.parent / "state", "replace")
