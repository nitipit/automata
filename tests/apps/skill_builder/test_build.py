"""Finished-artifact contracts; no network and no installed-skill synchronization."""
import hashlib
from pathlib import Path

import pytest

from automata.apps.skill_builder.message_router.build import BUNDLES, PAGES, ROOT, SKILL, build
from automata.install.skills import install_skills

LIBRARY = ROOT / ".agents/var/apps/dashboard/public/lib"


def snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*") if path.is_file()
    }


def test_cached_build_is_reproducible_and_matches_shipped_artifact(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    build(first, LIBRARY)
    build(second, LIBRARY)
    assert snapshot(first) == snapshot(second) == snapshot(SKILL)
    assert {path.stem for path in (first / "webref").glob("*.html")} == set(PAGES)
    for name, digest in BUNDLES.items():
        assert snapshot(first)[f"webref/lib/{name}"] == digest


def test_missing_or_changed_cache_fails_before_writing(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="Missing cached bundle"):
        build(output, cache)
    assert not output.exists()
    (cache / "adaptive-ui.js").write_text("unreviewed")
    with pytest.raises(ValueError, match="Unreviewed cached bundle"):
        build(output, cache)
    assert not output.exists()


def test_stale_assets_require_review_not_automatic_deletion(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    stale = output / "retired.js"
    stale.write_text("preserve me")
    with pytest.raises(ValueError, match="Unexpected output files"):
        build(output, LIBRARY)
    assert stale.read_text() == "preserve me"
    assert not (output / "SKILL.md").exists()
    assert not (output / "webref/index.html").exists()


def test_disposable_skill_install_contains_only_finished_reference(tmp_path):
    destination = tmp_path / "installed-skills"
    install_skills(target_root=destination, skill_names=["automata-message-router"])
    installed = destination / "automata-message-router"
    assert {path.name for path in installed.iterdir()} == {"SKILL.md", "webref"}
    assert snapshot(installed) == snapshot(SKILL)
    assert not list(installed.rglob("*.py"))
    assert not list(installed.rglob("*.ts"))
    assert not list(installed.rglob("*.map"))
    assert not list(installed.rglob("*echarts*"))
    for page in (installed / "webref").glob("*.html"):
        text = page.read_text()
        assert "{%" not in text and "{{" not in text
        assert 'src="/' not in text and 'href="/' not in text
    for module in (installed / "webref").glob("**/*.js"):
        if module.parent.name == "lib":
            continue
        text = module.read_text()
        assert "from '/" not in text and "import '/" not in text
        assert "anatomy-theme" not in text
        assert "WebSocket" not in text and "fetch(" not in text
