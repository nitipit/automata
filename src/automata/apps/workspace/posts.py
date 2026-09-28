"""Conversation post contract and atomic idempotency inside the workspace value.

Router provenance is supplied by the private adapter, never by an HTTP caller.
A saved receipt describes persistence only, not delivery or task completion.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from .schemas import IDENTIFIER, validate_message

CONTEXT = {"projectId": "project-northstar", "conversationId": "conversation-aster"}


def agent_author(provenance: dict) -> dict:
    if (not isinstance(provenance, dict) or provenance.get("kind") != "agent"
            or provenance.get("id") != "workspace-agent"
            or not isinstance(provenance.get("sessionId"), str)
            or not IDENTIFIER.fullmatch(provenance["sessionId"])):
        raise ValueError("Unauthorized conversation author")
    return {"agentId": "agent-automata", "participant": provenance["id"],
            "sessionId": provenance["sessionId"]}


def validate_post(value: dict, *, agent: bool) -> dict:
    if not isinstance(value, dict) or set(value) != {"operationId", "context", "content"}:
        raise ValueError("Post requires operationId, context and content only")
    operation = value["operationId"]
    context = value["context"]
    if not isinstance(operation, str) or not IDENTIFIER.fullmatch(operation):
        raise ValueError("Invalid operationId")
    if (not isinstance(context, dict) or set(context) - {*CONTEXT, "webboardId"}
            or any(context.get(key) != expected for key, expected in CONTEXT.items())
            or ("webboardId" in context and context["webboardId"] != "main")):
        raise ValueError("Post destination is not authorized")
    content = value["content"]
    validate_message({"id": "validation", "operationId": operation,
                      "role": "agent" if agent else "user", "text": "", "content": content})
    if content is None:
        raise ValueError("Post content is required")
    for item in content:
        if set(item) != {"id", "type", "version", "data"} or item["version"] != 1:
            raise ValueError("Invalid post content item")
        if item["type"] not in ({"text", "form"} if agent else {"text", "form-response"}):
            raise ValueError("Unsupported post content type")
        if item["type"] == "text":
            text = item["data"].get("text")
            if (set(item["data"]) != {"text"} or not isinstance(text, str)
                    or not text.strip() or len(text) > 6000):
                raise ValueError("Text requires 1–6000 characters")
        if item["type"] == "form-response":
            data = item["data"]
            if (set(data) != {"messageId", "componentId", "definition", "values"}
                    or not all(isinstance(data[k], str) and IDENTIFIER.fullmatch(data[k])
                               for k in ("messageId", "componentId"))
                    or not isinstance(data["definition"], dict)
                    or not isinstance(data["values"], dict)
                    or any(not isinstance(k, str) or not isinstance(v, str) or len(v) > 6000
                           for k, v in data["values"].items())):
                raise ValueError("Invalid form response content")
    # Detach caller data and reject non-JSON numbers before hashing/persisting.
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def normalize_posts(state: dict) -> dict:
    """Deterministic additive v2 migration; no invented historical timestamps."""
    state.setdefault("postOperations", {})
    for row in state["conversations"].values():
        for sequence, message in enumerate(row["messages"], 1):
            message.setdefault("messageId", message["id"])
            message.setdefault("seq", sequence)
            message.setdefault("createdAt", None)
    return state


def apply_post(state: dict, envelope: dict, author: dict | None) -> dict:
    """Mutate a transaction-local state, returning the original receipt on retry."""
    value = validate_post(envelope, agent=author is not None)
    identity = author["participant"] if author else "local-user"
    scope = json.dumps([identity, value["context"], value["operationId"]], sort_keys=True)
    key = hashlib.sha256(scope.encode()).hexdigest()
    digest = hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                      separators=(",", ":")).encode()).hexdigest()
    operations = state.setdefault("postOperations", {})
    existing = operations.get(key)
    if existing:
        if existing["digest"] != digest:
            raise ValueError("Operation ID already belongs to a different payload")
        return existing["receipt"]
    row = state["conversations"][value["context"]["conversationId"]]
    for item in value["content"]:
        if item["type"] == "form-response":
            data = item["data"]
            source = next((m for m in row["messages"] if m["id"] == data["messageId"]), None)
            definition = next((c for c in (source or {}).get("content", [])
                               if c["id"] == data["componentId"] and c["type"] == "form"), None)
            if not definition or definition["data"] != data["definition"]:
                raise ValueError("Form response does not match saved component")
            prior = source.get("interactions", {}).get(data["componentId"])
            if prior and prior["status"] != "draft":
                raise ValueError("Form was already submitted; do not replay")
    message_id = str(uuid4())
    sequence = max((m.get("seq", 0) for m in row["messages"]), default=0) + 1
    created = datetime.now(UTC).isoformat()
    receipt = {"status": "saved", "operationId": value["operationId"],
               "messageId": message_id, "seq": sequence, "createdAt": created,
               "context": value["context"]}
    text = "\n".join(item["data"]["text"] for item in value["content"] if item["type"] == "text")
    message = {"id": message_id, "messageId": message_id, "seq": sequence,
               "createdAt": created, "operationId": value["operationId"],
               "context": value["context"], "role": "agent" if author else "user",
               "text": text[:6000], "content": value["content"], "serverOwned": True,
               "provenance": "authenticated-agent-post" if author else "local-user-post"}
    if author:
        message["author"] = author
    else:
        message["delivery"] = {"status": "pending", "operationId": value["operationId"],
                               "detail": "Saved; agent delivery not confirmed"}
        for item in value["content"]:
            if item["type"] == "form-response":
                data = item["data"]
                source = next(m for m in row["messages"] if m["id"] == data["messageId"])
                source.setdefault("interactions", {})[data["componentId"]] = {
                    "status": "pending", "operationId": value["operationId"],
                    "values": data["values"], "detail": "Saved; agent delivery not confirmed"}
    row["messages"].append(message)
    operations[key] = {"digest": digest, "receipt": receipt}
    state["revision"] += 1
    return receipt


def guard_browser_save(incoming: dict, current: dict) -> None:
    """CAS alone cannot stop a current-revision client forging/removing posts."""
    if incoming.get("postOperations", {}) != current.get("postOperations", {}):
        raise ValueError("Conversation operation records are backend-owned")
    for key, row in current["conversations"].items():
        proposed = incoming["conversations"][key]["messages"]
        existing = row["messages"]
        if len(proposed) != len(existing):
            raise ValueError("Conversation messages are backend-owned")
        def immutable(message):
            return {k: v for k, v in message.items() if k not in {"interactions", "delivery"}}
        for old, new in zip(existing, proposed, strict=True):
            if immutable(old) != immutable(new):
                raise ValueError("Conversation content is backend-owned")
            for component, prior in old.get("interactions", {}).items():
                if prior.get("status") == "draft":
                    continue
                updated = new.get("interactions", {}).get(component, {})
                if (updated.get("status") == "draft"
                        or updated.get("operationId") != prior.get("operationId")
                        or updated.get("values") != prior.get("values")
                        or not updated):
                    raise ValueError("Submitted component values cannot be reset or replayed")
