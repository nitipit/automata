"""Flat document/identity contract, legacy compatibility and read-only boundaries."""

import pytest
from fastapi.testclient import TestClient

from automata.tools.anatomy import catalog, data, server
from automata.tools.anatomy.content import SKILLS


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        data,
        "tools",
        lambda: [
            {
                "name": "collision",
                "kind": "Tool package",
                "copies": [{"scope": "bundled", "source": "automata/tools/collision"}],
            },
            {
                "name": "collision",
                "kind": "Pi extension",
                "copies": [{"scope": "global", "source": "~/.pi/agent/extensions/collision.ts"}],
            },
        ],
    )
    monkeypatch.setattr(
        data,
        "skills",
        lambda: (
            [
                {
                    "name": "automata-workplan",
                    "description": "Fixture",
                    "copies": [{"scope": "global", "source": "skills/automata-workplan/SKILL.md"}],
                    "toolPaths": [".agents/tools/collision/main.py"],
                }
            ],
            [],
        ),
    )
    return TestClient(server.create_app(), base_url="http://127.0.0.1:8766")


@pytest.mark.parametrize(
    "path,section",
    [
        ("/", "overview"),
        ("/skills/", "skills"),
        ("/tools/", "tools"),
        ("/activity/", "activity"),
        ("/skills/automata-workplan/", "skills"),
        ("/tools/package--collision/", "tools"),
        ("/tools/extension--collision/", "tools"),
        ("/automata-agent-evaluation/references/scoring.html", "skills"),
    ],
)
def test_direct_navigation_and_active_section(client, path, section):
    response = client.get(path)
    assert response.status_code == 200
    nav = response.text.split('<nav aria-label="Anatomy">')[1].split("</nav>")[0]
    assert nav.count('aria-current="page"') == 1
    assert f'data-section="{section}"' in nav.split('aria-current="page"')[0].split("<a")[-1]
    for label in ("Overview", "Skills", "Tools", "Activity"):
        assert f">{label}</a>" in nav
    assert 'role="tablist"' not in response.text
    assert "<aside" not in response.text
    assert client.post(path, json={}).status_code == 405


def test_skill_flat_and_legacy_source_contract(client):
    for old in (
        "/automata-workplan/",
        "/automata-workplan/index.html",
        "/templates/skill.html?name=automata-workplan",
    ):
        response = client.get(old, follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/skills/automata-workplan/"
    response = client.get("/skills/automata-workplan/")
    assert 'aria-label="Breadcrumb"' in response.text
    assert 'href="/skills/automata-workplan/SKILL.md"' in response.text
    assert "Installation sources and declared tools" in response.text
    assert "Runtime readiness: not checked" in response.text
    assert (
        client.get("/skills/automata-workplan/SKILL.md").content
        == (SKILLS / "automata-workplan/SKILL.md").read_bytes()
    )


def test_tool_collision_stays_distinct_and_has_provenance(client):
    listing = client.get("/tools/").text
    assert "/tools/package--collision/" in listing
    assert "/tools/extension--collision/" in listing
    package = client.get("/tools/package--collision/").text
    extension = client.get("/tools/extension--collision/").text
    assert 'aria-label="Breadcrumb"' in package
    assert "automata/tools/collision" in package
    assert "Tool package · Available to install" in package
    assert "Pi extension · Installed" in extension
    assert 'href="/skills/automata-workplan/"' in package
    assert "No explicit skill relationship" in extension
    assert "Runtime readiness: not checked" in package


@pytest.mark.parametrize(
    "path",
    [
        "/tools/not-found/",
        "/tools/collision/",
        "/skills/not-found/",
        "/skills/automata-workplan/private.md",
        "/skills/automata-workplan/references/private.html",
        "/tools/package--collision/main.py",
        "/activity/private",
        "/tools/index.html",
        "/templates/tools/detail.html",
    ],
)
def test_unknown_documents_and_no_generic_file_mount(client, path):
    assert client.get(path).status_code == 404


def test_installed_only_evidence_does_not_publish_private_source(client, monkeypatch):
    monkeypatch.setattr(
        catalog,
        "installed_skills",
        lambda: (
            [
                {
                    "name": "custom-local-skill",
                    "description": "Local purpose",
                    "copies": [
                        {"scope": "project", "source": ".agents/skills/custom-local-skill/SKILL.md"}
                    ],
                    "toolPaths": [],
                }
            ],
            [],
        ),
    )
    response = client.get("/skills/")
    assert 'data-name="custom-local-skill" data-setup="installed"' in response.text
    assert "Local purpose" in response.text
    assert "source is not published by this viewer" in response.text
    assert client.get("/skills/custom-local-skill/").status_code == 404
    assert client.get("/skills/custom-local-skill/SKILL.md").status_code == 404


@pytest.mark.parametrize("path", ["skills", "tools", "activity"])
def test_catalog_slash_aliases(client, path):
    response = client.get("/" + path, follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/" + path + "/"


def test_overview_activity_have_separate_content(client):
    overview = client.get("/").text
    activity = client.get("/activity/").text
    assert 'id="identity-body"' in overview and 'id="range"' not in overview
    assert 'id="range"' in activity and 'id="identity-body"' not in activity
    for path in ("/skills/", "/skills/automata-workplan/", "/tools/", "/tools/package--collision/"):
        assert "/automata/components/monitor.js" not in client.get(path).text
