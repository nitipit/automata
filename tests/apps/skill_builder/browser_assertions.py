"""Focused browser contracts for the shared reading column and code component."""

from playwright.sync_api import expect

CODE_SAMPLES = {
    "javascript": 'const html = "<img src=x onerror=window.__snippetExecuted=true>";\n'
    '// Preserve literal HTML and whitespace\n\tconsole.log(html);\n',
    "js": "const alias = true;\n",
    "json": '{"answer": true, "count": 42}\n',
    "bash": '# Preserve tabs and trailing spaces\nprintf "%s\\n" "$HOME"  \n',
    "sh": 'echo "$HOME"\n',
    "python": 'def greet(name):\n\treturn "Hello " + name\n',
    "py": "answer = True\n",
    "yaml": "enabled: true\nitems:\n  - value\n",
    "yml": "answer: 42\n",
    "plaintext": '<script>window.__snippetExecuted=true</script>\n',
    "html": '<img src=x onerror="window.__snippetExecuted=true">\n',
    "jinja": "Unsupported grammar remains plain text.\n",
    "unknown-language": "<b>literal & unchanged</b>\n",
}
LITERAL_LANGUAGES = {"plaintext", "html", "jinja", "unknown-language"}
FIXTURE_MARKDOWN = (
    "\n\n## Synthetic code fixtures\n\nInline `const plain = true;` stays literal.\n\n"
)
FIXTURE_MARKDOWN += "\n".join(
    f"```{language}\n{source}```\n" for language, source in CODE_SAMPLES.items()
)
FIXTURE_MARKDOWN += "\n```\nNo language: <b>literal</b>\n```\n"


def assert_centered(page):
    rect = page.locator("article.lesson").evaluate(
        """el => {
          const rect = el.getBoundingClientRect();
          const style = getComputedStyle(el);
          return {left: rect.left, right: rect.right, width: rect.width,
                  viewport: innerWidth, align: style.textAlign};
        }"""
    )
    assert abs((rect["left"] + rect["right"]) / 2 - rect["viewport"] / 2) < 1, rect
    assert rect["width"] <= 900, rect
    assert rect["align"] in {"start", "left"}, rect
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")


def assert_highlighting(page):
    for language, raw in CODE_SAMPLES.items():
        code = page.locator(f"code-example code.language-{language}").last
        if language in LITERAL_LANGUAGES:
            expect(code.locator("span")).to_have_count(0)
        else:
            expect(code.locator("span").first).to_be_attached()
        assert code.text_content() == raw
        selection = code.evaluate(
            """el => {
              const select = node => {
                const range = document.createRange(); range.selectNodeContents(node);
                const selection = getSelection(); selection.removeAllRanges();
                selection.addRange(range);
                const text = selection.toString(); selection.removeAllRanges(); return text;
              };
              const highlighted = select(el);
              const plain = el.cloneNode(false); plain.textContent = el.textContent;
              el.parentNode.append(plain);
              const literal = select(plain); plain.remove();
              return {highlighted, literal};
            }"""
        )
        # Chrome omits the final non-rendered newline for ordinary pre selections too.
        # Highlighting must not change native selection/copy semantics at all.
        assert selection["highlighted"] == selection["literal"], (language, selection)
        assert selection["highlighted"] == raw.removesuffix("\n"), (language, selection)
    assert page.locator("article p > code span").count() == 0
    unlabelled = page.locator("code-example code:not([class])").last
    assert unlabelled.text_content() == "No language: <b>literal</b>\n"
    assert unlabelled.locator("span").count() == 0
    assert page.locator("code-example img, code-example script").count() == 0
    assert page.evaluate("window.__snippetExecuted === undefined")
    code = page.locator("code-example code.language-javascript").last
    before = code.inner_html()
    code.locator("..").locator("..").evaluate(
        "el => { const parent = el.parentNode; el.remove(); parent.append(el); }"
    )
    expect(code).to_have_text(CODE_SAMPLES["javascript"], use_inner_text=False)
    page.wait_for_timeout(50)
    assert code.inner_html() == before
    # No copy button exists: native keyboard selection is the copy contract.
    assert page.locator("code-example button").count() == 0


def assert_token_contrast(page):
    ratios = page.locator("code-example span[class^='hljs-']").evaluate_all(
        """elements => {
          const luminance = color => {
            const channels = color.match(/[\\d.]+/g).slice(0, 3).map(Number)
              .map(c => c / 255).map(c => c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4);
            return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722;
          };
          return elements.map(el => {
            const foreground = luminance(getComputedStyle(el).color);
            const background = luminance(getComputedStyle(el.closest('pre')).backgroundColor);
            return (Math.max(foreground, background) + .05) /
              (Math.min(foreground, background) + .05);
          });
        }"""
    )
    assert ratios and min(ratios) >= 4.5, ratios
