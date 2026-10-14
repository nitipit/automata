"""Run the focused shared-template/browser proof."""

from pathlib import Path

import pytest

if __name__ == "__main__":
    raise SystemExit(pytest.main(["-q", str(Path(__file__).with_name("test_browser.py"))]))
