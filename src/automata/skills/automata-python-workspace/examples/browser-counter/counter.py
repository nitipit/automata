"""Example-owned Python object/schema/publication adapter. No reusable runtime here."""

from runtime_import import PUBLICATION_MIME

BOOTSTRAP = f"""
from dataclasses import dataclass
from IPython.display import display
@dataclass
class Counter:
    value: int = 0
counter = Counter()
def publish_state():
    if type(counter.value) is not int or abs(counter.value) > 10**12:
        raise ValueError("counter.value must be an integer within ±10^12")
    display({{{PUBLICATION_MIME!r}: {{
        "count": counter.value, "object_id": str(id(counter))}}}}, raw=True)
publish_state()
"""


def counter_state(publication):
    if (
        isinstance(publication, dict)
        and type(publication.get("count")) is int
        and abs(publication["count"]) <= 10**12
        and isinstance(publication.get("object_id"), str)
        and len(publication["object_id"]) <= 32
    ):
        return {"count": publication["count"], "object_id": publication["object_id"]}
    return None


def counter_event(event):
    result = dict(event)
    if event["kind"] == "publication":
        result["kind"] = "state"
        result["state"] = counter_state(event.get("publication"))
    elif event["kind"] == "publication_error":
        result["kind"] = "projection_error"
    return result


def counter_snapshot(runtime):
    view = runtime.view()
    return {
        **view,
        "state": counter_state(view["publication"]),
        "events": [counter_event(event) for event in view["events"]],
    }
