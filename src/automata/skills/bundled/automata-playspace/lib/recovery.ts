import { cloneJSON } from "./contracts.js";

/** Single-writer Cache API I/O. Callers validate draft contracts before save/use. */
export function createCacheRecovery({ cacheStorage = globalThis.caches,
  cacheName, key, onState = () => {}, origin = globalThis.location?.origin }: {
  cacheStorage?: CacheStorage;
  cacheName: string;
  key: string;
  origin?: string;
  onState?: (message: string) => void;
}) {
  if (!cacheName || !origin) throw new Error("Explicit cache namespace and origin required");
  const url = new URL(key, origin);
  if (url.origin !== origin || url.username || url.password || url.hash) {
    throw new Error("Recovery key must be same-origin without credentials or fragment");
  }
  key = url.href;
  let writes = Promise.resolve();
  let revision = 0;
  let live = true;
  const notify = (message: string) => { if (live) onState(message); };
  return {
    async load() {
      if (!live) return null;
      try {
        if (!cacheStorage) throw new Error("unavailable");
        const cache = await cacheStorage.open(cacheName);
        if (!live) return null;
        const response = await cache.match(key);
        if (!live) return null;
        if (!response) { notify("No saved draft yet"); return null; }
        const snapshot = await response.json();
        if (!live) return null;
        notify("Snapshot read; validation required");
        return snapshot;
      } catch {
        notify("Recovery unavailable or malformed; current draft retained; cache not erased");
        return null;
      }
    },
    save(snapshot: unknown) {
      if (!live) return Promise.resolve(false);
      let serialized: string;
      try { serialized = JSON.stringify(cloneJSON(snapshot)); }
      catch { notify("Not saved; finite serializable JSON required"); return Promise.resolve(false); }
      const current = ++revision;
      notify("Saving local draft…");
      const result = writes.then(async () => {
        if (!live) return false;
        try {
          if (!cacheStorage) throw new Error("unavailable");
          const cache = await cacheStorage.open(cacheName);
          if (!live) return false;
          await cache.put(key, new Response(serialized, {
            headers: { "Content-Type": "application/json" },
          }));
          if (current === revision) notify("Saved locally; this origin/profile only");
          return true;
        } catch {
          notify("Not saved; browser storage failed; current draft retained");
          return false;
        }
      });
      writes = result.then(() => {});
      return result;
    },
    flush: () => writes,
    // Already-issued puts cannot be revoked; queued work and callbacks are fenced.
    dispose() { live = false; },
    cacheName, key,
  };
}
