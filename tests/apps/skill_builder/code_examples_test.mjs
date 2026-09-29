import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const page = name => readFileSync(`src/automata/apps/skill_builder/skills/message-router/references/${name}.md`, 'utf8');

test('send teaches distinct independent, reply and one-way flows', () => {
  const source = page('send');
  assert.equal((source.match(/```mermaid\n/g) || []).length, 3);
  assert.match(source, /worker.send\("reviewer"/);
  assert.match(source, /reviewer.send\("worker"/);
  assert.match(source, /worker.respond\(message.id/);
  assert.match(source, /expectReply: false/);
  assert.match(source, /Pi adapter ignores one-way notifications/);
  assert.match(source, /before/); assert.match(source, /request.accepted/);
});
test('connect is explicit about private credentials and generic vs Pi clients', () => {
  const source = page('connect');
  assert.match(source, /createMessageRouterClient/); assert.match(source, /worker-example/);
  assert.match(source, /does not launch Pi/); assert.match(source, /NOT in a public/);
  assert.match(source, /WORKER_ENDPOINT/); assert.match(source, /built-in WebSocket/);
  assert.match(source, /Authentication:/); assert.match(source, /Authorization:/);
  assert.match(source, /application-provisioning prerequisite/);
  assert.match(source, /does not automatically fetch an endpoint record/);
});
test('configure uses one explicit directed topology', () => {
  const source = page('configure');
  for (const grant of ['desk:viewer','desk:worker','worker:reviewer','reviewer:worker']) assert.ok(source.includes('--allow '+grant));
  assert.doesNotMatch(source, /--allow worker:desk/);
  assert.match(source, /--offline/); assert.match(source, /mktemp/);
});
test('discovery shows exact caller scope and packet fields', () => {
  const source = page('discover');
  for (const field of ['"v": 2','"type": "result"','"requestId"','"destinations"','"pending": 0']) assert.ok(source.includes(field));
  assert.match(source, /sorted by ID/); assert.match(source, /not a global participant directory/);
});
test('failure examples preserve uncertainty and cancellation race', () => {
  const source = page('failures');
  for (const word of ['forbidden','offline','unknown_route','peer_disconnected','canceled','uncertain']) assert.ok(source.includes(word));
  assert.match(source, /cancel\(request.id\)/); assert.match(source, /no retraction/);
});
test('diagrams render authored Markdown blocks, not a JavaScript content registry', () => {
  const source = readFileSync('src/automata/apps/skill_builder/templates/components/protocol-diagram.js', 'utf8');
  assert.match(source, /securityLevel: 'strict'/); assert.match(source, /htmlLabels: false/);
  assert.match(source, /querySelector\('\.diagram-source'\)\?\.textContent/);
  assert.doesNotMatch(source, /Object.freeze|dataset.diagram|WebSocket|location.search|fetch\(/);
  assert.doesNotMatch(source, /participant W as worker|desk\[desk/);
  const landing = readFileSync('src/automata/apps/skill_builder/skills/message-router/SKILL.md', 'utf8');
  assert.equal((landing.match(/```mermaid\n/g) || []).length, 2);
  assert.doesNotMatch(landing, /references\/overview\.md/);
  for (const [name, count] of Object.entries({configure: 1, connect: 1, discover: 1, send: 3, failures: 2})) {
    assert.equal((page(name).match(/```mermaid\n/g) || []).length, count);
  }
});
