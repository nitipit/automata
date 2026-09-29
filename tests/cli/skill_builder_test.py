"""Skill Builder CLI and Markdown contracts; no downloads or live services."""
import subprocess
import sys
from html.parser import HTMLParser

import pytest
from engrave.template import get_template
from jinja2 import StrictUndefined, select_autoescape

from automata.apps.skill_builder.message_router.build import (
    LIBRARY,
    SOURCE,
    ReferenceRenderer,
    skill_body,
)


class CodeText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_code = False
        self.text = ""

    def handle_starttag(self, tag, attrs):
        if tag == "code":
            self.in_code = True

    def handle_endtag(self, tag):
        if tag == "code":
            self.in_code = False

    def handle_data(self, data):
        if self.in_code:
            self.text += data


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "automata.apps.skill_builder.cli", *map(str, args)],
        capture_output=True, text=True, check=False,
    )


def test_help_describes_complete_skill_and_side_effect_boundaries():
    root = cli("--help")
    assert root.returncode == 0
    assert "message-router" in root.stdout
    command = cli("message-router", "--help")
    assert command.returncode == 0
    assert "--output" in command.stdout
    assert "--library-root" in command.stdout
    assert "not webref alone" in command.stdout
    assert "no downloads" in command.stdout


def test_cli_build_copies_canonical_skill_and_renders_its_body(tmp_path):
    output = tmp_path / "skill"
    result = cli("message-router", "--output", output, "--library-root", LIBRARY)
    assert result.returncode == 0, result.stdout + result.stderr
    assert {p.name for p in output.iterdir()} == {"SKILL.md", "webref"}
    assert (output / "SKILL.md").read_bytes() == (SOURCE / "SKILL.md").read_bytes()
    overview = (output / "webref/index.html").read_text()
    assert "Agent skill instructions" in overview
    assert "Connect or reuse" in overview
    assert "metadata:" not in overview and "automata-tools:" not in overview
    assert 'href="webref/' not in overview
    assert '<a href="./connect.html">connection</a>' in overview
    assert 'href=&#34;' not in overview


def test_cli_reports_build_failure_without_traceback_or_output(tmp_path):
    result = cli("message-router", "--output", tmp_path / "out", "--library-root", tmp_path)
    assert result.returncode != 0
    assert "Missing cached bundle" in result.stdout
    assert "Traceback" not in result.stdout + result.stderr
    assert not (tmp_path / "out").exists()


def test_skill_body_strips_only_frontmatter():
    body = '# Instructions\n\n```yaml\nname: literal\n---\n```\n'
    assert skill_body('---\nname: example\ndescription: example\n---\n' + body) == body
    for text in ("no metadata", "---\nname: unclosed", "---\nname: empty\n---\n"):
        with pytest.raises(ValueError):
            skill_body(text)


def test_engrave_filter_keeps_template_syntax_and_html_literal_in_code(tmp_path):
    import mistune

    (tmp_path / "example.html").write_text("{{ content | markdown }}")
    template = get_template(
        dir_src=tmp_path,
        markdown_to_html=mistune.create_markdown(renderer=ReferenceRenderer(escape=False)),
        autoescape=select_autoescape(["html"]),
        undefined=StrictUndefined,
    )("example.html")
    code = '{{ secret }} {% dangerous %} <script>alert("x")</script> & text\n'
    rendered = template.render(content=f"```js\n{code}```\n")
    assert '<pre tabindex="0">' in rendered
    assert "<script>" not in rendered
    parser = CodeText()
    parser.feed(rendered)
    assert parser.text == code


def test_authoring_content_is_markdown_not_duplicate_html_pages():
    assert len(list((SOURCE / "content").glob("*.md"))) == 6
    assert {p.name for p in (SOURCE / "site").glob("*.html")} == {"_base.html", "page.html"}
    assert not (SOURCE / "notices").exists()
    assert (SOURCE / "licenses/PROVENANCE.txt").is_file()
