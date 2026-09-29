import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import Prism from '../../../src/automata/apps/skill_builder/templates/lib/prism.js';
import lineNumbersCSS from '../../../src/automata/apps/skill_builder/templates/components/prism-line-numbers.css.js';

const root = 'src/automata/apps/skill_builder/templates/';
const digest = path => createHash('sha256').update(readFileSync(root + path)).digest('hex');

test('pinned Prism bundle includes reviewed grammars and exact official plugin CSS', () => {
  for (const name of ['javascript', 'js', 'json', 'bash', 'sh', 'python', 'py', 'yaml', 'yml', 'markdown']) {
    assert.ok(Prism.languages[name]);
  }
  for (const literal of ['jinja', 'mermaid', 'unknown']) assert.equal(Prism.languages[literal], undefined);
  assert.equal(digest('lib/prism.js'),
    'db64933eccbb6f8edb10f1d0e0a94c1d5d4889fbc1c3705096a17dad9ffef8a2');
  assert.equal(digest('licenses/prism-LICENSE.txt'),
    '2b947f0901a7ffcf08a89957da9783c0e9c6e72cb6ce8e959f501ab5409e4d2b');
  const provenance = readFileSync(root + 'licenses/prism-PROVENANCE.txt', 'utf8');
  assert.ok(provenance.includes(createHash('sha256').update(lineNumbersCSS).digest('hex')));
});

test('Prism returns escaped markup, never evaluates snippets', () => {
  const source = 'const html = "<img src=x onerror=globalThis.__executed=true>";\n';
  const rendered = Prism.highlight(source, Prism.languages.javascript, 'javascript');
  assert.match(rendered, /token keyword/);
  assert.match(rendered, /&lt;img/);
  assert.doesNotMatch(rendered, /<img/);
  assert.equal(globalThis.__executed, undefined);
});
