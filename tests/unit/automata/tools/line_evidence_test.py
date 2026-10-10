"""Coverage/freshness semantics and Dictify contracts, without a browser."""

import sys
from pathlib import Path

import pytest

SOURCE = Path(__file__).parents[4] / "src/automata/tools/line"
sys.path.insert(0, str(SOURCE))
from line_contracts import ReadCoverage  # noqa: E402
from line_read_evidence import reading_evidence  # noqa: E402


def coverage(**changes):
    return dict(
        boundary_reached=False,
        reason="no_more_loaded_messages",
        checkpoint_found=False,
        history_gap=False,
        older_history_unverified=True,
        loaded_messages=2,
        more=False,
        attachments_reviewed=False,
        **changes,
    )


@pytest.mark.parametrize(
    ("latest", "newest", "expected"),
    [
        (None, 1791619277379, "unknown"),
        (1791619277000, 1791619277379, "unknown"),
        (1791619277379, 1791619277000, "unknown"),
        (1791619277000, 1791619277999, "unknown"),
        (1791619278000, 1791619277999, "newer_chat_list_evidence"),
        (1791619276000, 1791619277379, "unknown"),
        (1791619277000, None, "unknown"),
    ],
)
def test_chat_list_seconds_do_not_falsely_claim_freshness(latest, newest, expected):
    messages = [{"timestamp_ms": newest}] if newest is not None else []
    result = reading_evidence(coverage(), messages, "2026-10-10T08:51:36Z", latest)
    assert result["freshness"] == expected
    assert result["newest_loaded_timestamp_ms"] == newest
    assert result["observed_at"] == "2026-10-10T08:51:36Z"
    assert result["chat_list_latest_timestamp_ms"] == latest


def test_stall_is_not_complete_history_or_proof_of_no_older_messages():
    result = reading_evidence(coverage(), [{"timestamp_ms": 100}], "now", None)
    assert result["reason"] == "no_more_loaded_messages"
    assert result["older_history_availability"] == "unknown"
    assert result["older_history_unverified"] is True
    assert result["result_overflow"] is False
    assert result["requested_window"]["lower_boundary_reached"] is False
    assert result["requested_window"]["upper_boundary_reached"] is False
    assert result["requested_window"]["returned_all_loaded_matches"] is True


def test_overflow_is_independent_of_loading_stop_and_availability():
    base = coverage()
    base.update(reason="scroll_limit", more=True)
    result = reading_evidence(base, [{"timestamp_ms": 100}], "now", None)
    assert result["result_overflow"] is result["more"] is True
    assert result["older_history_availability"] == "unknown"
    assert result["requested_window"]["returned_all_loaded_matches"] is False


def test_explicit_window_boundaries_are_loaded_evidence_not_backend_freshness():
    result = reading_evidence(
        coverage(),
        [{"timestamp_ms": 90}, {"timestamp_ms": 110}],
        "now",
        None,
        since_ms=100,
        until_ms=110,
    )
    assert result["requested_window"]["lower_boundary_reached"] is True
    assert result["requested_window"]["upper_boundary_reached"] is True
    assert result["freshness"] == "unknown"
    assert result["older_history_availability"] == "unknown"


def test_missing_cursor_keeps_loaded_window_incomplete():
    base = coverage()
    base.update(cursor_found=False, history_gap=True, code="HISTORY_GAP")
    result = reading_evidence(base, [{"timestamp_ms": 100}], "now", None, after=(99, "missing"))
    assert result["requested_window"]["after"] == [99, "missing"]
    assert not result["requested_window"]["lower_boundary_reached"]
    assert not result["requested_window"]["returned_all_loaded_matches"]


def test_coverage_schema_rejects_divergent_overflow_alias():
    result = reading_evidence(coverage(), [], "now", None)
    result["more"] = True
    with pytest.raises(ValueError, match="alias"):
        ReadCoverage(result)
