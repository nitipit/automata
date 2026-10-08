import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

test('diagrams render authored Markdown blocks without a transport dependency', () => {
  const source = readFileSync('src/automata/skills/templates/components/protocol-diagram.js', 'utf8');
  assert.match(source, /securityLevel: 'strict'/);
  assert.match(source, /htmlLabels: false/);
  assert.match(source, /querySelector\('\.diagram-source'\)\?\.textContent/);
  assert.doesNotMatch(source, /Object.freeze|dataset.diagram|WebSocket|location.search|fetch\(/);
});
