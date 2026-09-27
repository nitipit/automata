import { Base, Button, Card, html, reactive } from '/lib/adaptive-ui.js';
import { SkillLoadsChart, SkillTimelineChart, loadChartLibrary } from '/chart.js';
import { initializeTheme, setTheme, getTheme } from '/theme.js';

const $ = id => document.getElementById(id);
const el = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = String(text);
  if (className) node.className = className;
  return node;
};
const setupNames = { installed: 'Installed', available: 'Available to install', incomplete: 'Incomplete setup', unknown: 'Unknown setup' };
const state = reactive({ tab: 'identity', query: '', setup: 'all', selected: '', range: '7d', timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Bangkok', skill: '', limit: '10', phase: 'loading', error: '', count: 0, total: 0 });
const when = (value, timezone = data?.activity?.window?.timezone || state.timezone) => value ? new Intl.DateTimeFormat(undefined, { timeZone: timezone, dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : 'No recorded event';

class AnatomyTable extends Base {
  static { this.css = `display:block; overflow-x:auto; color:var(--anatomy-text);
    table { width:100%; border-collapse:collapse; font-size:14px; }
    th,td { text-align:left; vertical-align:top; padding:10px 8px; border-bottom:1px solid var(--anatomy-border); }
    th { color:var(--anatomy-muted); font-weight:600; }
    td:first-child { min-width:130px; } code { overflow-wrap:anywhere; font-size:12px; }
    small { display:block; color:var(--anatomy-muted); }
  `; }
  static validateData(value) {
    if (!Array.isArray(value.headers) || !Array.isArray(value.rows)) throw new Error('Invalid table data');
    return value;
  }
  applyData(value) {
    const { headers, rows } = AnatomyTable.validateData(value);
    const table = el('table'); const head = el('thead'); const header = el('tr');
    for (const title of headers) { const cell = el('th', title); cell.scope = 'col'; header.append(cell); }
    head.append(header); table.append(head);
    const body = el('tbody');
    for (const values of rows) {
      const row = el('tr');
      for (const value of values) { const cell = el('td'); cell.append(value instanceof Node ? value : document.createTextNode(String(value))); row.append(cell); }
      body.append(row);
    }
    if (!rows.length) { const row = el('tr'); const cell = el('td', 'No matching records.'); cell.colSpan = headers.length; row.append(cell); body.append(row); }
    table.append(body); this.replaceChildren(table);
  }
}
Card.addStyle('grid-template-columns: minmax(0, 1fr); > * { min-width: 0; }');
Card.define('aui-card'); Button.define('aui-button'); AnatomyTable.define('anatomy-table');
const tables = {};
for (const id of ['capabilities-table', 'other-tools-table', 'activity-table']) {
  tables[id] = AnatomyTable.create({ data: { headers: [], rows: [] } }); $(id).append(tables[id]);
}
const ranking = SkillLoadsChart.create({ data: { rows: [], timeline: [], available: false, timezone: state.timezone } });
const timeline = SkillTimelineChart.create({ data: { rows: [], timeline: [], available: false, timezone: state.timezone } });
$('activity-chart').append(ranking); $('timeline-chart').append(timeline);
html`<span>${() => state.count} of ${() => state.total} capabilities · copies grouped by skill name</span>`($('capability-count'));
let data = null; let busy = false; let queued = false; let lastSuccess = null; let libraryReady = false;
let capabilityFingerprint = null;

function sourceDetails(copies) {
  const list = el('ul');
  for (const copy of copies || []) {
    const item = el('li'); item.append(el('strong', `${copy.scope}: `), el('code', copy.source));
    if (copy.modified) item.append(el('small', `Modified ${when(copy.modified)}`));
    list.append(item);
  }
  return list;
}
function capabilityDetail(row) {
  const panel = $('capability-detail');
  if (!row) { panel.replaceChildren(el('p', 'Select a capability to see sources and declared tools.', 'muted')); return; }
  const heading = el('h3', row.name);
  const status = el('p', `Setup: ${setupNames[row.status] || row.status} · Skill: ${row.skillInstalled ? 'installed' : 'not installed'}`);
  const readiness = el('p', `Runtime readiness: ${row.readiness || 'Not checked'}`);
  panel.replaceChildren(heading, el('p', row.description), status, readiness, el('h4', 'Skill copies'), sourceDetails(row.copies), el('h4', 'Declared tools'));
  if (!row.tools.length) panel.append(el('p', 'No separate tool declared.'));
  for (const tool of row.tools) {
    const entry = el('div'); entry.append(el('code', tool.declaration), el('p', `Entry: ${tool.status}`));
    if (tool.sources?.length) entry.append(sourceDetails(tool.sources));
    panel.append(entry);
  }
}
function metrics(target, values) {
  $(target).replaceChildren(...values.map(([label, value]) => {
    const node = el('div'); node.append(el('strong', value ?? '—'), el('span', label)); return node;
  }));
}
function renderCapabilities() {
  if (!data) return;
  const items = data.capabilities.items;
  const rows = items.filter(row => `${row.name} ${row.description}`.toLowerCase().includes(state.query) && (state.setup === 'all' || state.setup === row.status));
  state.count = rows.length; state.total = items.length;
  if (!rows.some(row => row.name === state.selected)) state.selected = rows[0]?.name || '';
  tables['capabilities-table'].applyData({ headers: ['Capability', 'Purpose', 'Setup'], rows: rows.map(row => {
    const button = el('button', row.name.replace(/^automata-/, ''), 'capability-select');
    button.type = 'button'; button.setAttribute('aria-pressed', String(state.selected === row.name));
    button.addEventListener('click', () => {
      state.selected = row.name;
      for (const item of tables['capabilities-table'].querySelectorAll('.capability-select'))
        item.setAttribute('aria-pressed', String(item === button));
      capabilityDetail(row);
    });
    return [button, row.description, setupNames[row.status] || row.status];
  }) });
  capabilityDetail(items.find(row => row.name === state.selected));
}
function renderCharts() {
  if (!data) return;
  const activity = data.activity; const available = activity.status === 'ready';
  const rows = state.limit === 'all' ? activity.rows : activity.rows.slice(0, 10);
  const common = { available, timezone: activity.window?.timezone || state.timezone, bucket: activity.bucket, timeline: activity.timeline || [] };
  timeline.applyData({ ...common, rows: activity.rows });
  ranking.applyData({ ...common, rows });
  $('timeline-state').textContent = !libraryReady ? 'ECharts unavailable; counts remain below.' : !available ? 'Recording unavailable.' : `${activity.timeline.length} ${activity.bucket === 'hour' ? 'hourly' : 'daily'} buckets · ${common.timezone}`;
  $('chart-state').textContent = !libraryReady ? 'ECharts unavailable; ranking data remains below.' : !available ? 'Recording unavailable.' : `Showing ${rows.length} of ${activity.rows.length} recorded skills`;
  tables['activity-table'].applyData({ headers: ['Skill', 'Load events', 'Latest recorded load'], rows: rows.map(row => [row.name, row.count, when(row.latest, common.timezone)]) });
}
function updateSkillOptions(snapshot) {
  const names = new Set([...(snapshot.activity.skillOptions || []), ...snapshot.capabilities.items.map(row => row.name)]);
  const select = $('skill');
  select.replaceChildren(new Option('All skills', ''), ...[...names].sort().map(name => new Option(name, name)));
  if (state.skill && !names.has(state.skill)) select.add(new Option(state.skill, state.skill));
  select.value = state.skill;
}
function render(snapshot) {
  data = snapshot;
  $('scope').textContent = `Project: ${data.project} · ${data.scope}`;
  $('warnings').textContent = (data.warnings || []).join(' · ');
  const items = data.capabilities.items;
  const nextCapabilities = JSON.stringify(data.capabilities);
  const capabilitiesChanged = nextCapabilities !== capabilityFingerprint;
  if (capabilitiesChanged) metrics('inventory', Object.entries(setupNames).map(([status, title]) => [title, items.filter(row => row.status === status).length]));
  $('identity-source').textContent = data.identity.source;
  $('identity-modified').textContent = data.identity.modified ? `· Modified ${when(data.identity.modified)}` : '';
  if ($('identity-body').textContent !== data.identity.body) $('identity-body').textContent = data.identity.body;
  $('identity-note').textContent = data.identity.note;
  if (capabilitiesChanged) {
    renderCapabilities();
    tables['other-tools-table'].applyData({ headers: ['Name', 'Kind', 'Sources'], rows: data.capabilities.otherTools.map(row => [row.name, row.kind, sourceDetails(row.copies)]) });
    $('capability-note').textContent = data.capabilities.note;
    capabilityFingerprint = nextCapabilities;
  }
  updateSkillOptions(data);
  const activity = data.activity;
  metrics('activity-counts', [['Recorded load events', activity.total], ['Distinct recorded skills', activity.distinct], ['Last 24h (all project records)', activity.last24h]]);
  $('window').textContent = activity.window ? `Selected window: ${when(activity.window.start, activity.window.timezone)} → ${when(activity.window.end, activity.window.timezone)} (${activity.window.timezone})` : '';
  const installed = items.filter(row => row.skillInstalled);
  const used = new Set(activity.rows.map(row => row.name));
  $('coverage').textContent = activity.status === 'ready'
    ? `${installed.filter(row => used.has(row.name)).length} of ${installed.length} installed skills have a recorded load in the selected window. ${activity.coverageNote || 'Missing records do not establish inactivity or recorder uptime.'}`
    : `Activity recording is unavailable. ${activity.coverageNote || 'Inventory remains available; usage is unknown.'}`;
  $('period').textContent = activity.status === 'ready'
    ? `Available project records: ${when(activity.availableFirst)} → ${when(activity.availableLatest)}. These bounds are not recorder uptime.`
    : `Source: ${activity.source}${activity.error ? ' · Reader error: ' + activity.error : ''}`;
  $('activity-note').textContent = activity.note + (activity.invalid ? ` ${activity.invalid} invalid project records were skipped.` : '');
  renderCharts();
}
function setTab(name, focus = false) {
  state.tab = name;
  for (const tab of ['identity', 'capabilities', 'statistics']) {
    const active = tab === name; const button = $(`tab-${tab}`);
    button.setAttribute('aria-selected', String(active)); button.tabIndex = active ? 0 : -1;
    $(tab).hidden = !active;
  }
  if (focus) $(`tab-${name}`).focus();
  if (name === 'statistics') { timeline.redraw(); ranking.redraw(); }
}
for (const tab of ['identity', 'capabilities', 'statistics']) {
  $(`tab-${tab}`).addEventListener('click', () => setTab(tab));
  $(`tab-${tab}`).addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault(); const tabs = ['identity', 'capabilities', 'statistics'];
    const index = event.key === 'Home' ? 0 : event.key === 'End' ? 2 : (tabs.indexOf(state.tab) + (event.key === 'ArrowRight' ? 1 : 2)) % 3;
    setTab(tabs[index], true);
  });
}
function status() {
  const node = $('status'); node.dataset.state = state.error ? 'error' : 'ready';
  const age = lastSuccess ? Math.floor((Date.now() - lastSuccess) / 1000) : null;
  node.textContent = state.error ? `${state.error} ${age === null ? 'No data yet.' : `Showing data from ${age}s ago.`}`
    : lastSuccess ? `${$('auto').checked ? 'Auto-refresh' : 'Paused'} · updated ${age}s ago` : 'Connecting…';
}
function params() {
  const query = new URLSearchParams({ range: state.range, timezone: state.timezone });
  if (state.skill) query.set('skill', state.skill);
  if (state.range === 'custom') { query.set('start', $('start').value); query.set('end', $('end').value); }
  return query;
}
async function refresh() {
  if (busy) { queued = true; return; }
  busy = true; const request = params().toString();
  try {
    // Let the server validate timezone, dates and skill; never substitute a different window.
    const response = await fetch(`/api/anatomy?${request}`, { cache: 'no-store', signal: AbortSignal.timeout(8000) });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(typeof body.detail === 'string' ? body.detail : `Snapshot unavailable (${response.status})`);
    }
    const snapshot = await response.json();
    if (request === params().toString()) { render(snapshot); lastSuccess = Date.now(); state.error = ''; state.phase = 'ready'; }
    else queued = true;
  } catch (error) { if (request === params().toString()) { state.error = error.message || 'Refresh failed.'; state.phase = 'error'; } }
  finally { busy = false; status(); if (queued) { queued = false; refresh(); } }
}
$('capability-filter').addEventListener('input', event => { state.query = event.target.value.toLowerCase().trim(); renderCapabilities(); });
$('setup-filter').addEventListener('change', event => { state.setup = event.target.value; renderCapabilities(); });
$('chart-limit').addEventListener('change', event => { state.limit = event.target.value; renderCharts(); });
$('range').addEventListener('change', event => { state.range = event.target.value; $('custom-dates').hidden = state.range !== 'custom'; if (state.range !== 'custom' || ($('start').value && $('end').value)) refresh(); });
$('timezone').value = state.timezone;
$('timezone').addEventListener('change', event => { state.timezone = event.target.value.trim(); refresh(); });
$('skill').addEventListener('change', event => { state.skill = event.target.value; refresh(); });
for (const id of ['start', 'end']) $(id).addEventListener('change', () => { if ($('start').value && $('end').value) refresh(); });
$('refresh').addEventListener('click', refresh);
$('auto').addEventListener('change', () => { status(); if ($('auto').checked) refresh(); });
initializeTheme(); $('theme').value = getTheme().preference;
$('theme').addEventListener('change', event => setTheme(event.target.value));
document.addEventListener('anatomy-theme-change', () => { $('theme').value = getTheme().preference; timeline.redraw(); ranking.redraw(); });
setInterval(() => { if ($('auto').checked) refresh(); }, 5000);
setInterval(status, 1000);
loadChartLibrary().then(library => { libraryReady = Boolean(library); renderCharts(); });
refresh();
