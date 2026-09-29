import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import hljs from '../../../src/automata/apps/skill_builder/templates/lib/highlight.js';

const root = 'src/automata/apps/skill_builder/templates/';
const digest = path => createHash('sha256').update(readFileSync(root + path)).digest('hex');

test('pinned Highlight.js bundle contains only the reviewed grammar subset', () => {
  assert.equal(hljs.versionString, '11.11.1');
  assert.deepEqual(hljs.listLanguages().sort(), ['bash', 'javascript', 'json', 'python', 'yaml']);
  for (const alias of ['js', 'sh', 'py', 'yml']) assert.ok(hljs.getLanguage(alias));
  for (const literal of ['html', 'jinja', 'mermaid', 'plaintext', 'unknown']) {
    assert.equal(hljs.getLanguage(literal), undefined);
  }
  assert.equal(digest('lib/highlight.js'),
    '6cc987718bc54f43b77072a60595d88b8aa3a915edf8c5d2cb59bdb3994e98ba');
  assert.equal(digest('licenses/highlightjs-LICENSE.txt'),
    '6c081431591d9df696c82dc598fe1423765b8a299b200ed00b281afd0f64c490');
});

test('highlight returns escaped markup, never evaluates snippets', () => {
  const source = 'const html = "<img src=x onerror=globalThis.__executed=true>";\n';
  const rendered = hljs.highlight(source, {language: 'javascript'}).value;
  assert.match(rendered, /hljs-keyword/);
  assert.match(rendered, /&lt;img/);
  assert.doesNotMatch(rendered, /<img/);
  assert.equal(globalThis.__executed, undefined);
});
