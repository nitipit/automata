"""Private node admission and central directed initiation policy.

Version 2 compiles same-network defaults and exact allow/block exceptions once at
startup. Version 1 retains only its explicit grants: loading it never widens access.
Clients do not carry ACLs. Reply capabilities remain the routing core's concern.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .protocol import SESSION_RE

MAX_PARTICIPANTS = 128


@dataclass(frozen=True)
class Grant:
    kind: str
    token: str
    allow: frozenset[str]
    network: str | None = None  # None identifies the explicit-only v1 contract.


def valid_name(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SESSION_RE.fullmatch(value):
        raise ValueError(f"{label} must use 1–128 ASCII letters, numbers, '_' or '-'")
    return value


def validate_config(value: Any) -> dict[str, Grant]:
    if not isinstance(value, dict) or type(value.get("v")) is not int:
        raise ValueError("Expected version 1 participant or version 2 node configuration")
    if value["v"] == 1:
        if set(value) != {"v", "participants"}:
            raise ValueError("Expected version 1 participant configuration")
        return legacy_grants(value["participants"])
    if value["v"] != 2 or set(value) - {"v", "nodes", "allow", "block"} or "nodes" not in value:
        raise ValueError("Expected version 2 nodes, with optional allow and block pairs")
    nodes = validate_nodes(value["nodes"], legacy=False)
    allowed = validate_pairs(value.get("allow", []), nodes, "allow")
    blocked = validate_pairs(value.get("block", []), nodes, "block")
    return {
        source: Grant(
            spec["kind"], spec["token"],
            frozenset(
                target for target, destination in nodes.items()
                if (source, target) not in blocked and (
                    (source, target) in allowed or (
                        source != target and spec["network"] == destination["network"]
                    )
                )
            ),
            spec["network"],
        )
        for source, spec in nodes.items()
    }


def validate_nodes(value: Any, *, legacy: bool) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict) or not 1 <= len(value) <= MAX_PARTICIPANTS:
        raise ValueError("Configure 1–128 nodes")
    nodes, tokens = {}, set()
    for identity, spec in value.items():
        valid_name(identity, "Node ID")
        fields = {"kind", "token", "allow"} if legacy else {"kind", "token", "network"}
        if (not isinstance(spec, dict) or set(spec) - fields or "token" not in spec
                or (legacy and set(spec) != fields)):
            raise ValueError("Participant requires kind, token and allow" if legacy else
                             "Node requires token; kind and network are optional")
        kind = spec.get("kind", "node")
        if kind not in (("page", "agent") if legacy else ("node", "page", "agent")):
            raise ValueError("Invalid node kind")
        token = spec["token"]
        if (not isinstance(token, str) or not 32 <= len(token) <= 256
                or not token.isascii() or token in tokens):
            raise ValueError("Each node needs a distinct 32–256 character ASCII token")
        network = None if legacy else valid_name(spec.get("network", "default"), "Network")
        tokens.add(token)
        nodes[identity] = {**spec, "kind": kind, "network": network}
    return nodes


def validate_pairs(value: Any, nodes: dict, label: str) -> set[tuple[str, str]]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list of source:destination pairs")
    pairs = set()
    for pair in value:
        if not isinstance(pair, str):
            raise ValueError(f"{label} must name configured source:destination nodes")
        source, separator, target = pair.partition(":")
        if not separator or source not in nodes or target not in nodes:
            raise ValueError(f"{label} must name configured source:destination nodes")
        pairs.add((source, target))
    return pairs


def legacy_grants(value: Any) -> dict[str, Grant]:
    nodes = validate_nodes(value, legacy=True)
    grants = {}
    for identity, spec in nodes.items():
        allowed = spec["allow"]
        if not isinstance(allowed, list) or any(
            not isinstance(item, str) or item not in nodes for item in allowed
        ):
            raise ValueError("Allowed destinations must be configured participant IDs")
        grants[identity] = Grant(spec["kind"], spec["token"], frozenset(allowed))
    return grants
