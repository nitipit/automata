/** Closed, bounded URL contract. No arbitrary return paths or storage deserialization. */
const choices = (value, allowed, fallback) => allowed.includes(value) ? value : fallback;
const text = (value, max = 128) => typeof value === 'string' && value.length <= max && !/[\x00-\x1f]/.test(value) ? value : '';
function date(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return '';
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(parsed.valueOf()) && parsed.toISOString().slice(0,10) === value ? value : '';
}
function timezone(value, fallback) {
  try { new Intl.DateTimeFormat('en', {timeZone:value}).format(); return value || fallback; }
  catch { return fallback; }
}
export function parseMonitorState(search, defaultZone = 'UTC') {
  const p = new URLSearchParams(search);
  const start = date(p.get('start')), end = date(p.get('end'));
  let range = choices(p.get('range'), ['24h','7d','30d','custom'], '7d');
  if (range === 'custom' && (!start || !end || start > end)) range = '7d';
  return {
    tab:choices(p.get('tab'), ['identity','capabilities','statistics'], 'identity'),
    query:text(p.get('query'),256).trim().toLowerCase(),
    setup:choices(p.get('setup'), ['all','installed','available','incomplete','unknown'], 'all'),
    selected:text(p.get('selected')), range,
    timezone:timezone(text(p.get('timezone')), defaultZone),
    skill:text(p.get('skill')), limit:choices(p.get('limit'), ['10','all'], '10'),
    paused:p.get('paused') === '1', start, end,
  };
}
export function serializeMonitorState(state) {
  const p = new URLSearchParams();
  for (const key of ['tab','query','setup','selected','range','timezone','skill','limit','start','end']) {
    if (state[key]) p.set(key, state[key]);
  }
  p.set('paused', state.paused ? '1' : '0');
  return p.toString();
}
