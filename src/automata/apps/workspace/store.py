"""Durable project state in one atomic ShelfDB value."""

from __future__ import annotations

import json
import re
from pathlib import Path
from threading import RLock
from typing import Any

from dictify import Field, Model
from shelfdb.shelf import DB

from .schemas import normalize_message, validate_message

PROJECT_ID = "project-northstar"
AGENTS = {"agent-a": "Aster", "agent-b": "Mira"}
CONVERSATIONS = {"conversation-aster": "agent-a", "conversation-mira": "agent-b"}


class WorkspaceState(Model):
    """Validated top-level state envelope. Nested fields get domain checks below."""

    version = Field(required=True).instance(int).verify(lambda value: value == 2)
    revision = Field(required=True).instance(int).verify(lambda value: value >= 0)
    projectId = Field(required=True).instance(str).verify(lambda value: value == PROJECT_ID)
    artifact = Field(required=True).instance(dict)
    conversations = Field(required=True).instance(dict)
    view = Field(required=True).instance(dict)


def default_state() -> dict[str, Any]:
    return {
        "version": 2,
        "revision": 0,
        "projectId": PROJECT_ID,
        "artifact": {
            "id": "artifact-launch-brief",
            "title": "Launch brief",
            "content": (
                "Northstar launch\n\nA clear, calm home for teams to turn early thinking "
                "into shipped work."
                "\n\n## This week\n- Align on the smallest useful launch"
                "\n- Validate the onboarding flow\n- Share a first draft with the team"
            ),
        },
        "conversations": {
            conversation_id: {
                "id": conversation_id,
                "agentId": agent_id,
                "sessionId": f"session-{agent_id}-simulated",
                "draft": "",
                "messages": [],
            }
            for conversation_id, agent_id in CONVERSATIONS.items()
        },
        "view": {
            "selectedArtifactId": "artifact-launch-brief",
            "selectedConversationId": "conversation-aster",
        },
    }


def _load_state(value: Any) -> dict[str, Any]:
    """Validate then add component descriptions without altering legacy text/drafts.

    Read normalization is not a DB rewrite. A subsequent explicit save persists the
    additive fields in v2, which older readers continue to accept via text fallback.
    """
    state = validate_state(value)
    for row in state["conversations"].values():
        row["messages"] = [normalize_message(message) for message in row["messages"]]
    return state


def validate_state(value: Any) -> dict[str, Any]:
    """Reject malformed or unexpected identities before any durable write."""
    try:
        validated = dict(WorkspaceState(value))
    except (Model.Error, TypeError, ValueError) as error:
        raise ValueError("Invalid workspace state envelope") from error
    if type(validated["revision"]) is not int or validated["revision"] < 0:
        raise ValueError("Invalid workspace revision")
    artifact = validated["artifact"]
    if (
        artifact.get("id") != "artifact-launch-brief"
        or not isinstance(artifact.get("title"), str)
        or not isinstance(artifact.get("content"), str)
        or len(artifact["content"]) > 50_000
    ):
        raise ValueError("Invalid shared artifact")
    conversations = validated["conversations"]
    if set(conversations) != set(CONVERSATIONS):
        raise ValueError("Workspace must contain exactly the two simulated conversations")
    for conversation_id, agent_id in CONVERSATIONS.items():
        row = conversations[conversation_id]
        if not isinstance(row, dict):
            raise ValueError(f"Invalid conversation {conversation_id}")
        if (
            row.get("id") != conversation_id
            or row.get("agentId") != agent_id
            or row.get("sessionId") != f"session-{agent_id}-simulated"
            or not isinstance(row.get("draft"), str)
            or len(row["draft"]) > 6000
            or not isinstance(row.get("messages"), list)
        ):
            raise ValueError(f"Invalid conversation {conversation_id}")
        ids = set()
        for message in row["messages"]:
            validate_message(message)
            if "author" in message and conversation_id != "conversation-aster":
                raise ValueError("Assigned agent does not own this conversation")
            if message["id"] in ids:
                raise ValueError(f"Duplicate message in {conversation_id}")
            ids.add(message["id"])
    view = validated["view"]
    if (
        set(view) != {"selectedArtifactId", "selectedConversationId"}
        or view.get("selectedArtifactId") != "artifact-launch-brief"
        or view.get("selectedConversationId") not in CONVERSATIONS
    ):
        raise ValueError("Invalid workspace view state")
    return validated


