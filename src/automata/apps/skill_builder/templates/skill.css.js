import { ReferencePage } from './components/reference-page.js';
import './components/protocol-diagram.js';
import './components/code-example.js';
import './components/raw-skill.js';
import { enhanceMarkdown } from './components/markdown-content.js';

class SkillPage extends ReferencePage {
  static {
    this.css = `
      article.lesson { max-width: 80ch; margin: 2rem auto; }
      article h2 { margin-top: 2rem; }
      article h3 { margin-top: 1.5rem; }
      article :not(pre) > code {
        background: var(--webref-accent-soft);
        padding: .1em .3em;
        border-radius: .25em;
        font-size: .9em;
      }
      table { display: block; overflow: auto; border-collapse: collapse; }
      th, td { border: 1px solid var(--aui-border); padding: .5rem; }
      blockquote { border-left: 3px solid var(--aui-border); margin-left: 0; padding-left: 1rem; }
    `;
  }

  connectedCallback() {
    super.connectedCallback();
    enhanceMarkdown(this.querySelector('article'));
  }
}
SkillPage.define('skill-page');
