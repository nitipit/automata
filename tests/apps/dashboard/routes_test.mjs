import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { parseMonitorState, serializeMonitorState } from '../../../src/automata/apps/dashboard/templates/automata/components/monitor-state.js';

test('closed monitor URL defaults and invalid values', () => {
  const state = parseMonitorState('?tab=unsafe&range=invalid&timezone=Invalid&limit=500&setup=invalid&paused=wat', 'UTC');
  assert.equal(state.tab, 'identity'); assert.equal(state.range, '7d');
  assert.equal(state.timezone, 'UTC'); assert.equal(state.limit, '10');
  assert.equal(state.setup, 'all'); assert.equal(state.paused, false);
});
test('all useful state roundtrips including paused custom dates', () => {
  const query = '?tab=statistics&query=router&setup=installed&selected=automata-message-router&range=custom&timezone=America%2FNew_York&skill=automata-message-router&limit=all&paused=1&start=2026-03-07&end=2026-03-09';
  const state = parseMonitorState(query);
  assert.deepEqual(parseMonitorState(serializeMonitorState(state)), state);
  assert.equal(state.paused, true); assert.equal(state.start, '2026-03-07');
});
test('invalid dates and unbounded text cannot enter restored state', () => {
  assert.equal(parseMonitorState('?range=custom&start=2026-02-30&end=2026-03-05').range, '7d');
  assert.equal(parseMonitorState('?range=custom&start=2026-03-05&end=2026-03-01').range, '7d');
  assert.equal(parseMonitorState('?query='+'a'.repeat(257)).query, '');
  assert.equal(parseMonitorState('?skill=%00secret').skill, '');
});
test('document lifecycle aborts requests and clears timers', () => {
  const source = readFileSync('src/automata/apps/dashboard/templates/automata/components/monitor.js', 'utf8');
  assert.match(source, /pagehide/); assert.match(source, /clearInterval\(polling\)/);
  assert.match(source, /lifetime\.abort\(\)/); assert.match(source, /if \(disposed\) return/);
  assert.match(source, /\$\('auto'\)\.checked = !restored.paused/);
});
test('no SPA routing in document navigation', () => {
  const source = readFileSync('src/automata/apps/dashboard/templates/shared/components/anatomy-nav.js', 'utf8');
  assert.doesNotMatch(source, /hashchange|preventDefault|fetch\(/);
  assert.match(source, /\/automata\/index.html\?/);
});
