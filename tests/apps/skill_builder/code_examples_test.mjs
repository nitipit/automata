import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const page = name => readFileSync(`src/automata/apps/skill_builder/message_router/content/${name}.md`, 'utf8');

test('send teaches distinct independent, reply and one-way flows', () => {
  const source = page('send');
  assert.equal((source.match(/<protocol-diagram /g) || []).length, 3);
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
test('diagrams consume a fixed authored registry, never supplied text', () => {
  const source = readFileSync('src/automata/apps/skill_builder/message_router/site/components/protocol-diagram.js', 'utf8');
  assert.match(source, /securityLevel:'strict'/); assert.match(source, /htmlLabels:false/);
  assert.match(source, /diagrams\[this.dataset.diagram\]/);
  assert.doesNotMatch(source, /WebSocket|location.search|fetch\(/);
});
