"""Selected-session recovery bundles in genuine freedesktop OS trash.

No deletion fallback, unrelated database snapshots, or arbitrary-path restore.
Native removal is permitted only after this durable recovery evidence exists.
"""

from __future__ import annotations

import configparser
import hashlib
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from urllib.parse import unquote

from session_store import absolute, recheck
from token_awareness import atomic_write
from token_records import CoverageError, session_id


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def prefix_digest(path, size):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while size:
            chunk = stream.read(min(size, 1024 * 1024))
            if not chunk:
                raise CoverageError("restored rollout prefix is incomplete")
            value.update(chunk)
            size -= len(chunk)
    return value.hexdigest()


def sync_directory(path):
    fd = os.open(path, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def signature(client, identity):
    # Native hydration proves usability rather than merely JSONL recoverability.
    thread = client.request("thread/read", {"threadId": identity, "includeTurns": True})["thread"]
    if thread["id"] != identity:
        raise CoverageError("native history identity mismatch")
    # Canonical full native history, including all message/tool payloads and
    # clocks. No fields are excluded as volatile; disagreement fails closed.
    canonical = json.dumps(
        thread["turns"], sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return {
        "sha256": hashlib.sha256(canonical).hexdigest(),
        "turnCount": len(thread["turns"]),
        "itemCount": sum(len(turn["items"]) for turn in thread["turns"]),
    }


def stage(state_root, root, selected, signatures, xdg_home, recovery=None):
    if not shutil.which("gio"):
        raise CoverageError("gio recoverable trash required; no deletion fallback")
    state_root, xdg_home = absolute(state_root), absolute(xdg_home)
    if xdg_home.is_relative_to(root) or root.is_relative_to(xdg_home):
        raise CoverageError("trash location must be separate from native store")
    xdg_home.mkdir(parents=True, exist_ok=True, mode=0o700)
    staging = state_root / "recovery-stage"
    index = state_root / "recoveries"
    staging.mkdir(exist_ok=True, mode=0o700)
    index.mkdir(exist_ok=True, mode=0o700)
    if staging.stat().st_dev != xdg_home.stat().st_dev:
        raise CoverageError("cross-filesystem recovery trash unsupported")
    recovery = session_id(recovery) if recovery else str(uuid.uuid4())
    package = staging / ("codex-session-" + recovery)
    package.mkdir(mode=0o700)
    entries = []
    for candidate in selected:
        recheck(root, candidate)
        filename = candidate["id"] + ".jsonl"
        source, target = Path(candidate["path"]), package / filename
        shutil.copyfile(source, target)
        target.chmod(0o600)
        with target.open("rb") as stream:
            os.fsync(stream.fileno())
        recheck(root, candidate)
        entries.append(
            {
                "candidate": candidate,
                "filename": filename,
                "sha256": digest(target),
                "signature": signatures[candidate["id"]],
                "status": "prepared",
            }
        )
    info = root.stat()
    manifest = {
        "version": 1,
        "runtime": "codex",
        "nativeVersion": "0.159.0",
        "recoveryId": recovery,
        "storeRoot": str(root),
        "rootIdentity": [info.st_dev, info.st_ino],
        "entries": entries,
    }
    atomic_write(package / "manifest.json", manifest)
    sync_directory(package)
    sync_directory(staging)
    trash_files = xdg_home / "Trash/files"
    trash_info = xdg_home / "Trash/info"
    trashed, info_path = trash_files / package.name, trash_info / (package.name + ".trashinfo")
    if trashed.exists() or info_path.exists():
        raise CoverageError("trash collision; package preserved without native deletion")
    receipt = {
        **manifest,
        "packagePath": str(trashed),
        "stagingPath": str(package),
        "trashInfoPath": str(info_path),
        "phase": "staged-not-removed",
    }
    receipt_path = index / (recovery + ".json")
    atomic_write(receipt_path, receipt)
    result = subprocess.run(
        ["gio", "trash", str(package)],
        capture_output=True,
        timeout=15,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(xdg_home.parent),
            "XDG_DATA_HOME": str(xdg_home),
            "GIO_USE_VFS": "local",
        },
    )
    if result.returncode or package.exists() or not trashed.is_dir() or not info_path.is_file():
        raise CoverageError("OS trash unverified; native deletion not attempted; package retained")
    config = configparser.ConfigParser(interpolation=None)
    config.read(info_path)
    if unquote(config["Trash Info"]["Path"]) != str(package) or not config["Trash Info"].get(
        "DeletionDate"
    ):
        raise CoverageError("OS trash metadata mismatch; native deletion not attempted")
    verify_package(receipt, trashed)
    sync_directory(trash_files)
    sync_directory(trash_info)
    receipt["phase"] = "recoverable-package-verified"
    atomic_write(receipt_path, receipt)
    return receipt_path, receipt


def verify_package(receipt, package):
    if package.is_symlink() or not package.is_dir():
        raise CoverageError("recovery package unavailable")
    manifest_path = package / "manifest.json"
    if manifest_path.is_symlink():
        raise CoverageError("symlinked recovery manifest")
    manifest = json.loads(manifest_path.read_text())
    for key in ("version", "runtime", "nativeVersion", "recoveryId", "storeRoot", "rootIdentity"):
        if manifest[key] != receipt[key]:
            raise CoverageError("recovery manifest identity mismatch")
    if len(manifest["entries"]) != len(receipt["entries"]):
        raise CoverageError("recovery entry mismatch")
    for saved, entry in zip(manifest["entries"], receipt["entries"], strict=True):
        for key in ("candidate", "filename", "sha256", "signature"):
            if saved[key] != entry[key]:
                raise CoverageError("recovery entry identity mismatch")
        identity = session_id(entry["candidate"]["id"])
        if entry["filename"] != identity + ".jsonl":
            raise CoverageError("invalid recovery filename")
        path = package / entry["filename"]
        if path.is_symlink() or not path.is_file() or digest(path) != entry["sha256"]:
            raise CoverageError("recovery payload changed")
    return package


def load_recovery(state_root, root, recovery):
    recovery = session_id(recovery)
    path = absolute(state_root) / "recoveries" / (recovery + ".json")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
        raise CoverageError("recovery receipt unavailable")
    receipt = json.loads(path.read_text())
    info = root.stat()
    if (
        receipt["version"] != 1
        or receipt["runtime"] != "codex"
        or receipt["nativeVersion"] != "0.159.0"
        or receipt["storeRoot"] != str(root)
        or receipt["recoveryId"] != recovery
        or receipt["rootIdentity"] != [info.st_dev, info.st_ino]
    ):
        raise CoverageError("recovery receipt root/identity mismatch")
    package = Path(receipt["packagePath"])
    # An owner may first restore the bundle through the desktop Trash UI. Only
    # its exact recorded staging destination is accepted, never arbitrary paths.
    if not package.exists():
        package = Path(receipt["stagingPath"])
    return path, receipt, verify_package(receipt, package)
