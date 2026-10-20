// Local inventory state is bounded and URL-owned; no monitor or install controls.
const search = document.getElementById('tool-search');
const setup = document.getElementById('tool-setup');
const params = new URLSearchParams(location.search);
const edited = search.value !== search.defaultValue;
if (!edited) search.value = (params.get('query') || '').slice(0, 256);
if (setup.value === 'all') setup.value = ['installed','available'].includes(params.get('setup')) ? params.get('setup') : 'all';
function filter(persist = false) {
  const query = search.value.trim().toLocaleLowerCase();
  let count = 0;
  for (const row of document.querySelectorAll('[data-tool]')) {
    row.hidden = !row.dataset.name.toLocaleLowerCase().includes(query) || (setup.value !== 'all' && row.dataset.setup !== setup.value);
    if (!row.hidden) count++;
  }
  document.getElementById('tool-count').textContent = `${count} tool${count === 1 ? '' : 's'} shown`;
  document.getElementById('tools-empty').hidden = count !== 0;
  if (persist) {
    const queryParams = new URLSearchParams();
    if (query) queryParams.set('query', query);
    if (setup.value !== 'all') queryParams.set('setup', setup.value);
    history.replaceState(null, '', location.pathname + (queryParams.size ? '?' + queryParams : ''));
    try { sessionStorage.setItem('anatomy-query-tools', queryParams); } catch { /* URL remains usable. */ }
    document.dispatchEvent(new Event('anatomy-query-change'));
  }
}
search.addEventListener('input', () => filter(true));
setup.addEventListener('change', () => filter(true));
filter(edited);
search.dataset.ready = 'true';
