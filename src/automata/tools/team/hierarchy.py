"""Agent reporting hierarchy projected from manager-owned team relationships.

Managers represent teams. Their highest managed team establishes placement;
other members report to the deepest team's manager. Legacy ancestor membership
is not a second reporting link. Ambiguous same-depth managers are not guessed.
"""


def agent_parents(state):
    teams = state["teams"]
    root_manager = next(iter(state["goals"].values()))["manager_id"]

    def depth(team):
        count, seen = 0, set()
        while team["parent_id"] is not None:
            if team["id"] in seen:
                raise ValueError("team cycle")
            seen.add(team["id"])
            team = teams[team["parent_id"]]
            count += 1
        return count

    depths = {key: depth(team) for key, team in teams.items()}
    parents = {root_manager: None}
    for aid in state["agents"]:
        if aid == root_manager:
            continue
        managed = [team for team in teams.values() if team["manager_id"] == aid]
        if managed:
            level = min(depths[team["id"]] for team in managed)
            candidates = set()
            for team in managed:
                if depths[team["id"]] != level:
                    continue
                parent = teams.get(team["parent_id"])
                while parent is not None and parent["manager_id"] == aid:
                    parent = teams.get(parent["parent_id"])
                if parent is not None:
                    candidates.add(parent["manager_id"])
        else:
            memberships = [team for team in teams.values() if aid in team["agent_ids"]]
            level = max((depths[team["id"]] for team in memberships), default=-1)
            candidates = {
                team["manager_id"]
                for team in memberships
                if depths[team["id"]] == level and team["manager_id"] != aid
            }
        if len(candidates) > 1:
            raise ValueError(
                f"ambiguous reporting managers for agent {aid}; clarify team membership"
            )
        parents[aid] = next(iter(candidates), None)
    for aid in parents:
        seen, current = set(), aid
        while current is not None:
            if current in seen:
                raise ValueError("agent reporting cycle")
            seen.add(current)
            current = parents[current]
    return parents


def direct_reports(state, aid):
    parents = agent_parents(state)
    return [state["agents"][key] for key in sorted(parents) if parents[key] == aid and key != aid]


def agent_path(state, aid):
    parents = agent_parents(state)
    path = []
    while aid is not None:
        path.append(state["agents"][aid]["name"])
        aid = parents[aid]
    return " / ".join(reversed(path))
