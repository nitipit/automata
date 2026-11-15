"""Offline browser connector checks; no host/browser/model is started."""
from pathlib import Path

import pytest


@pytest.mark.parametrize("suite,libraries", [("connector.test.ts", ()), ("tools.test.ts", ("typebox",))])
def test_web_ui_connector(run_extension_node, suite, libraries):
    run_extension_node("web-ui", Path(__file__).parent / "web-ui" / suite, libraries=libraries)
