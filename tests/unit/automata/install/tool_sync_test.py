"""Opt-in tool preview/backups and recoverable replacement failures."""

from pathlib import Path

import pytest

from automata.install import tools


@pytest.fixture
def installation(tmp_path):
    source = tmp_path / "source" / "demo"
    source.mkdir(parents=True)
    (source / "version.txt").write_text("new\n")
    target = tmp_path / "installed" / "demo"
    target.mkdir(parents=True)
    (target / "version.txt").write_text("old\n")
    return source, target, tmp_path / "backups"


def replace(installation):
    source, target, backups = installation
    return tools.install_tools(
        source_root=source.parent,
        target_root=target.parent,
        tool_names=[source.name],
        mode="replace",
        backup_root=backups,
    )


def test_preview_does_not_create_target_or_backup(tmp_path):
    source = tmp_path / "source" / "demo"
    source.mkdir(parents=True)
    result = tools.install_tools(
        source_root=source.parent,
        target_root=tmp_path / "target",
        tool_names=["demo"],
        dry_run=True,
        backup_root=tmp_path / "backups",
    )
    assert isinstance(result[0], tools.ToolSyncResult)
    assert result[0].action == "add" and result[0].dry_run
    assert not (tmp_path / "target").exists()
    assert not (tmp_path / "backups").exists()


def test_backed_up_replacement_retains_old_bytes(installation):
    _, target, _ = installation
    result = replace(installation)[0]
    assert isinstance(result, tools.ToolSyncResult) and result.backup is not None
    assert result.action == "change"
    assert (target / "version.txt").read_text() == "new\n"
    assert (Path(result.backup) / "version.txt").read_text() == "old\n"
    assert not list(target.parent.glob(".tool-stage-*"))


def test_partial_copy_failure_leaves_old_tool_active(installation, monkeypatch):
    _, target, backups = installation

    def fail_copy(**kwargs):
        kwargs["target"].mkdir()
        (kwargs["target"] / "partial.txt").write_text("incomplete")
        raise OSError("injected copy failure")

    monkeypatch.setattr(tools, "install_one", fail_copy)
    with pytest.raises(tools.ToolInstallError, match="old tool is unchanged"):
        replace(installation)
    assert (target / "version.txt").read_text() == "old\n"
    assert not (target / "partial.txt").exists()
    assert not list(backups.glob("tools-*/demo"))
    assert not list(target.parent.glob(".tool-stage-*"))


def test_publication_failure_restores_old_tool(installation, monkeypatch):
    _, target, _ = installation

    def fail_publish(staged, destination):
        raise OSError("injected publication failure")

    monkeypatch.setattr(tools, "_publish_tool", fail_publish, raising=False)
    with pytest.raises(tools.ToolInstallError, match="old tool was restored"):
        replace(installation)
    assert (target / "version.txt").read_text() == "old\n"
    assert not list(target.parent.glob(".tool-stage-*"))


def test_failed_restore_reports_preserved_backup(installation, monkeypatch):
    _, target, backups = installation
    move = tools.shutil.move

    def fail_publish(staged, destination):
        raise OSError("injected publication failure")

    def fail_restore(source, destination):
        if Path(destination) == target:
            raise OSError("injected restore failure")
        return move(source, destination)

    monkeypatch.setattr(tools, "_publish_tool", fail_publish, raising=False)
    monkeypatch.setattr(tools.shutil, "move", fail_restore)
    with pytest.raises(tools.ToolInstallError, match="Restore failed") as error:
        replace(installation)
    backup = next(backups.glob("tools-*/demo"))
    assert str(backup) in str(error.value)
    assert (backup / "version.txt").read_text() == "old\n"
    assert not target.exists()


def test_failed_publication_never_deletes_an_unexpected_destination(installation, monkeypatch):
    _, target, backups = installation

    def competing_destination(staged, destination):
        destination.mkdir()
        (destination / "foreign.txt").write_text("other writer")
        raise OSError("destination appeared")

    monkeypatch.setattr(tools, "_publish_tool", competing_destination, raising=False)
    with pytest.raises(tools.ToolInstallError, match="not overwritten") as error:
        replace(installation)
    backup = next(backups.glob("tools-*/demo"))
    assert str(backup) in str(error.value)
    assert (target / "foreign.txt").read_text() == "other writer"
    assert (backup / "version.txt").read_text() == "old\n"


def test_symlink_backup_preserves_referent(installation, tmp_path):
    source, target, backups = installation
    (target / "version.txt").unlink()
    target.rmdir()
    referent = tmp_path / "referent"
    referent.mkdir()
    (referent / "private.txt").write_text("retain")
    target.symlink_to(referent, target_is_directory=True)
    result = replace((source, target, backups))[0]
    assert isinstance(result, tools.ToolSyncResult) and result.backup is not None
    backup = Path(result.backup)
    assert backup.is_symlink() and backup.resolve() == referent
    assert (referent / "private.txt").read_text() == "retain"
    assert not target.is_symlink()
    assert (target / "version.txt").read_text() == "new\n"


