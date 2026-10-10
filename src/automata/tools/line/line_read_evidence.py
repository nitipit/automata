"""Describe loaded evidence without inferring server freshness or complete history."""

from line_contracts import ReadCoverage


def chat_list_latest(page, row_selector, chat_id):
    """Inspect only already-visible chat rows; do not navigate or refresh LINE."""
    rows = page.locator(row_selector).evaluate_all(
        """(rows, id) => rows
      .filter(e => e.dataset.mid === id)
      .map(e => Date.parse(e.querySelector('time')?.getAttribute('datetime')) || null)
    """,
        chat_id,
    )
    return rows[0] if len(rows) == 1 and type(rows[0]) is int and rows[0] > 0 else None


def reading_evidence(
    coverage,
    messages,
    observed_at,
    listed_latest,
    since_ms=None,
    until_ms=None,
    before=None,
    after=None,
):
    """List times have second precision. Equal seconds establish no freshness claim."""
    stamps = [m["timestamp_ms"] for m in messages]
    newest = max(stamps) if stamps else None
    oldest = min(stamps) if stamps else None
    freshness = "unknown"
    if listed_latest is not None and newest is not None and listed_latest // 1000 > newest // 1000:
        freshness = "newer_chat_list_evidence"
    lower = bool(
        (since_ms is not None and oldest is not None and oldest < since_ms)
        or (after is not None and coverage.get("cursor_found", False))
    )
    upper = bool(
        (until_ms is not None and newest is not None and newest >= until_ms)
        or (before is not None and coverage.get("cursor_found", False))
    )
    return ReadCoverage(
        dict(
            coverage,
            result_overflow=coverage["more"],
            older_history_availability="unknown",
            observed_at=observed_at,
            newest_loaded_timestamp_ms=newest,
            chat_list_latest_timestamp_ms=listed_latest,
            freshness=freshness,
            requested_window={
                "since_ms": since_ms,
                "until_ms": until_ms,
                "before": list(before) if before else None,
                "after": list(after) if after else None,
                "lower_boundary_reached": lower,
                "upper_boundary_reached": upper,
                "returned_all_loaded_matches": not coverage["more"] and not coverage["history_gap"],
            },
        )
    ).dict()
