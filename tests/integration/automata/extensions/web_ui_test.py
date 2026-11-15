"""Installed Pi loader check, without browser host or provider requests."""
from pathlib import Path


def test_web_ui_pi_loader(run_extension_node):
    run_extension_node(
        "web-ui", Path(__file__).parent / "web-ui" / "pi_loader.test.ts", native_pi=True
    )
