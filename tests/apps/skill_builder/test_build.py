"""Direct source views and Markdown-only installation: no build output exists."""

import shutil

import pytest
from fastapi.testclient import TestClient

from automata.install.skills import install_skills
from automata.skills.content import SKILLS, SOURCE, discover, export_agent, lookup
from automata.skills.server import create_app


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file() and '__pycache__' not in p.parts}


def test_export_and_installer_preserve_canonical_identities(tmp_path):
    for name in ('automata-agent-design', 'automata-workplan', 'automata-agent-evaluation'):
        export_agent(name, tmp_path / name)
        package = SKILLS / name
        assert snapshot(tmp_path / name) == snapshot(package)
        install_skills(target_root=tmp_path / 'installed', skill_names=[name])
        assert snapshot(tmp_path / 'installed' / name) == snapshot(package)
    assert len(discover(SKILLS, 'automata-workplan', False)) == 1
    assert len([p for p in discover(SKILLS, None, True) if p.document == 'SKILL.md']) == 38
    export_agent('automata-adaptive-ui', tmp_path / 'adaptive')
    assert snapshot(tmp_path / 'adaptive') == snapshot(SKILLS / 'automata-adaptive-ui')
    assert (tmp_path / 'adaptive/scripts/build.py').is_file()
    assert (tmp_path / 'adaptive/lib/package.json').is_file()


def test_reference_navigation():
    with TestClient(create_app()) as client:
        source = client.get('/automata-agent-evaluation/').text
        assert 'href="/automata-agent-evaluation/references/scoring.html"' in source
        assert client.get('/templates/skill.html?name=automata-workplan').status_code == 200
        assert client.get('/templates/reference.html?name=automata-agent-evaluation'
                          '&reference=references/scoring.md').status_code == 200


def test_workplan_canonical_identity_discovery_and_export(tmp_path):
    pages = discover(SKILLS, 'automata-workplan', False)
    assert [(page.skill, page.title, page.url) for page in pages] == [
        ('automata-workplan', 'Automata Workplan', '/automata-workplan/')
    ]
    assert lookup(pages, 'automata-workplan') == pages[0]
    export_agent('automata-workplan', tmp_path / 'export')
    assert snapshot(tmp_path / 'export') == snapshot(SKILLS / 'automata-workplan')
    for selector in ('automata-plan', 'plan', 'automata-message-router', 'message-router',
                     'automata-playspace'):
        with pytest.raises(FileNotFoundError):
            discover(SKILLS, selector, False)
        with pytest.raises(ValueError, match='Unknown skill document'):
            lookup(pages, selector)


def test_export_refuses_stale_files(tmp_path):
    (tmp_path / 'private.txt').write_text('keep')
    with pytest.raises(ValueError, match='noncanonical'):
        export_agent('automata-agent-design', tmp_path)


def test_public_routes_and_allowed_roots(tmp_path):
    root = tmp_path / 'source'
    shutil.copytree(SOURCE, root)
    outside = tmp_path / 'private.txt'
    outside.write_text('must not leak')
    (root / 'templates/components/escape.js').symlink_to(outside)
    (root / 'templates/components/base.js').symlink_to(root / 'templates/base.html')
    with TestClient(create_app(root=root)) as client:
        legacy = client.get('/templates/index.html', follow_redirects=False)
        assert legacy.status_code == 307
        assert legacy.headers['location'] == '/'
        assert client.get('/templates/index.html').url.path == '/'
        for path in ['/', '/templates/skill.html?name=automata-workplan',
                     '/templates/reference.html?name=automata-agent-evaluation&reference=references/scoring.md',
                     '/automata-agent-design/', '/automata-workplan/']:
            response = client.get(path)
            assert response.status_code == 200, path
            assert '{% extends' not in response.text
        for path in ['/server.py', '/templates/base.html', '/templates/catalog.html',
                     '/templates/components/escape.js', '/templates/components/base.js',
                     '/templates/../server.py', '/%2e%2e/private.txt',
                     '/templates/skill.html?name=../private',
                     '/templates/reference.html?name=automata-agent-evaluation&reference=../../private.txt',
                     '/docs', '/openapi.json', '/plan/', '/plan/index.html',
                     '/message-router/', '/message-router/index.html',
                     '/message-router/references/connect.html']:
            response = client.get(path)
            assert response.status_code == 404, (path, response.text)
            assert 'must not leak' not in response.text
        for retired in ('automata-message-router', 'automata-playspace', 'automata-plan',
                        'automata-thinking-control', 'automata-codex-sessions'):
            for path in (f'/{retired}/', f'/templates/skill.html?name={retired}',
                         f'/skills/{retired}/SKILL.md'):
                assert client.get(path).status_code == 404, path
        assert client.get('/skills/automata-workplan/SKILL.md').content == (
            SKILLS / 'automata-workplan/SKILL.md'
        ).read_bytes()
        assert client.get('/automata-journal/templates/entry.html').status_code == 200
        assert client.get('/automata-agent-evaluation/references/scoring.html').status_code == 200
        assert client.get('/automata-adaptive-ui/lib/package.json').status_code == 404
        assert client.get('/automata-workplan/index.html').status_code == 200


def test_references_never_evaluate_jinja_or_authored_html(tmp_path):
    root = tmp_path / 'source'
    shutil.copytree(SOURCE, root)
    reference = root / 'bundled/automata-agent-evaluation/references/scoring.md'
    reference.write_text('# Scoring\n\n```jinja\n{{ missing }} {% unknown %}\n```\n'
                         '\n<script>window.authored = true;</script>\n')
    with TestClient(create_app(root=root)) as client:
        rendered = client.get('/automata-agent-evaluation/references/scoring.html')
        assert rendered.status_code == 200
        assert '{{ missing }} {% unknown %}' in rendered.text
        assert '&lt;script&gt;' in rendered.text
        assert '<script>window.authored' not in rendered.text
