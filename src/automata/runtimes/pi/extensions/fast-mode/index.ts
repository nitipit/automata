import type { ExtensionAPI, ExtensionContext, SessionEntry } from "@earendil-works/pi-coding-agent";

export const MODE_TYPE = "automata-fast-mode";
const STATUS_KEY = "automata-fast-mode";
type Route = { provider: string; api: string; id: string; baseUrl: string };
const record = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);

/** Best-effort SELECTED-route guard, not physical dispatch identity. Supported
 * use is official direct selection, no proxies/redirection or dispatch-time
 * model switches. Pi 1.0.4's payload hook omits the physical model argument.
 */
export function supportedRoute(model: unknown): model is Route {
  if (!record(model) || typeof model.baseUrl !== "string" || typeof model.id !== "string") return false;
  let url: URL;
  try { url = new URL(model.baseUrl); } catch { return false; }
  if (url.protocol !== "https:" || url.port || url.username || url.password || url.search || url.hash) return false;
  const path = url.pathname.replace(/\/+$/, "");
  if (model.provider === "openai") {
    return url.hostname === "api.openai.com" && path === "/v1" &&
      (model.api === "openai-responses" || model.api === "openai-completions");
  }
  return model.provider === "openai-codex" && model.api === "openai-codex-responses" &&
    url.hostname === "chatgpt.com" &&
    ["/backend-api", "/backend-api/codex", "/backend-api/codex/responses"].includes(path);
}

/** Raw active ancestry preserves policy across compaction, not abandoned branches. */
export function branchState(entries: readonly SessionEntry[]): { enabled: boolean } {
  let enabled = false;
  for (const entry of entries) {
    if (entry.type === "custom" && entry.customType === MODE_TYPE && record(entry.data) &&
        entry.data.version === 1 && typeof entry.data.enabled === "boolean") enabled = entry.data.enabled;
  }
  return { enabled };
}

/** Codex's Fast config label maps to priority on the wire; explicit standard
 * routing omits the field. See the pinned official serializer in README.md.
 */
const requestedTier = (enabled: boolean, model: Route) =>
  enabled ? "priority" : model.provider === "openai-codex" ? undefined : "default";

export default function fastMode(pi: ExtensionAPI): void {
  function status(ctx: ExtensionContext): string {
    const { enabled } = branchState(ctx.sessionManager.getBranch());
    const model = ctx.model;
    const eligibility = supportedRoute(model) ?
      `eligible selected route; request=${requestedTier(enabled, model) ?? "omitted (Codex standard request)"}` :
      "inactive (unsupported selected route); tier not enforced";
    return `Fast request policy ${enabled ? "on" : "off"}; ${eligibility}; response tier not tracked`;
  }
  const refresh = (ctx: ExtensionContext) => {
    if (ctx.hasUI) ctx.ui.setStatus(STATUS_KEY, status(ctx));
  };

  pi.registerFlag("fast", {
    description: "Request premium Fast tier at startup (including eligible warming calls)",
    type: "boolean",
    default: false,
  });
  pi.registerCommand("fast", {
    description: "Request policy for this branch: /fast on|off|status (premium when on)",
    getArgumentCompletions: prefix => ["on", "off", "status"].filter(value => value.startsWith(prefix))
      .map(value => ({ value, label: value })),
    handler: async (args, ctx) => {
      const action = args.trim().toLowerCase() || "status";
      const valid = ["on", "off", "status"].includes(action);
      if (valid && action !== "status") {
        pi.appendEntry(MODE_TYPE, { version: 1, enabled: action === "on" });
      }
      refresh(ctx);
      const text = valid ? status(ctx) + (action === "on" ?
        "; premium usage/pricing may apply to eligible conversation and auxiliary calls." : "") :
        "Usage: /fast on|off|status";
      if (ctx.hasUI) ctx.ui.notify(text, valid ? "info" : "warning");
      else console.error(text); // Never corrupt JSON/RPC stdout with status text.
    },
  });

  pi.on("session_start", (event, ctx) => {
    // Initial CLI startup also covers --continue/--resume/--session/--fork.
    // Do not reapply the launch override on /reload, /new or in-process /resume.
    const flag = pi.getFlag("fast");
    if (event.reason === "startup" && (flag === true || flag === "true") &&
        !branchState(ctx.sessionManager.getBranch()).enabled) {
      pi.appendEntry(MODE_TYPE, { version: 1, enabled: true });
    }
    refresh(ctx);
  });
  pi.on("session_tree", (_event, ctx) => refresh(ctx));
  pi.on("model_select", (_event, ctx) => refresh(ctx));
  pi.on("session_shutdown", (_event, ctx) => {
    if (ctx.hasUI) ctx.ui.setStatus(STATUS_KEY, undefined);
  });

  pi.on("before_provider_request", (event, ctx) => {
    const model = ctx.model;
    if (!supportedRoute(model) || !record(event.payload) || event.payload.model !== model.id) return;
    // Intentional policy for ALL eligible hooked calls, including cache warming.
    // No main-request snapshots, response observers, prices or outcome records.
    const payload = { ...event.payload };
    const tier = requestedTier(branchState(ctx.sessionManager.getBranch()).enabled, model);
    if (tier === undefined) delete payload.service_tier; // Clear inherited premium, not just our own value.
    else payload.service_tier = tier;
    return payload;
  });
}
