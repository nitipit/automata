"""Canonical Markdown discovery, safe page lookup, rendering, and agent export."""

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

SOURCE = Path(__file__).resolve().parent
SKILLS = SOURCE / "skills"


def body(text: str) -> str:
    """Remove leading YAML metadata without interpreting examples as templates."""
    if text.startswith("---\n"):
        parts = text.split("\n---\n", 1)
        if len(parts) != 2:
            raise ValueError("Unclosed Markdown frontmatter")
        text = parts[1]
    if not text.strip():
        raise ValueError("Empty Markdown document")
    return text.lstrip("\n")


@dataclass(frozen=True)
class Page:
    skill: str
    source: Path
    url: str
    title: str
    document: str
    description: str = ""



def markdown_links(text: str):
    """Use the Markdown parser, not a parallel page list or regex over code fences."""
    import mistune

    ast = mistune.create_markdown(renderer="ast")(body(text))

    def walk(nodes):
        for node in nodes:
            if node["type"] == "link":
                yield node["attrs"]["url"]
            yield from walk(node.get("children", []))

    return walk(ast)


def discover(skills: Path, selector: str | None, all_skills: bool) -> list[Page]:
    if bool(selector) == all_skills:
        raise ValueError("Choose exactly one skill name or --all")
    if selector and not re.fullmatch(r"[a-z0-9][a-z0-9-]*", selector):
        raise ValueError("Invalid skill name")
    roots = sorted(skills.iterdir()) if all_skills else [skills / selector]
    pages = []
    for root in roots:
        if all_skills and not (root / "SKILL.md").is_file():
            continue
        if not root.resolve().is_relative_to(skills.resolve()):
            raise ValueError("Skill directory escapes app skills root")
        pending, visited = [root / "SKILL.md"], set()
        while pending:
            source = pending.pop(0).resolve()
            if source in visited:
                continue
            if not source.is_relative_to(root.resolve()) or source.suffix != ".md":
                raise ValueError("Markdown reference escapes its skill")
            relative = source.relative_to(root.resolve())
            if relative != Path("SKILL.md") and relative.parts[0] != "references":
                raise ValueError("References must live in references/")
            text = source.read_text(encoding="utf-8")
            stripped = body(text)
            import mistune

            ast = mistune.create_markdown(renderer="ast")(stripped)
            heading = next(
                (node for node in ast if node["type"] == "heading" and node["attrs"]["level"] == 1),
                None,
            )
            title = (
                "".join(child.get("raw", "") for child in heading["children"])
                if heading
                else source.stem.replace("-", " ").title()
            )
            url = (
                f"/{root.name}/"
                if relative == Path("SKILL.md")
                else f"/{root.name}/{relative.with_suffix('.html').as_posix()}"
            )
            paragraph = next((node for node in ast if node['type'] == 'paragraph'), None)

            def plain_text(nodes):
                return ''.join(plain_text(node['children']) if 'children' in node
                               else node.get('raw', ' ') for node in nodes)

            description = ' '.join(plain_text(paragraph['children']).split()) if paragraph else ''
            pages.append(Page(root.name, source, url, title, relative.as_posix(), description))
            visited.add(source)
            for link in markdown_links(text):
                parsed = urlsplit(link)
                if not parsed.scheme and not parsed.netloc and parsed.path.endswith(".md"):
                    pending.append(source.parent / unquote(parsed.path))
    if not pages:
        raise ValueError("No skills found")
    return pages


def lookup(pages: list[Page], skill: str, document: str = "SKILL.md") -> Page:
    """Accept only a document reached through canonical discovery, never a file path."""
    for page in pages:
        if page.skill == skill and page.document == document:
            return page
    raise ValueError("Unknown skill document")


def render_markdown(page: Page) -> str:
    """Render references as Markdown only: no Jinja evaluation or authored raw HTML."""
    import mistune

    class Renderer(mistune.HTMLRenderer):
        def link(self, text, url, title=None):
            parsed = urlsplit(url)
            if not parsed.scheme and not parsed.netloc and parsed.path.endswith(".md"):
                target = urlsplit(urljoin(f"/skills/{page.skill}/{page.document}", url))
                path = target.path.removeprefix("/skills")
                path = (path.removesuffix("SKILL.md") if path.endswith("/SKILL.md")
                        else path[:-3] + ".html")
                url = target._replace(path=path).geturl()
            return super().link(text, url, title)

    return mistune.create_markdown(renderer=Renderer(escape=True))(
        page.source.read_text(encoding="utf-8")
    )


def export_agent(selector: str, output: Path, skills: Path = SKILLS) -> None:
    """Copy only canonical Markdown, never browser assets or private state."""
    pages = discover(skills, selector, False)
    root = (skills / selector).resolve()
    files = {p.source.relative_to(root): p.source for p in pages}
    if output.exists():
        existing = {p.relative_to(output) for p in output.rglob("*") if p.is_file()}
        if existing - files.keys():
            raise ValueError("Output contains noncanonical files; choose a fresh directory")
    for relative, source in files.items():
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
