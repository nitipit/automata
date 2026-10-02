"""Private, bounded local pairing state. Secrets are hashed; malformed state fails closed."""
from __future__ import annotations

import hashlib
import json
import math
import os
import secrets
import tempfile
import time
from pathlib import Path
from typing import Any

from .protocol import reject_json_constant, strict_object_pairs

MAX_CODES = 32
MAX_SESSIONS = 128


def digest(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


class AuthStore:
    def __init__(self, directory: Path, pages: set[str], *, session_seconds: int = 604800,
                 code_seconds: int = 300):
        try:
            import fcntl  # Unix-only dependency belongs to the opt-in constructor.
        except ImportError:
            raise ValueError("Local browser auth requires Unix file locks and sockets") from None
        if not 1 <= session_seconds <= 31536000 or not 1 <= code_seconds <= 3600:
            raise ValueError("Auth lifetimes must be positive (session ≤1 year, code ≤1 hour)")
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.directory.stat().st_mode & 0o077:
            raise ValueError("Auth directory must have private mode 0700")
        self.pages = pages
        self.session_seconds, self.code_seconds = session_seconds, code_seconds
        self.path = self.directory / "state.json"
        if self.path.is_symlink() or (self.directory / "owner.lock").is_symlink():
            raise ValueError("Private auth files must not be symlinks")
        self.lock = os.open(self.directory / "owner.lock", os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.state = self.load()
            self.prune()
            self.save()
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        if self.lock is not None:
            os.close(self.lock)
            self.lock = None

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"v": 1, "codes": {}, "sessions": {}}
        try:
            if self.path.stat().st_mode & 0o077 or self.path.stat().st_size > 131072:
                raise ValueError("Unsafe auth state")
            value = json.loads(self.path.read_text(), object_pairs_hook=strict_object_pairs,
                               parse_constant=reject_json_constant)
            if (not isinstance(value, dict) or set(value) != {"v", "codes", "sessions"}
                    or type(value["v"]) is not int or value["v"] != 1):
                raise ValueError("Invalid auth state")
            session_ids = set()
            for kind, limit in (("codes", MAX_CODES), ("sessions", MAX_SESSIONS)):
                records = value[kind]
                if not isinstance(records, dict) or len(records) > limit:
                    raise ValueError("Invalid auth records")
                for key, record in records.items():
                    fields = {"participant", "expiresAt", "attempts" if kind == "codes" else "id"}
                    if (len(key) != 64 or any(c not in "0123456789abcdef" for c in key)
                            or not isinstance(record, dict) or set(record) != fields
                            or record["participant"] not in self.pages
                            or type(record["expiresAt"]) not in (int, float)
                            or not math.isfinite(record["expiresAt"])):
                        raise ValueError("Invalid auth record")
                    if kind == "codes":
                        if type(record["attempts"]) is not int or not 1 <= record["attempts"] <= 5:
                            raise ValueError("Invalid pairing budget")
                    else:
                        identity = record["id"]
                        if (not isinstance(identity, str) or len(identity) != 32
                                or any(c not in "0123456789abcdef" for c in identity)
                                or identity in session_ids):
                            raise ValueError("Invalid or duplicate session identifier")
                        session_ids.add(identity)
            return value
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise ValueError(
                "Auth state malformed or unsafe; explicit operator repair required") from error

    def save(self) -> None:
        fd, temporary = tempfile.mkstemp(prefix=".state-", dir=self.directory)
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(self.state, handle, allow_nan=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def prune(self) -> None:
        now = time.time()
        for kind in ("codes", "sessions"):
            self.state[kind] = {key: record for key, record in self.state[kind].items()
                                if record["expiresAt"] > now}

    def pair_code(self, participant: str) -> dict[str, Any]:
        if participant not in self.pages:
            raise ValueError("Pairing requires a configured page participant")
        self.prune()
        if len(self.state["codes"]) >= MAX_CODES:
            raise ValueError("Pairing capacity reached")
        code = secrets.token_urlsafe(32)
        expires = time.time() + self.code_seconds
        self.state["codes"][digest(code)] = {
            "participant": participant, "expiresAt": expires, "attempts": 5,
        }
        self.save()
        return {"code": code, "participant": participant, "expiresAt": expires}

    def exchange(self, code: str) -> tuple[str, dict[str, Any]]:
        self.prune()
        record = self.state["codes"].get(digest(code))
        if record is None:
            # A bounded global guess budget: random invalid codes consume every active
            # code's budget. Only a private operator can issue a fresh code.
            for key, entry in list(self.state["codes"].items()):
                entry["attempts"] -= 1
                if not entry["attempts"]:
                    del self.state["codes"][key]
            self.save()
            raise ValueError("Invalid, expired or consumed pairing code")
        return self.issue_session(record["participant"], code_key=digest(code))

    def issue_session(self, participant: str, *, code_key: str | None = None) -> tuple[str, dict]:
        """Persist one session; callers own approval/exclusivity and cookie delivery."""
        if participant not in self.pages:
            raise ValueError("Session requires a configured page")
        self.prune()
        if len(self.state["sessions"]) >= MAX_SESSIONS:
            raise ValueError("Session capacity reached")
        token = secrets.token_urlsafe(32)
        session = {"id": secrets.token_hex(16), "participant": participant,
                   "expiresAt": time.time() + self.session_seconds}
        if code_key is not None:
            del self.state["codes"][code_key]
        self.state["sessions"][digest(token)] = session
        self.save()
        return token, session

    def session(self, token: str) -> dict[str, Any] | None:
        record = self.state["sessions"].get(digest(token))
        return record if record and record["expiresAt"] > time.time() else None

    def revoke(self, *, token: str | None = None, participant: str | None = None,
               session_id: str | None = None) -> list[str]:
        revoked = []
        for key, record in list(self.state["sessions"].items()):
            if ((token is not None and key == digest(token))
                    or (participant is not None and record["participant"] == participant)
                    or (session_id is not None and record["id"] == session_id)):
                revoked.append(record["id"])
                del self.state["sessions"][key]
        self.prune()
        self.save()
        return revoked
