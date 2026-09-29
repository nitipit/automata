"""Direct source views and Markdown-only installation: no build output exists."""

import shutil

import pytest
from fastapi.testclient import TestClient

from automata.install.skills import install_skills
from automata.skills.content import SKILLS, SOURCE, discover, export_agent
from automata.skills.server import create_app


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def test_export_and_installer_preserve_both_identities(tmp_path):
    for slug, identity in [
        ("automata-message-router", "automata-message-router"),
        ("automata-plan", "automata-plan")
    ]:
        export_agent(slug, tmp_path / slug)
        package = SKILLS / slug
        assert snapshot(tmp_path / slug) == snapshot(package)
        assert all(p.endswith(".md") for p in snapshot(package))
        install_skills(target_root=tmp_path / "installed", skill_names=[identity])
        assert snapshot(tmp_path / "installed" / identity) == snapshot(package)
    assert len(discover(SKILLS, "automata-plan", False)) == 1
    assert len(discover(SKILLS, "automata-message-router", False)) == 6
    assert len([p for p in discover(SKILLS, None, True) if p.document == "SKILL.md"]) == 40
    export_agent("automata-adaptive-ui", tmp_path / "adaptive")
    assert snapshot(tmp_path / "adaptive") == snapshot(SKILLS / "automata-adaptive-ui")
    assert (tmp_path / "adaptive/scripts/build.py").is_file()
    assert (tmp_path / "adaptive/lib/package.json").is_file()


def test_legacy_selectors_and_navigation(tmp_path):
    for slug in ('plan', 'message-router'):
        export_agent(slug, tmp_path / slug)
        assert snapshot(tmp_path / slug) == snapshot(SKILLS / f'automata-{slug}')
    with TestClient(create_app()) as client:
        source = client.get('/message-router/').text
        assert 'href="/message-router/references/connect.html"' in source
        assert 'href="/message-router/"' in source
        assert 'href="/automata-message-router/' not in source
        assert client.get('/templates/skill.html?name=message-router').status_code == 200
        assert client.get('/templates/reference.html?name=message-router'
                          '&reference=references/connect.md').status_code == 200
    with TestClient(create_app()) as client:
        assert client.get('/templates/skill.html?name=plan').status_code == 200


def test_export_refuses_stale_files(tmp_path):
    (tmp_path / "private.txt").write_text("keep")
    with pytest.raises(ValueError, match="noncanonical"):
        export_agent("automata-message-router", tmp_path)


def test_public_routes_and_allowed_roots(tmp_path):
    root = tmp_path / "source"
    shutil.copytree(SOURCE, root)
    outside = tmp_path / "private.txt"
    outside.write_text("must not leak")
    (root / "templates/components/escape.js").symlink_to(outside)
    (root / "templates/components/base.js").symlink_to(root / "templates/base.html")
    with TestClient(create_app(root=root)) as client:
        legacy = client.get('/templates/index.html', follow_redirects=False)
        assert legacy.status_code == 307
        assert legacy.headers['location'] == '/'
        assert client.get('/templates/index.html').url.path == '/'
        for path in ["/", "/templates/skill.html?name=automata-plan",
                     "/templates/reference.html?name=automata-message-router&reference=references/connect.md",
                     "/message-router/", "/message-router/index.html", "/plan/"]:
            response = client.get(path)
            assert response.status_code == 200, path
            assert "{% extends" not in response.text
        for path in ["/server.py", "/templates/base.html", "/templates/catalog.html",
                     "/templates/components/escape.js", "/templates/components/base.js",
                     "/templates/../server.py",
                     "/%2e%2e/private.txt", "/templates/skill.html?name=../private",
                     "/templates/reference.html?name=automata-message-router&reference=../../private.txt",
                     "/skills/message-router/references/connect.md", "/docs", "/openapi.json"]:
            response = client.get(path)
            assert response.status_code == 404, (path, response.text)
            assert "must not leak" not in response.text
        assert client.get("/skills/plan/SKILL.md").content == (
            SKILLS / "automata-plan/SKILL.md"
        ).read_bytes()
        assert client.get("/automata-journal/templates/entry.html").status_code == 200
        assert client.get("/automata-agent-evaluation/references/scoring.html").status_code == 200
        assert client.get("/automata-adaptive-ui/lib/package.json").status_code == 404
        assert client.get("/plan/").status_code == 200
        assert client.get("/skills/plan/SKILL.md").status_code == 200


def test_references_never_evaluate_jinja_or_authored_html(tmp_path):
    root = tmp_path / "source"
    shutil.copytree(SOURCE, root)
    reference = root / "bundled/automata-message-router/references/connect.md"
    reference.write_text('# Connect\n\n```jinja\n{{ missing }} {% unknown %}\n```\n'
                         '\n<script>window.authored = true;</script>\n')
    with TestClient(create_app(root=root)) as client:
        rendered = client.get("/message-router/references/connect.html")
        assert rendered.status_code == 200
        assert "{{ missing }} {% unknown %}" in rendered.text
        assert "&lt;script&gt;" in rendered.text
        assert "<script>window.authored" not in rendered.text
