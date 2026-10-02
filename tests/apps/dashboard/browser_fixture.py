"""Synthetic monitor data: browser acceptance never reads live recorder/identity."""
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo


def snapshot(url):
    query = parse_qs(urlparse(url).query)
    zone = query.get("timezone", ["UTC"])[0]
    skill = query.get("skill", [""])[0]
    start = "2026-09-21T00:00:00+00:00"
    end = "2026-09-28T00:00:00+00:00"
    if query.get('range') == ['custom'] and query.get('start') and query.get('end'):
        start = datetime.fromisoformat(query['start'][0]).replace(tzinfo=ZoneInfo(zone)).isoformat()
        end = (datetime.fromisoformat(query['end'][0]).replace(tzinfo=ZoneInfo(zone))
               + timedelta(days=1)).isoformat()
    items = [{"name": "automata-message-router", "description": "Illustrative router capability",
              "status": "installed", "skillInstalled": True, "readiness": "Not checked",
              "copies": [], "tools": []}]
    rows = [{"name": skill or "automata-message-router", "count": 4, "latest": start}]
    return {
        "project": "Synthetic acceptance fixture", "scope": "No live data", "warnings": [],
        "identity": {"source": "fixture/AGENTS.md", "modified": start,
                     "body": "# Synthetic identity\nNo live instructions read.", "note": "Fixture"},
        "capabilities": {"items": items, "otherTools": [], "note": "Fixture"},
        "activity": {"status": "ready", "window": {"start": start, "end": end, "timezone": zone},
                     "rows": rows, "timeline": [{"start": start, "count": 4}],
                     "bucket": "hour" if query.get("range") == ["24h"] else "day",
                     "skillOptions": ["automata-message-router"], "total": 4, "distinct": 1,
                     "last24h": 2, "availableFirst": start, "availableLatest": end,
                     "coverageNote": "Fixture only", "note": "Synthetic load counts", "invalid": 0},
    }
