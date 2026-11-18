import { browserTrustProof } from "./browser-trust-proof";

const action = document.querySelector<HTMLButtonElement>("#trust-create");
const status = document.querySelector<HTMLElement>("#trust-status");
const URL_PATH = /^\/sessions\/[A-Za-z0-9_-]{1,256}\/#admission=[A-Za-z0-9_-]{1,256}$/;

if (action && status) {
  const button = action;
  const message = status;
  const intent = status.dataset.intent;
  const nav = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
  const auto = status.dataset.auto === "1" && nav?.type === "navigate" &&
    !window.location.hash && window.top === window;
  let submitted = false;

  function visible() {
    return !(document as Document & {prerendering?: boolean}).prerendering &&
      document.visibilityState === "visible";
  }

  async function create() {
    if (submitted || !intent || !visible()) return;
    submitted = true;
    button.disabled = true;
    message.textContent = "Checking browser trust…";
    try {
      const proof = await browserTrustProof(false);
      // Storage can complete after a focus/visibility transition. Wait again for
      // activation rather than dispatching from a now-hidden document.
      if (!visible()) {
        submitted = false;
        button.disabled = false;
        message.textContent = "Start a new Pi session in this tab.";
        return;
      }
      if (!proof) {
        message.textContent = "Browser trust is unavailable. Connect an authenticated Web Chat tab, then reopen this page.";
        return;
      }
      message.textContent = "Starting a new chat…";
      const response = await fetch("/sessions/trust/create", {
        method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: {"Content-Type": "application/json"}, body: JSON.stringify({proof, intent}),
        signal: AbortSignal.timeout(50_000),
      });
      if (!response.ok) {
        const failure = await response.json();
        message.textContent = failure?.code === "browser_untrusted" ?
          "Browser trust expired. Connect an authenticated Web Chat tab, then reopen this page." :
          typeof failure?.error === "string" ? failure.error : "New chat unavailable. Reopen this page to try again.";
        return;
      }
      const {url} = await response.json();
      if (typeof url !== "string" || !URL_PATH.test(url)) throw new Error("Unexpected admission path");
      window.location.replace(url);
    } catch {
      message.textContent = "New chat could not be confirmed. It was not retried.";
    }
  }

  button.disabled = false;
  button.addEventListener("click", (event) => { if (event.isTrusted) void create(); });
  if (auto) {
    const activate = () => { if (visible()) void create(); };
    document.addEventListener("visibilitychange", activate);
    document.addEventListener("prerenderingchange", activate);
    activate();
  }
}