def test_publication_failure_restores_symlink(installation, tmp_path, monkeypatch):
    source, target, backups = installation
    (target / "version.txt").unlink()
    target.rmdir()
    referent = tmp_path / "referent"
    referent.mkdir()
    target.symlink_to(referent, target_is_directory=True)

    def fail_publish(staged, destination):
        raise OSError("injected publication failure")

    monkeypatch.setattr(tools, "_publish_tool", fail_publish, raising=False)
    with pytest.raises(tools.ToolInstallError, match="old tool was restored"):
        replace((source, target, backups))
    assert target.is_symlink() and target.resolve() == referent
    assert referent.is_dir()


def test_backup_file_rejected_before_any_installation(installation):
    source, target, backups = installation
    (source.parent / "added").mkdir()
    backups.write_text("not a directory")
    with pytest.raises(tools.ToolInstallError, match="Backup root must be a directory"):
        tools.install_tools(
            source_root=source.parent,
            target_root=target.parent,
            tool_names=["added", "demo"],
            mode="replace",
            backup_root=backups,
        )
    assert not (target.parent / "added").exists()
    assert (target / "version.txt").read_text() == "old\n"


def test_backup_overlap_refused_without_writes(installation):
    source, target, _ = installation
    with pytest.raises(tools.ToolInstallError, match="Backup root overlaps"):
        replace((source, target, target / "backups"))
    assert (target / "version.txt").read_text() == "old\n"


def test_whole_selection_preflight_refuses_missing_source(installation):
    source, target, _ = installation
    with pytest.raises(tools.ToolInstallError, match="Source tool directory does not exist"):
        tools.install_tools(
            source_root=source.parent,
            target_root=target.parent,
            tool_names=["demo", "missing"],
            dry_run=True,
        )
    assert (target / "version.txt").read_text() == "old\n"


def test_handled_publication_interrupt_restores_old_tool(installation, monkeypatch):
    _, target, _ = installation

    def interrupt_publish(staged, destination):
        raise KeyboardInterrupt()

    monkeypatch.setattr(tools, "_publish_tool", interrupt_publish)
    with pytest.raises(tools.ToolInstallError, match="KeyboardInterrupt.*old tool was restored"):
        replace(installation)
    assert (target / "version.txt").read_text() == "old\n"


def test_backup_move_failure_is_actionable_and_does_not_publish(installation, monkeypatch):
    _, target, backups = installation

    def fail_move(source, destination):
        raise OSError("backup denied")

    monkeypatch.setattr(tools.shutil, "move", fail_move)
    with pytest.raises(tools.ToolInstallError, match="Backup move failed") as error:
        replace(installation)
    assert str(target) in str(error.value)
    assert str(backups) in str(error.value)
    assert (target / "version.txt").read_text() == "old\n"
    assert not list(target.parent.glob(".tool-stage-*"))


def test_batch_failure_reports_earlier_applied_backup(installation, monkeypatch):
    source, target, backups = installation
    second = source.parent / "second"
    second.mkdir()
    (second / "version.txt").write_text("second new")
    installed_second = target.parent / "second"
    installed_second.mkdir()
    (installed_second / "version.txt").write_text("second old")
    install = tools.install_one

    def fail_second(**kwargs):
        if kwargs["name"] == "second":
            raise OSError("second copy failed")
        return install(**kwargs)

    monkeypatch.setattr(tools, "install_one", fail_second)
    with pytest.raises(
        tools.ToolInstallError, match="Earlier installations remain applied"
    ) as error:
        tools.install_tools(
            source_root=source.parent,
            target_root=target.parent,
            tool_names=["demo", "second"],
            mode="replace",
            backup_root=backups,
        )
    backup = next(backups.glob("tools-*/demo"))
    assert str(backup) in str(error.value)
    assert (backup / "version.txt").read_text() == "old\n"
    assert (target / "version.txt").read_text() == "new\n"
    assert (installed_second / "version.txt").read_text() == "second old"


@pytest.mark.parametrize("declaration", ["legacy", "deno"])
def test_staged_copy_preserves_manifest_and_bytecode_filters(installation, declaration):
    source, target, _ = installation
    (source / "private.txt").write_text("not included")
    (source / "module.pyc").write_bytes(b"bytecode")
    if declaration == "legacy":
        (source / ".automataignore").write_text("private.txt\n")
    else:
        (source / "deno.json").write_text(
            '{"exports":"./version.txt","publish":{"include":["version.txt"]}}'
        )
    replace(installation)
    assert (target / "version.txt").read_text() == "new\n"
    assert not (target / "private.txt").exists()
    assert not (target / "module.pyc").exists()
