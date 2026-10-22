"""Unit suites: Node and real libraries, without a Pi runtime, relay or model."""

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "bundle,suite,libraries",
    [
        ("pi-agent-team", "capture.test.ts", ()),
        ("pi-agent-team", "registration.test.ts", ("typebox",)),
        ("nodalwire", "protocol.test.ts", ("edictor",)),
        ("nodalwire", "messaging.test.ts", ("edictor", "typebox")),
    ],
    ids=[
        "pi-agent-team-capture", "pi-agent-team-registration",
        "nodalwire-protocol", "nodalwire-messaging",
    ],
)
def test_extension_unit(run_extension_node, bundle: str, suite: str, libraries: tuple[str, ...]):
    run_extension_node(bundle, Path(__file__).parent / bundle / suite, libraries=libraries)
