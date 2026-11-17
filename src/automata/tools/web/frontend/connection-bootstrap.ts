// Classic script, deliberately before the upstream bridge and the chat module.
// Retain only this tab/origin's admission credential, never titles or history.
(() => {
  const fragment = new URLSearchParams(location.hash.slice(1));
  const supplied = fragment.get("token");
  try {
    if (supplied) sessionStorage.setItem("automata.chat.token", supplied);
    else {
      const saved = sessionStorage.getItem("automata.chat.token");
      if (saved) {
        fragment.set("token", saved);
        history.replaceState(null, "", `${location.pathname}${location.search}#${fragment}`);
      }
    }
  } catch {
    // Storage-denied tabs can still use their original admission URL once.
  }
})();
