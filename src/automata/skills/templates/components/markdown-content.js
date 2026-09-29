// Enhance Mistune output; never parse Markdown or evaluate snippets.
export function enhanceMarkdown(article) {
  for (const code of article.querySelectorAll('pre > code')) {
    const pre = code.parentElement;
    if (pre.closest('code-example, protocol-diagram')) continue;
    const diagram = code.classList.contains('language-mermaid');
    const component = document.createElement(diagram ? 'protocol-diagram' : 'code-example');
    if (diagram) {
      const previous = pre.previousElementSibling;
      component.setAttribute('aria-label', previous?.textContent || 'Protocol diagram');
      pre.classList.add('diagram-source');
      pre.hidden = true;
    } else {
      pre.tabIndex = 0;
    }
    const parent = pre.parentNode;
    const next = pre.nextSibling;
    component.append(pre);
    // Connect with children already present, so component lifecycle reads native text.
    parent.insertBefore(component, next);
  }
  const source = new URL(article.dataset.source, location.origin);
  for (const anchor of article.querySelectorAll('a[href]')) {
    const target = new URL(anchor.getAttribute('href'), source);
    if (target.origin !== location.origin || !target.pathname.startsWith('/skills/')) continue;
    if (!target.pathname.endsWith('.md')) continue;
    target.pathname = target.pathname.slice('/skills'.length)
      .replace(/\/SKILL\.md$/, '/index.html').replace(/\.md$/, '.html');
    anchor.href = target.pathname + target.search + target.hash;
  }
}
