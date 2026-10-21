"""Canonical direct views in the unified server; no skill website build output."""

import shutil

import pytest
from fastapi.testclient import TestClient

from automata.install.skills import install_skills
from automata.tools.anatomy.content import SKILLS, discover, export_agent, lookup
from automata.tools.anatomy.server import TEMPLATES, create_app


def snapshot(root):
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }


def copied_source(root):
    shutil.copytree(SKILLS, root / "skills", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(TEMPLATES, root / "templates")
    return create_app(skills_root=root / "skills", templates_root=root / "templates")


def client(app):
    return TestClient(app, base_url="http://127.0.0.1:8766")


def test_export_and_installer_preserve_canonical_identities(tmp_path):
    for name in ("automata-agent-design", "automata-workplan", "automata-agent-evaluation"):
        export_agent(name, tmp_path / name)
        package = SKILLS / name
        assert snapshot(tmp_path / name) == snapshot(package)
        install_skills(target_root=tmp_path / "installed", skill_names=[name])
        assert snapshot(tmp_path / "installed" / name) == snapshot(package)
    assert len(discover(SKILLS, "automata-workplan", False)) == 1
    assert len([p for p in discover(SKILLS, None, True) if p.document == "SKILL.md"]) == len(
        list(SKILLS.rglob("SKILL.md"))
    )
    export_agent("automata-documentation", tmp_path / "documentation")
    assert snapshot(tmp_path / "documentation") == snapshot(
        SKILLS / "automata-text-writing/skills/automata-documentation"
    )


def test_reference_navigation():
    with client(create_app()) as browser:
        source = browser.get("/automata-agent-evaluation/").text
        assert 'href="/automata-agent-evaluation/references/scoring.html"' in source
        assert browser.get("/templates/skill.html?name=automata-workplan").status_code == 200
        assert (
            browser.get(
                "/templates/reference.html?name=automata-agent-evaluation"
                "&reference=references/scoring.md"
            ).status_code
            == 200
        )


def test_workplan_canonical_identity_discovery_and_export(tmp_path):
    pages = discover(SKILLS, "automata-workplan", False)
    assert [(page.skill, page.title, page.url) for page in pages] == [
        ("automata-workplan", "Automata Workplan", "/automata-workplan/")
    ]
    assert lookup(pages, "automata-workplan") == pages[0]
    export_agent("automata-workplan", tmp_path / "export")
    assert snapshot(tmp_path / "export") == snapshot(SKILLS / "automata-workplan")
    for selector in ("automata-plan", "plan", "automata-playspace"):
        with pytest.raises(FileNotFoundError):
            discover(SKILLS, selector, False)
        with pytest.raises(ValueError, match="Unknown skill document"):
            lookup(pages, selector)


def test_export_refuses_stale_files(tmp_path):
    (tmp_path / "private.txt").write_text("keep")
    with pytest.raises(ValueError, match="noncanonical"):
        export_agent("automata-agent-design", tmp_path)


def test_public_routes_and_allowed_roots(tmp_path):
    root = tmp_path / "source"
    copied_source(root)
    outside = tmp_path / "private.txt"
    outside.write_text("must not leak")
    viewer = root / "templates/skills"
    (viewer / "components/escape.js").symlink_to(outside)
    (viewer / "components/base.js").symlink_to(viewer / "base.html")
    (viewer / "components/monitor.js").symlink_to(
        root / "templates/automata/components/monitor.js"
    )
    app = create_app(skills_root=root / "skills", templates_root=root / "templates")
    with client(app) as browser:
        legacy = browser.get("/templates/index.html", follow_redirects=False)
        assert legacy.status_code == 307
        assert legacy.headers["location"] == "/skills/"
        assert browser.get("/templates/index.html").url.path == "/skills/"
        for path in [
            "/skills/",
            "/templates/skill.html?name=automata-workplan",
            "/templates/reference.html?name=automata-agent-evaluation"
            "&reference=references/scoring.md",
            "/automata-agent-design/",
            "/automata-workplan/",
        ]:
            response = browser.get(path)
            assert response.status_code == 200, path
            assert "{% extends" not in response.text
            assert 'data-section="overview"' in response.text
            assert 'data-section="skills"' in response.text
            assert response.headers["content-security-policy"].startswith("default-src 'self'")
        for path in [
            "/server.py",
            "/templates/base.html",
            "/templates/catalog.html",
            "/templates/components/escape.js",
            "/templates/components/base.js",
            "/templates/components/monitor.js",
            "/templates/../server.py",
            "/%2e%2e/private.txt",
            "/templates/skill.html?name=../private",
            "/templates/reference.html?name=automata-agent-evaluation&reference=../../private.txt",
            "/docs",
            "/openapi.json",
            "/plan/",
            "/plan/index.html",
        ]:
            response = browser.get(path)
            assert response.status_code == 404, (path, response.text)
            assert "must not leak" not in response.text
        for retired in (
            "automata-playspace",
            "automata-plan",
            "automata-thinking-control",
            "automata-codex-sessions",
            "automata-journal",
            "automata-plain-text-writing",
        ):
            for path in (
                f"/{retired}/",
                f"/templates/skill.html?name={retired}",
                f"/skills/{retired}/SKILL.md",
            ):
                assert browser.get(path).status_code == 404, path
        assert (
            browser.get("/skills/automata-workplan/SKILL.md").content
            == (SKILLS / "automata-workplan/SKILL.md").read_bytes()
        )
        assert browser.get("/automata-text-writing/").status_code == 200
        assert browser.get("/automata-documentation/").status_code == 200
        assert browser.get("/automata-journal/templates/entry.html").status_code == 404
        assert browser.get("/automata-agent-evaluation/references/scoring.html").status_code == 200
        assert browser.get("/automata-adaptive-ui/lib/package.json").status_code == 404
        assert browser.get("/automata-workplan/index.html").status_code == 200


def test_references_never_evaluate_jinja_or_authored_html(tmp_path):
    root = tmp_path / "source"
    app = copied_source(root)
    reference = root / "skills/automata-agent-evaluation/references/scoring.md"
    reference.write_text(
        "# Scoring\n\n```jinja\n{{ missing }} {% unknown %}\n```\n"
        "\n<script>window.authored = true;</script>\n"
    )
    with client(app) as browser:
        rendered = browser.get("/automata-agent-evaluation/references/scoring.html")
        assert rendered.status_code == 200
        assert "{{ missing }} {% unknown %}" in rendered.text
        assert "&lt;script&gt;" in rendered.text
        assert "<script>window.authored" not in rendered.text


def test_shared_asset_ownership_and_legacy_urls():
    with client(create_app()) as browser:
        for old, current in (
            ("/templates/lib/adaptive-ui.js", "/lib/adaptive-ui.js"),
            ("/templates/components/live-refresh.js", "/shared/components/live-refresh.js"),
        ):
            legacy = browser.get(old)
            shared = browser.get(current)
            assert legacy.status_code == shared.status_code == 200
            assert legacy.content == shared.content
        assert '/shared/components/live-refresh.js' in browser.get("/tools/").text


def test_single_watcher_is_cancelled_on_shutdown():
    app = create_app()
    with client(app):
        task = app.state.watcher
        assert not task.done()
    assert task.done() and task.cancelled()
    assert not app.state.subscribers


def test_monitor_and_catalog_use_the_same_owned_template_environment(tmp_path):
    root = tmp_path / "source"
    app = copied_source(root)
    base = root / "templates/base.html"
    base.write_text(base.read_text().replace("Local, read-only Anatomy", "COPY-OWNED-SHELL"))
    with client(app) as browser:
        for path in ("/automata/index.html", "/skills/", "/automata-workplan/"):
            response = browser.get(path)
            assert response.status_code == 200
            assert "COPY-OWNED-SHELL" in response.text
