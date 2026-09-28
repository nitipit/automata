"""Explicit public routes and existing snapshot validation; never read live data."""
import pytest
from fastapi.testclient import TestClient

from automata.apps.dashboard import server
from automata.apps.dashboard.routes import automata


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        automata, "snapshot", lambda window: {"activity": {"window": window.public()}}
    )
    return TestClient(server.app, base_url="http://127.0.0.1:8766")


def test_api_compatibility_and_headers(client):
    response = client.get("/api/anatomy?range=7d&timezone=UTC")
    assert response.status_code == 200
    assert response.json()["activity"]["window"]["timezone"] == "UTC"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "connect-src 'self'" in response.headers["content-security-policy"]
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("query", [
    "timezone=invalid", "range=bad", "range=custom&start=bad&end=2026-01-01",
    "range=custom&start=2026-02-02&end=2026-02-01",
    "range=custom&start=2999-01-01&end=2999-01-02",
])
def test_readable_validation(client, query):
    response = client.get("/api/anatomy?" + query)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


@pytest.mark.parametrize("headers", [
    {"host": "localhost:8766"}, {"host": "attacker.example"},
    {"origin": "http://attacker.example"}, {"origin": "null"},
])
def test_foreign_access_rejected(client, headers):
    assert client.get("/api/anatomy", headers=headers).status_code == 403


@pytest.mark.parametrize("path", [
    "/.agents/var/private.json", "/src/automata/apps/workspace/README.md",
    "/api/state", "/api/conversations", "/server.py", "/lib/../private.json",
    "/%2e%2e/%2e%2e/private.json", "/docs", "/openapi.json",
    "/workspace-view.js", "/workspace", "/api/router", "/lib/mermaid/package.json",
])
def test_no_private_or_generic_file_routes(client, path):
    assert client.get(path).status_code == 404


def test_only_allowlisted_assets_are_served(client):
    for name in server.PUBLIC_ASSETS:
        response = client.get('/' + name + '?name=private.json')
        assert response.status_code == 200, name
        assert response.headers['content-type'].startswith('text/javascript')
        assert "frame-ancestors 'none'" in response.headers['content-security-policy']
    assert client.post('/automata/components/monitor.js', json={}).status_code == 405


@pytest.mark.parametrize('path', [
    '/base.html', '/message-router/base.html', '/templates/base.html',
    '/templates/automata/index.html', '/message-router/send.html.bak',
    '/message-router/components/private.json', '/automata/components/monitor.js.map',
    '/lib/mermaid.js.map', '/lib/chunks/private.js', '/theme.js', '/app.js',
    '/router-view.js', '/routes.js', '/layout.css', '/themes.css',
])
def test_template_sources_and_retired_spa_are_private(client, path):
    assert client.get(path).status_code == 404


@pytest.mark.parametrize('path,title', [
    ('/automata/index.html', 'Automata'),
    ('/message-router/configure.html', 'Configure'),
    ('/message-router/connect.html', 'Connect'),
    ('/message-router/discover.html', 'Discover'),
    ('/message-router/send.html', 'Send'),
    ('/message-router/failures.html', 'Handle failures'),
])
def test_rendered_documents_not_template_sources(client, path, title):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/html')
    assert title + ' · Anatomy' in response.text
    assert '{%' not in response.text and '{{' not in response.text
    assert 'script-src' in response.headers['content-security-policy']
    assert 'unsafe-eval' not in response.headers['content-security-policy']
    assert 'type="module"' in response.text
    if 'message-router' in path:
        assert 'components/monitor.js' not in response.text
        assert 'id="auto"' not in response.text


def test_document_aliases(client):
    for source, target in [('/', '/automata/index.html'), ('/automata/', '/automata/index.html'),
                           ('/message-router/', '/message-router/configure.html')]:
        response = client.get(source, follow_redirects=False)
        assert response.status_code == 302
        assert response.headers['location'] == target


def test_snapshot_failure_is_bounded(client, monkeypatch):
    def fail(_):
        raise RuntimeError("private detail")
    monkeypatch.setattr(automata, "snapshot", fail)
    response = client.get("/api/anatomy")
    assert response.status_code == 503
    assert "private detail" not in response.text
