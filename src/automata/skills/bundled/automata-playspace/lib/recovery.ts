/** Playspace-owned, single-writer Cache Storage. Never imports transport or credentials. */
export function createCacheRecovery({ cacheStorage = globalThis.caches,
  cacheName = "automata-playspace-chat-v2", key, onState = (_message: string) => {} }: {
    cacheStorage?: CacheStorage; cacheName?: string; key: string; onState?: (message: string) => void;
  }) {
  let writes = Promise.resolve();
  let revision = 0;
  let live = true;
  const notify = message => { if (live) onState(message); };
  if (!key) throw new Error("Explicit same-origin recovery key required");
  return {
    async load() {
      try {
        if (!cacheStorage) throw new Error("unavailable");
        const cache = await cacheStorage.open(cacheName);
        const response = await cache.match(key);
        if (!response) { notify("No v2 snapshot yet · v1 cache preserved and not imported"); return null; }
        const snapshot = await response.json();
        notify("Local snapshot read · validation required");
        return snapshot;
      } catch {
        notify("Recovery unavailable or malformed · current draft retained; cache not erased");
        return null;
      }
    },
    save(snapshot) {
      let serialized;
      try { serialized = JSON.stringify(snapshot); }
      catch { notify("Not saved · snapshot is not serializable"); return Promise.resolve(false); }
      const current = ++revision;
      notify("Saving local draft…");
      const result = writes.then(async () => {
        try {
          if (!cacheStorage) throw new Error("unavailable");
          const cache = await cacheStorage.open(cacheName);
          await cache.put(key, new Response(serialized, { headers: { "Content-Type": "application/json" } }));
          if (current === revision) notify("Saved v2 locally · this origin/profile only · v1 not imported");
          return true;
        } catch {
          notify("Not saved · browser storage failed; current draft retained");
          return false;
        }
      });
      writes = result.then(() => {});
      return result;
    },
    flush: () => writes,
    dispose() { live = false; },
    cacheName, key,
  };
}
