"""Canonical exports and ordinary native CLI builds, without rendering hooks."""

import hashlib
import shutil
import subprocess

import pytest

from automata.apps.skill_builder.content import SKILLS, SOURCE, discover, export_agent
from automata.apps.skill_builder.server import BUNDLES, native_command
from automata.install.skills import install_skills


def snapshot(root):
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*") if p.is_file()
    }


def test_export_matches_package_and_disposable_install(tmp_path):
    export_agent("message-router", tmp_path / "export")
    package = SKILLS / "message-router"
    assert snapshot(tmp_path / "export") == snapshot(package)
    assert all(p.endswith(".md") for p in snapshot(package))
    install_skills(target_root=tmp_path / "installed", skill_names=["automata-message-router"])
    assert snapshot(tmp_path / "installed/automata-message-router") == snapshot(package)
    assert len(discover(SKILLS, "message-router", False)) == 6
    assert not (package / "references/overview.md").exists()


def test_export_refuses_stale_files(tmp_path):
    (tmp_path / "private.txt").write_text("keep")
    with pytest.raises(ValueError, match="noncanonical"):
        export_agent("message-router", tmp_path)
    assert (tmp_path / "private.txt").read_text() == "keep"


@pytest.mark.parametrize(
    "selector,all_skills", [(None, False), ("message-router", True), ("../secret", False)]
)
def test_selector_rejection(selector, all_skills):
    with pytest.raises(ValueError):
        discover(SKILLS, selector, all_skills)


def build(root, output):
    return subprocess.run(
        native_command("build", output, all_skills=True, root=root),
        capture_output=True, text=True, timeout=30,
    )


def test_native_build_has_only_public_outputs_and_exact_raw_landing(tmp_path):
    output = tmp_path / "output"
    result = build(SOURCE, output)
    assert result.returncode == 0, result.stdout + result.stderr
    raw = output / "skills/message-router/SKILL.md"
    assert raw.read_bytes() == (SKILLS / "message-router/SKILL.md").read_bytes()
    assert not (output / "skills/message-router/references/connect.md").exists()
    assert not (SOURCE / 'index.html').exists()
    assert not (output / 'index.html').exists()
    assert (output / 'templates/index.html').exists()
    assert sorted(p.name for p in (output / 'templates').glob('*.html')) == ['index.html']
    assert not (output / "templates/skill.html").exists()
    assert not (output / "message-router/_layout.html").exists()
    assert not (output / "server.py").exists()
    assert not (SOURCE / "engrave_adapter.py").exists()
    for name in BUNDLES:
        expected = (SOURCE / "templates/lib" / name).read_bytes()
        assert (output / "templates/lib" / name).read_bytes() == expected
    for page in discover(SKILLS, None, True):
        assert (output / page.template_name).is_file()


def test_bundle_tampering_and_missing_entry_fail_before_cli(tmp_path):
    root = tmp_path / "source"
    shutil.copytree(SOURCE, root)
    (root / "templates/lib/prism.js").write_text("unreviewed")
    with pytest.raises(ValueError, match="Unreviewed local bundle"):
        native_command("build", tmp_path / "output", all_skills=True, root=root)
    shutil.copyfile(SOURCE / "templates/lib/prism.js", root / "templates/lib/prism.js")
    (root / "message-router/references/connect.html").unlink()
    with pytest.raises(ValueError, match="Missing native entry"):
        native_command("build", tmp_path / "output", all_skills=True, root=root)


def test_native_reference_jinja_and_trusted_html_semantics_are_explicit(tmp_path):
    root = tmp_path / "source"
    shutil.copytree(SOURCE, root)
    reference = root / "skills/message-router/references/connect.md"
    reference.write_text('# Connect\n\n```jinja\n{{ missing_variable }}\n```\n'
                         + '\n<script>window.authored = true;</script>\n')
    output = tmp_path / "output"
    result = build(root, output)
    assert result.returncode == 0, result.stdout + result.stderr
    rendered = (output / "message-router/references/connect.html").read_text()
    # Characterization, NOT old literal/sanitization guarantees: native Jinja is active.
    assert "{{ missing_variable }}" not in rendered
    assert '<script>window.authored = true;</script>' in rendered
    reference.write_text('# Connect\n\n```jinja\n{% unknown_tag %}\n```\n')
    result = build(root, output)
    assert result.returncode != 0
    assert "unknown_tag" in result.stderr
