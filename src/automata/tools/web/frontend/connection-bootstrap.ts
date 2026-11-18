// Classic script: scrub incoming credentials before the chat module loads.
// Only #admission is a reconnect credential; #token is a transient bridge ticket.
(() => {
  const fragment = new URLSearchParams(location.hash.slice(1));
  if (!fragment.has("admission") && !fragment.has("token")) return;
  const values = fragment.getAll("admission");
  if (values.length === 1 && values[0]) {
    (window as Window & { __automataChatAdmission?: string }).__automataChatAdmission = values[0];
  }
  history.replaceState(history.state, "", location.pathname + location.search);
})();
