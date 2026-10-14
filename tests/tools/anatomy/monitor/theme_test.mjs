import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync('src/automata/tools/anatomy/templates/shared/theme.js', 'utf8');

test('shared preference refreshes on history restoration without changing monitor state', async () => {
  const handlers = {};
  const storage = new Map([['anatomy-theme', 'dark']]);
  const picker = { value: 'dark' };
  const media = { matches: false, addEventListener: (name, handler) => { handlers[name] = handler; } };
  globalThis.matchMedia = () => media;
  globalThis.addEventListener = (name, handler) => { handlers[name] = handler; };
  globalThis.localStorage = {
    getItem: name => storage.get(name),
    setItem: (name, value) => storage.set(name, value),
  };
  globalThis.document = {
    documentElement: { dataset: {} },
    dispatchEvent: () => {},
    getElementById: name => name === 'theme' ? picker : null,
    createElement: () => ({}),
    head: { append: () => {} },
  };
  try {
    const theme = await import('data:text/javascript,' + encodeURIComponent(source));
    assert.equal(theme.initializeTheme(), 'dark');
    assert.equal(document.documentElement.dataset.theme, 'dark');
    storage.set('anatomy-theme', 'light'); // Changed by the catalog document.
    handlers.pageshow();
    assert.equal(picker.value, 'light');
    assert.deepEqual(theme.getTheme(), { preference: 'light', resolved: 'light' });
    assert.equal(document.documentElement.dataset.theme, 'light');
    assert.throws(() => theme.setTheme('invalid'), RangeError);
    theme.setTheme('system');
    media.matches = true;
    handlers.change();
    assert.deepEqual(theme.getTheme(), { preference: 'system', resolved: 'dark' });
    assert.deepEqual([...storage.keys()], ['anatomy-theme']);
  } finally {
    for (const name of ['matchMedia', 'addEventListener', 'localStorage', 'document']) {
      delete globalThis[name];
    }
  }
});
