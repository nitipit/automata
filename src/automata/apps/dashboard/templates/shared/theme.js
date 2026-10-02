const choices = new Set(['light', 'dark', 'system']);
const preferenceKey = 'anatomy-theme';
let preference = 'system';
let resolved = null;
let initialized = false;
const system = matchMedia('(prefers-color-scheme: dark)');

function applyTheme() {
  resolved = preference === 'system' ? (system.matches ? 'dark' : 'light') : preference;
  document.documentElement.dataset.theme = resolved;
  document.dispatchEvent(new CustomEvent('anatomy-theme-change', {detail:{preference, resolved}}));
}
export function initializeTheme() {
  if (!initialized) {
    try { const saved = localStorage.getItem(preferenceKey); if (choices.has(saved)) preference = saved; }
    catch { /* Storage is optional. */ }
    system.addEventListener('change', () => { if (preference === 'system') applyTheme(); });
    initialized = true;
  }
  applyTheme();
  return preference;
}
export function setTheme(value) {
  if (!choices.has(value)) throw new RangeError('Theme must be light, dark, or system');
  preference = value;
  try { localStorage.setItem(preferenceKey, value); } catch { /* Apply without persistence. */ }
  applyTheme();
}
export function getTheme() { return {preference, resolved}; }

// Document layout and semantic roles are shared; component-local styles stay in
// their Base subclasses. No standalone stylesheet or additional theme system.
const style = document.createElement('style');
style.textContent = `
:root {
  color-scheme:light;
  --aui-surface:#ffffff; --aui-text:#172b4d; --aui-muted-text:#475569;
  --aui-border:#cbd5e1; --aui-action:#1d4ed8; --aui-action-hover:#1e40af;
  --aui-action-text:#ffffff; --aui-danger:#b91c1c; --aui-focus:#1d4ed8;
  --aui-status:#475569; --anatomy-bg:#f8fafc; --anatomy-accent-soft:#dbeafe;
  --anatomy-success:#166534; --anatomy-warning:#92400e;
  --anatomy-chart-bar:#2563eb; --anatomy-chart-line:#0f766e;
  --anatomy-chart-grid:#e2e8f0; --anatomy-chart-text:#334155;
  --anatomy-chart-tooltip-bg:#ffffff; --anatomy-chart-tooltip-text:#172b4d;
  --anatomy-surface-raised:var(--aui-surface); --anatomy-text:var(--aui-text);
  --anatomy-muted:var(--aui-muted-text); --anatomy-border:var(--aui-border);
  --anatomy-accent:var(--aui-action); --anatomy-danger:var(--aui-danger);
}
:root[data-theme=dark] {
  color-scheme:dark;
  --aui-surface:#1e293b; --aui-text:#e2e8f0; --aui-muted-text:#b6c3d2;
  --aui-border:#475569; --aui-action:#60a5fa; --aui-action-hover:#93c5fd;
  --aui-action-text:#0b1220; --aui-danger:#fca5a5; --aui-focus:#93c5fd;
  --aui-status:#b6c3d2; --anatomy-bg:#0f172a; --anatomy-accent-soft:#1e3a5f;
  --anatomy-success:#86efac; --anatomy-warning:#fcd34d;
  --anatomy-chart-bar:#60a5fa; --anatomy-chart-line:#5eead4;
  --anatomy-chart-grid:#334155; --anatomy-chart-text:#cbd5e1;
  --anatomy-chart-tooltip-bg:#1e293b; --anatomy-chart-tooltip-text:#f1f5f9;
}
* {box-sizing:border-box;}
html, body {background:var(--anatomy-bg); color:var(--anatomy-text);}
body {margin:0; padding:clamp(1rem,3vw,2.5rem); font:15px/1.5 system-ui,sans-serif;}
main {max-width:1180px; margin:auto;}
h1,h2,h3,p {margin-top:0;}
h1 {font-size:clamp(1.8rem,3vw,2.5rem); line-height:1.15; margin-bottom:.5rem;}
h2 {font-size:1.35rem; margin-bottom:.35rem;}
h3 {font-size:1rem; margin-bottom:.75rem;}
p {margin-bottom:.8rem;}
a {color:var(--aui-action);}
.page-head,.header-actions,.refresh-line,.controls,.section-heading {
  display:flex; align-items:center; justify-content:space-between; gap:.85rem; flex-wrap:wrap;
}
.page-head {border-bottom:1px solid var(--anatomy-border); padding-bottom:1rem;}
.brand {font-weight:750;letter-spacing:.09em;text-decoration:none;color:var(--aui-text);}
.brand span {color:var(--aui-muted-text);}
.eyebrow {letter-spacing:.12em;font-size:.72rem;font-weight:700;color:var(--anatomy-accent);margin-bottom:.5rem;}
.muted,.small {color:var(--anatomy-muted);} .small {font-size:.84rem;}
.warning,#status[data-state=error] {color:var(--anatomy-danger);}
.refresh-line {justify-content:flex-start;padding:.85rem 0;font-size:.85rem;}
#scope {margin-right:auto;}
.tabs {display:flex;gap:.25rem;border-bottom:1px solid var(--anatomy-border);margin:.5rem 0 1.25rem;overflow-x:auto;}
.tabs button {background:none;color:var(--anatomy-muted);border:0;border-bottom:2px solid transparent;padding:.7rem 1rem;font:inherit;cursor:pointer;white-space:nowrap;}
.tabs button[aria-selected=true] {color:var(--anatomy-accent);border-bottom-color:var(--anatomy-accent);font-weight:650;}
[hidden] {display:none!important;} section,aui-card {min-width:0;} aui-card {display:block;}
.controls {justify-content:flex-start;margin:1rem 0;align-items:end;}
label {display:inline-flex;flex-direction:column;gap:.3rem;font-size:.85rem;font-weight:550;}
label:has(input[type=checkbox]) {flex-direction:row;align-items:center;font-weight:normal;}
input,select {max-width:100%;padding:.48rem .65rem;min-height:2.45rem;border:1px solid var(--anatomy-border);border-radius:.35rem;background:var(--anatomy-surface-raised);color:var(--anatomy-text);font:inherit;}
input[type=search] {width:min(22rem,100%);} input[type=checkbox] {min-height:auto;accent-color:var(--anatomy-accent);}
#timezone {width:13rem;}
:focus-visible {outline:3px solid var(--aui-focus);outline-offset:2px;}
.metrics {display:flex;gap:.75rem;flex-wrap:wrap;margin:1rem 0;}
.metrics>div {min-width:9rem;padding:.7rem 1rem;border:1px solid var(--anatomy-border);border-radius:.4rem;background:var(--anatomy-surface-raised);}
.metrics strong {display:block;font-size:1.4rem;font-variant-numeric:tabular-nums;}
.metrics span {color:var(--anatomy-muted);font-size:.8rem;}
.source,code {overflow-wrap:anywhere;}
#identity-body {padding:1rem;background:var(--anatomy-bg);color:var(--anatomy-text);border:1px solid var(--anatomy-border);border-radius:.35rem;max-height:55vh;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;font:.8rem/1.6 ui-monospace,monospace;}
.capability-layout {display:grid;grid-template-columns:minmax(0,1.2fr) minmax(15rem,.8fr);gap:1rem;align-items:start;}
.table-wrap {min-width:0;overflow-x:auto;}
.detail-panel {border:1px solid var(--anatomy-border);background:var(--anatomy-surface-raised);border-radius:.4rem;padding:1rem;min-width:0;overflow-wrap:anywhere;}
.detail-panel h3 {margin-bottom:.3rem;} .detail-panel ul {padding-left:1.25rem;}
.detail-panel li {margin:.4rem 0;} .detail-panel code {font-size:.78rem;}
.capability-select {display:block;width:100%;background:none;color:var(--anatomy-accent);border:0;padding:0;text-align:left;font:inherit;cursor:pointer;}
.capability-select[aria-pressed=true] {font-weight:700;}
#timeline-chart {min-height:250px;} #activity-chart {min-height:120px;}
.section-heading {margin-top:1.5rem;} .section-heading h3 {margin-bottom:0;}
details {margin:1rem 0;} summary {cursor:pointer;}
footer {border-top:1px solid var(--anatomy-border);margin-top:1.5rem;padding-top:1rem;}
.skip-link {position:absolute;top:-5rem;}
.skip-link:focus {top:.5rem;background:var(--aui-surface);padding:.5rem;z-index:10;}
.guide-heading {margin:2rem 0 1rem;} .goal {font-size:1.2rem;max-width:48rem;}
.guide-context {font-size:.85rem;padding:1rem;border-left:3px solid var(--aui-border);color:var(--aui-muted-text);max-width:65rem;}
.lesson {display:block;margin:1.6rem 0;padding:1.4rem;border:1px solid var(--aui-border);border-radius:.6rem;background:var(--aui-surface);}
.lesson>p,.lesson>ul {max-width:65rem;} .lesson h2 {margin-bottom:.7rem;} .lesson h3 {margin-top:1.2rem;}
.result {border-left:3px solid var(--anatomy-success);padding-left:1rem;margin-top:1rem;}
pre {max-width:100%;overflow:auto;} .next {display:block;margin:2rem 0;font-weight:600;}
@media(max-width:760px) {
  .capability-layout {grid-template-columns:1fr;}
  .header-actions {width:100%;justify-content:flex-start;}
  .metrics>div {flex:1 1 9rem;} .refresh-line #scope {flex-basis:100%;}
}
`;
document.head.append(style);
