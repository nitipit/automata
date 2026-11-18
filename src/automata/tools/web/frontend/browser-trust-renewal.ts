import { browserTrustProof } from "./browser-trust-proof";

const RENEW_AFTER = 10 * 60_000;
const RETRY_AFTER = 60_000;
const REQUEST_TIMEOUT = 10_000;

type Writer = { admission: string; ticket: string };

/** A restartable lifecycle for the current writer, without storing its credentials. */
export function createBrowserTrustRenewal({sessionPath, getWriter}: {
  sessionPath: string; getWriter: () => Writer | undefined;
}) {
  let active = false;
  let disposed = false;
  let timer: number | undefined;
  let dueWall = 0;
  let dueMonotonic = 0;
  let pending: AbortController | undefined;

  function waitFor(delay: number) {
    dueWall = Date.now() + delay;
    dueMonotonic = performance.now() + delay;
  }
  function remaining() { return Math.min(dueWall - Date.now(), dueMonotonic - performance.now()); }
  function schedule() {
    window.clearTimeout(timer);
    if (active && !pending) timer = window.setTimeout(check, Math.max(0, remaining()));
  }

  function check() {
    if (!active || pending) return;
    if (remaining() > 0) { schedule(); return; }
    const writer = getWriter();
    if (!writer) { waitFor(RETRY_AFTER); schedule(); return; }
    const controller = new AbortController();
    pending = controller;
    const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT);
    void (async () => {
      let refreshed = false;
      try {
        const aborted = new Promise<undefined>((resolve) => {
          controller.signal.addEventListener("abort", () => resolve(undefined), {once: true});
        });
        const proof = await Promise.race([browserTrustProof(true), aborted]);
        if (!proof || controller.signal.aborted || pending !== controller) return;
        const current = getWriter();
        if (!current || current.ticket !== writer.ticket || current.admission !== writer.admission) return;
        const response = await fetch(`${sessionPath}/browser-trust`, {
          method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
          headers: {"Content-Type": "application/json", Authorization: `Bearer ${current.admission}`},
          body: JSON.stringify({proof, ticket: current.ticket}), signal: controller.signal,
        });
        refreshed = response.status === 204;
        await response.body?.cancel();
      } catch {
        // Trust is optional for this tab's writing; failures do not disconnect it.
      } finally {
        window.clearTimeout(timeout);
        if (pending === controller) {
          pending = undefined;
          waitFor(refreshed ? RENEW_AFTER : RETRY_AFTER);
          schedule();
        }
      }
    })();
  }

  function start() {
    if (disposed || active) return;
    active = true;
    waitFor(0);
    window.addEventListener("focus", check);
    window.addEventListener("pageshow", check);
    document.addEventListener("visibilitychange", check);
    check();
  }

  function stop() {
    active = false;
    window.clearTimeout(timer);
    pending?.abort();
    pending = undefined;
    window.removeEventListener("focus", check);
    window.removeEventListener("pageshow", check);
    document.removeEventListener("visibilitychange", check);
  }

  return {start, stop, dispose: () => { disposed = true; stop(); }};
}
