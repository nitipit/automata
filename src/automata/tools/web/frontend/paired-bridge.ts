type Bridge = { status: string; connect(): Promise<void>; close(): void };
type BridgeClass = new (options: { url: string; token: string }) => Bridge;
export const bridgeWindow = window as Window & { awr?: Bridge };
export const wsOrigin = `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}`;

let BridgeClass: BridgeClass | undefined;
let cancelBootstrap: (() => void) | undefined;
let bootstrapUncertain = false;

// The pinned classic artifact exposes its constructor only after consuming a
// fragment token and opening /ws. Load it once, after the server reserves our
// pair. All subsequent attempts construct a new handle without touching the URL.
export async function prepareBridge(ticket: string): Promise<Bridge> {
  if (BridgeClass) {
    const bridge = new BridgeClass({ url: `${wsOrigin}/ws`, token: ticket });
    Object.defineProperty(window, "awr", { value: bridge, configurable: true });
    return bridge;
  }
  if (cancelBootstrap || bootstrapUncertain) throw new Error("UI bridge needs a page reload");
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "/bridge.js";
    const originalHash = location.hash;
    const fragment = `#${new URLSearchParams({ token: ticket })}`;
    const path = location.pathname + location.search;
    const finish = (error?: Error) => {
      clearTimeout(deadline);
      cancelBootstrap = undefined;
      script.onload = script.onerror = null;
      if (location.hash === fragment) history.replaceState(history.state, "", path + originalHash);
      script.remove();
      const bridge = bridgeWindow.awr;
      if (error || !bridge) {
        reject(error ?? new Error("UI bridge did not initialize"));
      } else {
        BridgeClass = bridge.constructor as BridgeClass;
        resolve(bridge);
      }
    };
    const deadline = window.setTimeout(() => {
      // An aborted loader may still evaluate later. Don't stage a later pair's
      // fragment in this document when execution of this script is uncertain.
      bootstrapUncertain = true;
      finish(new Error("UI bridge load timed out"));
    }, 5000);
    cancelBootstrap = () => { bootstrapUncertain = true; finish(new Error("UI bridge load cancelled")); };
    script.onload = () => finish();
    script.onerror = () => finish(new Error("UI bridge could not load"));
    history.replaceState(history.state, "", path + fragment);
    document.head.append(script);
  });
}

export function bridgeNeedsReload() { return bootstrapUncertain; }
export function closeBridge() {
  cancelBootstrap?.();
  bridgeWindow.awr?.close();
}
