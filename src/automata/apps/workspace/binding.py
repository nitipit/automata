"""Explicit private page credential bootstrap; no static endpoint-file serving."""
import json
import os
from pathlib import Path
from urllib.parse import urlparse


def read_binding() -> dict | None:
    path = os.environ.get("WORKSPACE_PAGE_ENDPOINT")
    if not path:
        return None
    endpoint = json.loads(Path(path).read_text())
    url = urlparse(endpoint.get("wsUrl", ""))
    if (url.scheme != "ws" or url.hostname != "127.0.0.1"
            or not url.port or url.username or url.password):
        raise ValueError("Binding requires a loopback router")
    if endpoint.get("kind") != "page":
        raise ValueError("Only page credentials may be supplied to Workspace")
    participant = endpoint.get("participant")
    token = endpoint.get("token")
    target = os.environ.get("WORKSPACE_AGENT_PARTICIPANT")
    agent_id = os.environ.get("WORKSPACE_AGENT_ID")
    if agent_id != "agent-automata" or target != "workspace-agent":
        raise ValueError("Explicit Automata assignment is required")
    if not all(isinstance(value, str) and value for value in (participant, token, target)):
        raise ValueError("Incomplete explicit binding")
    return {
        "conversationId": "conversation-aster", "agentId": agent_id,
        "displayName": "Automata", "to": target,
        "credentials": {"wsUrl": endpoint["wsUrl"], "participant": participant, "token": token},
    }
