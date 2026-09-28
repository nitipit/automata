/** Backend messages + three-way merge of browser-owned edits. No input replay. */
const clone = value => value === undefined ? undefined : structuredClone(value);
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);

export function mergeState(base, local, remote) {
  const merged = clone(remote);
  let conflict = false;
  function edit(before, ours, theirs) {
    if (equal(ours, before)) return clone(theirs);
    if (!equal(theirs, before) && !equal(theirs, ours)) conflict = true;
    return clone(ours);
  }
  merged.artifact = edit(base.artifact, local.artifact, remote.artifact);
  merged.view = edit(base.view, local.view, remote.view);
  for (const [id, row] of Object.entries(merged.conversations)) {
    const before = base.conversations[id], ours = local.conversations[id];
    row.draft = edit(before.draft, ours.draft, row.draft);
    for (const message of row.messages) {
      const old = before.messages.find(m => m.id === message.id);
      const current = ours.messages.find(m => m.id === message.id);
      if (!old || !current) continue;
      for (const field of ["delivery", "interactions"]) {
        const value = edit(old[field], current[field], message[field]);
        if (value !== undefined) message[field] = value;
        else delete message[field];
      }
    }
  }
  return { value: merged, conflict, dirty: !equal(merged, remote) };
}

export function createStateSync({ state, api, render, controls, setStatus }) {
  let timer, stopped = false, controller;
  const queue = task => {
    const result = state.saveChain.catch(() => {}).then(task);
    state.saveChain = result;
    return result;
  };
  async function bounded(path, options = {}) {
    controller = new AbortController();
    const timeout = setTimeout(() => controller?.abort(), 15000);
    try { return await api(path, { ...options, signal: controller.signal }); }
    finally { clearTimeout(timeout); controller = null; }
  }
  function adopt(remote) {
    const merged = mergeState(state.base, state.value, remote);
    state.base = clone(remote);
    state.value = merged.value;
    state.dirty = merged.dirty;
    if (merged.conflict) {
      state.conflicted = true;
      controls.setConflict(true);
      setStatus("Conflict · local drafts retained. Copy local changes before reloading.", "error");
    }
    render();
    return !state.conflicted;
  }
  async function refreshInner() {
    const remote = await bounded("/api/state");
    if (stopped) return false;
    if (remote.revision !== state.base.revision) adopt(remote);
    return true;
  }
  function refresh() { return queue(refreshInner); }
  function saveNow() {
    clearTimeout(state.timer);
    if (!state.ready || state.conflicted || stopped) return Promise.resolve(false);
    return queue(async () => {
      if (state.conflicted || stopped) return false;
      // Only browser-owned edits are retried after a proven append-only rebase.
      // This is NOT a replay of posts, form submissions or agent deliveries.
      for (let attempt = 0; attempt < 2; attempt++) {
        const sent = clone(state.value);
        try {
          const saved = await bounded("/api/state", { method: "PUT", body: JSON.stringify(sent) });
          if (stopped) return false;
          const merged = mergeState(sent, state.value, saved);
          state.base = clone(saved);
          state.value = merged.value;
          state.dirty = merged.dirty;
          render();
          setStatus(state.dirty ? "Unsaved changes" : "All changes saved", state.dirty ? "pending" : "");
          return true;
        } catch (error) {
          if (stopped) return false;
          if (error.status === 409 && attempt === 0) {
            try { await refreshInner(); }
            catch { /* Retain local edits; report original conflict below. */ }
            if (!state.conflicted && state.value.revision !== sent.revision) continue;
          }
          state.dirty = true;
          if (error.status === 409) {
            state.conflicted = true;
            controls.setConflict(true);
          }
          setStatus(`${state.conflicted ? "Conflict" : "Save failed"} · ${error.message} · local edits retained`, "error");
          return false;
        }
      }
      return false;
    });
  }
  async function poll() {
    if (stopped) return;
    try { await refresh(); }
    catch { if (!stopped) setStatus("Catch-up unavailable · local drafts retained; no input replay", "error"); }
    finally { if (!stopped) timer = setTimeout(poll, document.hidden ? 5000 : 1200); }
  }
  return { saveNow, refresh,
    start() { stopped = false; state.base = clone(state.value); timer = setTimeout(poll, 1200); },
    stop() { stopped = true; clearTimeout(timer); controller?.abort(); },
  };
}
