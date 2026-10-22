"""Offline process/runtime boundaries; prerequisites are checked per suite."""

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "bundle,suite,libraries,native_pi",
    [
        ("pi-agent-team", "rpc.test.ts", ("typebox",), False),
        ("pi-agent-team", "loader.test.ts", (), True),
        ("nodalwire", "pi_compatibility.test.ts", ("edictor",), True),
    ],
    ids=["pi-agent-team-rpc", "pi-agent-team-loader", "nodalwire-pi-compatibility"],
)
def test_extension_integration(
    run_extension_node, bundle: str, suite: str, libraries: tuple[str, ...], native_pi: bool
):
    run_extension_node(
        bundle, Path(__file__).parent / bundle / suite, libraries=libraries, native_pi=native_pi
    )
