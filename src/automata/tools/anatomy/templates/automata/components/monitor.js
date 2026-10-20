import { parseMonitorState, serializeMonitorState } from './monitor-state.js';
import { SkillLoadsChart, SkillTimelineChart, loadChartLibrary } from './activity-chart.js';

/** Overview and Activity each own one bounded snapshot/polling lifecycle. */
export function initializeAutomata() {
  const $ = id => document.getElementById(id);
  const activityPage = $('dashboard-automata').dataset.section === 'activity';
  const state = parseMonitorState(location.search, Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC');
  const lifetime = new AbortController();
  let disposed = false, busy = false, queued = false, data = null, lastSuccess = null, error = '', libraryReady = false;
  const el = (tag, text) => { const node = document.createElement(tag); if (text !== undefined) node.textContent = String(text); return node; };
  const when = (value, timezone = data?.activity?.window?.timezone || state.timezone) => value ? new Intl.DateTimeFormat(undefined, { timeZone: timezone, dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : 'No recorded event';
  function persist() {
    const all = serializeMonitorState({ ...state, paused: !$('auto').checked });
    const allowed = activityPage ? ['range','timezone','skill','limit','paused','start','end'] : ['paused'];
    const query = new URLSearchParams([...new URLSearchParams(all)].filter(([key]) => allowed.includes(key)));
    history.replaceState(null, '', `${location.pathname}?${query}`);
    try { sessionStorage.setItem(`anatomy-query-${activityPage ? 'activity' : 'overview'}`, query); } catch { /* URL remains authoritative. */ }
    document.dispatchEvent(new Event('anatomy-query-change'));
  }
  function metrics(target, values) {
    $(target).replaceChildren(...values.map(([label, value]) => { const node = el('div'); node.append(el('strong', value ?? '—'), el('span', label)); return node; }));
  }
  let ranking, timeline;
  if (activityPage) {
    ranking = SkillLoadsChart.create({ data: { rows: [], timeline: [], available: false, timezone: state.timezone } });
    timeline = SkillTimelineChart.create({ data: { rows: [], timeline: [], available: false, timezone: state.timezone } });
    $('activity-chart').append(ranking); $('timeline-chart').append(timeline);
  }
  function renderCharts() {
    if (!activityPage || !data) return;
    const activity = data.activity, available = activity.status === 'ready';
    const rows = state.limit === 'all' ? activity.rows : activity.rows.slice(0, 10);
    const common = { available, timezone: activity.window?.timezone || state.timezone, bucket: activity.bucket, timeline: activity.timeline || [] };
    timeline.applyData({ ...common, rows: activity.rows }); ranking.applyData({ ...common, rows });
    $('timeline-state').textContent = !libraryReady ? 'ECharts unavailable; counts remain below.' : !available ? 'Recording unavailable.' : `${activity.timeline.length} ${activity.bucket === 'hour' ? 'hourly' : 'daily'} buckets · ${common.timezone}`;
    $('chart-state').textContent = !libraryReady ? 'ECharts unavailable; ranking data remains below.' : !available ? 'Recording unavailable.' : `Showing ${rows.length} of ${activity.rows.length} recorded skills`;
    const table = el('table'), head = el('thead'), header = el('tr'), body = el('tbody');
    for (const title of ['Skill', 'Load events', 'Latest recorded load']) { const cell = el('th', title); cell.scope = 'col'; header.append(cell); }
    head.append(header); table.append(head, body);
    for (const row of rows) { const tr = el('tr'); for (const value of [row.name, row.count, when(row.latest, common.timezone)]) tr.append(el('td', value)); body.append(tr); }
    if (!rows.length) { const tr = el('tr'), cell = el('td', 'No matching records.'); cell.colSpan = 3; tr.append(cell); body.append(tr); }
    $('activity-table').replaceChildren(table);
  }
  function render(snapshot) {
    data = snapshot;
    $('scope').textContent = `Project: ${data.project} · ${data.scope}`;
    $('warnings').textContent = (data.warnings || []).join(' · ');
    const items = data.capabilities.items;
    if (!activityPage) {
      metrics('inventory', [['Installed skills', items.filter(row => row.skillInstalled).length], ['Available skills', items.filter(row => !row.skillInstalled).length], ['Incomplete setup', items.filter(row => row.status === 'incomplete').length]]);
      $('identity-source').textContent = data.identity.source;
      $('identity-modified').textContent = data.identity.modified ? `· Modified ${when(data.identity.modified)}` : '';
      if ($('identity-body').textContent !== data.identity.body) $('identity-body').textContent = data.identity.body;
      $('identity-note').textContent = data.identity.note;
      return;
    }
    const names = new Set([...(data.activity.skillOptions || []), ...items.map(row => row.name)]);
    const select = $('skill');
    select.replaceChildren(new Option('All skills', ''), ...[...names].sort().map(name => new Option(name, name)));
    if (state.skill && !names.has(state.skill)) select.add(new Option(state.skill, state.skill));
    select.value = state.skill;
    const activity = data.activity;
    metrics('activity-counts', [['Recorded load events', activity.total], ['Distinct recorded skills', activity.distinct], ['Last 24h (all project records)', activity.last24h]]);
    $('window').textContent = activity.window ? `Selected window: ${when(activity.window.start, activity.window.timezone)} → ${when(activity.window.end, activity.window.timezone)} (${activity.window.timezone})` : '';
    const installed = items.filter(row => row.skillInstalled), used = new Set(activity.rows.map(row => row.name));
    $('coverage').textContent = activity.status === 'ready' ? `${installed.filter(row => used.has(row.name)).length} of ${installed.length} installed skills have a recorded load in the selected window. ${activity.coverageNote || 'Missing records do not establish inactivity or recorder uptime.'}` : `Activity recording is unavailable. ${activity.coverageNote || 'Inventory remains available; usage is unknown.'}`;
    $('period').textContent = activity.status === 'ready' ? `Available project records: ${when(activity.availableFirst)} → ${when(activity.availableLatest)}. These bounds are not recorder uptime.` : `Source: ${activity.source}${activity.error ? ' · Reader error: ' + activity.error : ''}`;
    $('activity-note').textContent = activity.note + (activity.invalid ? ` ${activity.invalid} invalid project records were skipped.` : '');
    renderCharts();
  }
  function status() {
    const age = lastSuccess ? Math.floor((Date.now() - lastSuccess) / 1000) : null;
    $('status').dataset.state = error ? 'error' : 'ready';
    $('status').textContent = error ? `${error} ${age === null ? 'No data yet.' : `Showing data from ${age}s ago.`}` : lastSuccess ? `${$('auto').checked ? 'Auto-refresh' : 'Paused'} · updated ${age}s ago` : 'Connecting…';
  }
  function params() {
    const query = new URLSearchParams({ range: state.range, timezone: state.timezone });
    if (state.skill) query.set('skill', state.skill);
    if (state.range === 'custom') { query.set('start', state.start); query.set('end', state.end); }
    return query;
  }
  async function refresh() {
    if (disposed) return;
    if (busy) { queued = true; return; }
    busy = true; const request = params().toString();
    try {
      const response = await fetch(`/api/anatomy?${request}`, { cache: 'no-store', signal: AbortSignal.any([lifetime.signal, AbortSignal.timeout(8000)]) });
      if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(typeof body.detail === 'string' ? body.detail : `Snapshot unavailable (${response.status})`); }
      const snapshot = await response.json();
      if (!disposed && request === params().toString()) { render(snapshot); persist(); lastSuccess = Date.now(); error = ''; } else queued = true;
    } catch (failure) { if (request === params().toString()) error = failure.message || 'Refresh failed.'; }
    finally { busy = false; status(); if (queued) { queued = false; refresh(); } }
  }
  if (activityPage) {
    for (const [id, value] of Object.entries({ range:state.range, timezone:state.timezone, 'chart-limit':state.limit, start:state.start, end:state.end })) $(id).value = value;
    $('custom-dates').hidden = state.range !== 'custom';
    $('chart-limit').addEventListener('change', event => { state.limit = event.target.value; renderCharts(); persist(); });
    for (const id of ['range','timezone','skill','start','end']) $(id).addEventListener('change', event => {
      state[id] = event.target.value.trim(); $('custom-dates').hidden = state.range !== 'custom'; persist();
      if (state.range !== 'custom' || (state.start && state.end)) refresh();
    });
    document.addEventListener('anatomy-theme-change', () => { timeline.redraw(); ranking.redraw(); });
    loadChartLibrary().then(library => { libraryReady = Boolean(library); if (!disposed) renderCharts(); });
  }
  $('auto').checked = !state.paused;
  $('auto').addEventListener('change', () => { persist(); status(); if ($('auto').checked) refresh(); });
  $('refresh').addEventListener('click', refresh);
  const polling = setInterval(() => { if ($('auto').checked) refresh(); }, 5000), aging = setInterval(status, 1000);
  window.addEventListener('pagehide', () => { disposed = true; clearInterval(polling); clearInterval(aging); lifetime.abort(); }, { once:true });
  window.addEventListener('pageshow', event => { if (event.persisted) location.reload(); });
  refresh();
}
initializeAutomata();