class WorkspaceStore:
    """Serialize reads/writes; one ShelfDB shelf value changes per transaction."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = RLock()
        path.mkdir(parents=True, exist_ok=True, mode=0o700)

    def load(self) -> dict[str, Any]:
        with self._lock:
            if not (self.path / "data.mdb").exists():
                return default_state()
            try:
                with DB(str(self.path)) as database, database.transaction(write=False) as tx:
                    item = tx.shelf("workspace").key(PROJECT_ID).item()
                    if item is None:
                        return default_state()
                    return _load_state(item.value)
            except (OSError, RuntimeError, ValueError, Model.Error) as error:
                raise RuntimeError("Saved workspace state could not be read") from error

    def save(self, value: Any) -> dict[str, Any]:
        state = validate_state(value)
        with self._lock:
            try:
                expected = state["revision"]
                with DB(str(self.path)) as database, database.transaction(write=True) as tx:
                    shelf = tx.shelf("workspace")
                    selected = shelf.key(PROJECT_ID)
                    current = (
                        _load_state(selected.item().value)
                        if selected.exists()
                        else default_state()
                    )
                    if expected != current["revision"]:
                        raise RevisionConflict(current["revision"])
                    state["revision"] = expected + 1
                    encoded = json.loads(json.dumps(state, ensure_ascii=False))
                    result = shelf.put(PROJECT_ID, encoded)
                    if not result.ok:
                        raise RuntimeError("ShelfDB rejected the workspace update")
                return encoded
            except RevisionConflict:
                raise
            except (OSError, RuntimeError, ValueError, Model.Error) as error:
                raise RuntimeError("Workspace changes were not saved") from error


class RevisionConflict(RuntimeError):
    """A client's whole-state update was based on an older durable revision."""

    def __init__(self, current_revision: int):
        self.current_revision = current_revision
        super().__init__(f"Workspace changed elsewhere (current revision {current_revision})")


_OPERATION = re.compile(r"^[a-zA-Z0-9_-]{8,100}$")


def simulated_reply(text: str, agent_name: str) -> str:
    """Clearly fake, deterministic response; never invokes a real agent."""
    excerpt = " ".join(text.split())[:120]
    return f"[Simulation] {agent_name} noted: “{excerpt}”. No real agent was contacted."


def append_message(
    store: WorkspaceStore, envelope: Any
) -> tuple[dict[str, Any], bool]:
    """Persist one idempotent local simulation, refusing ambiguous operation reuse."""
    if not isinstance(envelope, dict):
        raise ValueError("Expected a message-router-shaped envelope")
    conversation_id = envelope.get("conversationId")
    operation_id = envelope.get("clientOperationId")
    payload = envelope.get("payload")
    if not isinstance(conversation_id, str):
        raise ValueError("Conversation ID must be a string")
    if not isinstance(operation_id, str) or not _OPERATION.fullmatch(operation_id):
        raise ValueError("Invalid client operation ID")
    agent_id = CONVERSATIONS.get(conversation_id)
    if (
        envelope.get("projectId") != PROJECT_ID
        or agent_id is None
        or envelope.get("agentId") != agent_id
        or not isinstance(payload, dict)
    ):
        raise ValueError("Message envelope does not match the selected project and recipient")
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip() or len(text) > 6000:
        raise ValueError("Message must contain 1–6000 characters")
    with store._lock:
        state = store.load()
        row = state["conversations"][conversation_id]
        existing = [m for m in row["messages"] if m["operationId"] == operation_id]
        if existing:
            if existing[0]["text"] != text:
                raise ValueError("Operation ID already belongs to a different message")
            return state, True
        agent_id = CONVERSATIONS[conversation_id]
        row["messages"].extend([
            {"id": f"message-{operation_id}", "operationId": operation_id,
             "role": "user", "text": text},
            {"id": f"reply-{operation_id}", "operationId": operation_id,
             "role": "agent", "text": simulated_reply(text, AGENTS[agent_id])},
        ])
        row["draft"] = ""
        saved = store.save(state)
        return saved, False
