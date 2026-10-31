"""Offline process/runtime boundaries; prerequisites are checked per suite."""

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "bundle,suite,libraries,native_pi",
    [
        ("nodalwire", "pi_compatibility.test.ts", ("edictor",), True),
    ],
    ids=["nodalwire-pi-compatibility"],
)
def test_extension_integration(
    run_extension_node, bundle: str, suite: str, libraries: tuple[str, ...], native_pi: bool
):
    run_extension_node(
        bundle, Path(__file__).parent / bundle / suite, libraries=libraries, native_pi=native_pi
    )
