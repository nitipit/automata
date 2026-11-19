type Bridge = { status: string; connect(): Promise<void>; close(): void };
type BridgeClass = new (options: { url: string; token: string }) => Bridge;
export const bridgeWindow = window as Window & { awr?: Bridge; __automataBridgeTicket?: string };
export const wsOrigin = `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}`;

let BridgeClass: BridgeClass | undefined;
let cancelBootstrap: (() => void) | undefined;
let bootstrapUncertain = false;

// The Web Chat adapter supplies the pinned classic artifact with a one-shot
// in-memory ticket, never a URL fragment. After bootstrap, reconnects use its
// constructor directly.
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
    const finish = (error?: Error) => {
      clearTimeout(deadline);
      cancelBootstrap = undefined;
      script.onload = script.onerror = null;
      delete bridgeWindow.__automataBridgeTicket;
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
      // ticket in this document when execution of this script is uncertain.
      bootstrapUncertain = true;
      finish(new Error("UI bridge load timed out"));
    }, 5000);
    cancelBootstrap = () => { bootstrapUncertain = true; finish(new Error("UI bridge load cancelled")); };
    script.onload = () => finish();
    script.onerror = () => finish(new Error("UI bridge could not load"));
    bridgeWindow.__automataBridgeTicket = ticket;
    document.head.append(script);
  });
}

export function bridgeNeedsReload() { return bootstrapUncertain; }
export function closeBridge() {
  cancelBootstrap?.();
  bridgeWindow.awr?.close();
}
