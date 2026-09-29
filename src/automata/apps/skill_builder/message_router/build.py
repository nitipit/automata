"""Build the complete Message Router skill with Engrave and reviewed local bundles."""
import hashlib
import shutil
from pathlib import Path

import mistune
from engrave.template import get_template
from jinja2 import StrictUndefined, select_autoescape

SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parents[4]
SKILL = ROOT / "src/automata/runtimes/pi/skills/automata-message-router"
LIBRARY = ROOT / ".agents/var/apps/dashboard/public/lib"
PAGES = {
    "index": ("Overview", "Explicit routes. Private identities. Application-owned meaning."),
    "configure": ("Configure", "Decide who may start a message."),
    "connect": ("Connect", "Authenticate each client to one central router."),
    "discover": ("Discover", "Inspect your own allowed destinations."),
    "send": ("Send", "Start a message, then choose whether it needs a reply."),
    "failures": ("Handle failures", "Distinguish rejection from uncertain delivery."),
}
# Reviewed central builds. Changing these requires dependency/license review.
BUNDLES = {
    "adaptive-ui.js": "c6642917e2be4da690c8c565d91f12e065c6e10247414bae67f2ca914b3ccc9a",
    "mermaid.js": "d0830a6c05546e9edb8fe20a8f545f3e0dc7c4c3134d584bad9c13a99d7a71e0",
}
MODULES = (
    "components/reference-page.js",
    "components/code-example.js",
    "components/protocol-diagram.js",
    *(f"{page}.css.js" for page in PAGES),
)


class ReferenceRenderer(mistune.HTMLRenderer):
    """Keep Markdown code blocks keyboard-accessible in the shared UI component."""

    def block_code(self, code: str, info: str | None = None) -> str:
        rendered = super().block_code(code, info).replace("<pre>", '<pre tabindex="0">', 1)
        return f"<code-example>{rendered}</code-example>\n"

    def link(self, text: str, url: str, title: str | None = None) -> str:
        # Canonical SKILL.md links are relative to the skill, HTML lives in webref/.
        if url.startswith("webref/"):
            url = "./" + url.removeprefix("webref/")
        return super().link(text, url, title)


def skill_body(text: str) -> str:
    """Strip only leading YAML frontmatter; preserve Markdown and examples literally."""
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md requires leading YAML frontmatter")
    parts = text.split("\n---\n", 1)
    if len(parts) != 2 or not parts[1].strip():
        raise ValueError("SKILL.md requires closed frontmatter and a nonempty body")
    return parts[1].lstrip("\n")


def build(output: Path = SKILL, library_root: Path = LIBRARY) -> None:
    """Render in memory before publishing only SKILL.md and the finished webref."""
    for name, expected in BUNDLES.items():
        path = library_root / name
        if not path.is_file():
            raise ValueError(f"Missing cached bundle: {path}; no downloads are performed")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(
                f"Unreviewed cached bundle: {path}; inspect provenance before updating"
            )

    source_skill = (SOURCE / "SKILL.md").read_text(encoding="utf-8")
    template = get_template(
        dir_src=SOURCE / "site",
        markdown_to_html=mistune.create_markdown(renderer=ReferenceRenderer(escape=False)),
        autoescape=select_autoescape(["html"]),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )("page.html")
    # The markdown filter converts text without evaluating Jinja inside it.
    # Do not replace this with markdown(path), which templates Markdown first.
    rendered = {"SKILL.md": source_skill}
    for page, (title, goal) in PAGES.items():
        rendered[f"webref/{page}.html"] = template.render(
            page=page, title=title, goal=goal, pages=PAGES,
            content=(SOURCE / "content" / f"{page}.md").read_text(encoding="utf-8"),
            skill_body=skill_body(source_skill),
        )
    assets = {f"webref/{name}": SOURCE / "site" / name for name in MODULES}
    assets.update({f"webref/lib/{name}": library_root / name for name in BUNDLES})
    assets.update({f"webref/lib/{p.name}": p for p in sorted((SOURCE / "licenses").iterdir())})
    for path in assets.values():
        if not path.is_file():
            raise ValueError(f"Missing build asset: {path}")
    expected_files = set(rendered) | set(assets)
    if output.exists():
        existing = {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
        stale = existing - expected_files
        if stale:
            raise ValueError(
                f"Unexpected output files: {', '.join(sorted(stale))}; "
                "review them or build into a fresh --output directory; nothing was deleted"
            )
    for name, text in rendered.items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
    for name, path in assets.items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
