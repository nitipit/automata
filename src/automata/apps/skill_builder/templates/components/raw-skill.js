import { Base } from '../lib/adaptive-ui.js';

// Native Engrave copies this public canonical asset unchanged. No Markdown/Jinja
// parsing here: the landing is an exact source view, including its final newline.
class RawSkill extends Base {
  static { this.css = 'display: block; min-width: 0;'; }
  #request;

  connectedCallback() {
    super.connectedCallback();
    this.#request?.abort();
    const request = this.#request = new AbortController();
    const status = this.querySelector('[role=status]');
    const code = this.querySelector('code');
    status.hidden = false;
    status.textContent = 'Loading skill source…';
    code.textContent = '';
    const path = this.getAttribute('src');
    if (!/^\/skills\/[a-z0-9-]+\/SKILL\.md$/.test(path || '')) {
      status.textContent = 'Skill source unavailable: invalid public asset path.';
      return;
    }
    fetch(path, { signal: request.signal, credentials: 'same-origin' })
      .then(response => {
        if (!response.ok) throw new Error('Source unavailable');
        return response.text();
      })
      .then(text => {
        if (request.signal.aborted) return;
        code.textContent = text;
        code.closest('code-example').highlight();
        status.hidden = true;
      })
      .catch(error => {
        if (error.name !== 'AbortError') status.textContent = 'Skill source unavailable. Reload to retry.';
      });
  }

  disconnectedCallback() {
    this.#request?.abort();
    super.disconnectedCallback?.();
  }
}
RawSkill.define('raw-skill');
