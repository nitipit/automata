from automata.tools.team.store import merge, storage_key


def test_recursive_patch_does_not_mutate_old_or_patch(graph):
    task = graph["tasks"]["t"]
    patch = {"tokens": {"input": 42}, "note": "Progress"}
    result = merge(task, patch)
    assert result["tokens"]["input"] == 42
    assert result["tokens"]["output"] is None
    assert result["estimate"] == task["estimate"]
    assert result["status_changed_at"] == task["status_changed_at"]
    result["tokens"]["input"] = 99
    assert task["tokens"]["input"] is None
    assert patch["tokens"]["input"] == 42


def test_goal_keys_are_stable_unambiguous_and_goal_scoped():
    assert storage_key("g", "a") == storage_key("g", "a")
    assert storage_key("g", "a") != storage_key("other", "a")
    assert storage_key("a/b", "c") != storage_key("a", "b/c")
    assert storage_key('a"', "b") != storage_key("a", '"b')
