import { basename, join, resolve } from "node:path";
import { homedir } from "node:os";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const helper = fileURLToPath(new URL("./store.py", import.meta.url));

/** Observe complete, unpaginated SKILL.md reads; never alter tool results. */
export default function (pi: ExtensionAPI) {
  pi.on("tool_result", async (event, ctx) => {
    if (event.toolName !== "read" || event.isError) return;
    const { path, offset, limit } = event.input;
    if (typeof path !== "string" || basename(path) !== "SKILL.md") return;
    if ((offset != null && offset !== 1) || limit != null) return;
    const details = event.details as { truncation?: { truncated?: boolean } } | undefined;
    if (details?.truncation?.truncated) return;
    const text = event.content.filter((c) => c.type === "text").map((c) => c.text).join("\n");
    // Inspect the returned text, not a second read of a potentially changed file.
    const frontmatter = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/.exec(text)?.[1];
    const skill = frontmatter?.match(/^name:\s*["']?([a-z0-9]+(?:-[a-z0-9]+)*)["']?\s*$/m)?.[1];
    if (!skill || /\[.*(?:more lines|truncated).*\]/i.test(text)) return;
    const expanded = path.startsWith("~/") ? join(homedir(), path.slice(2)) : path;
    const eventData = {
      timestamp: new Date().toISOString(),
      sessionId: ctx.sessionManager.getSessionId(),
      toolCallId: event.toolCallId,
      project: ctx.cwd,
      skill,
      path: resolve(ctx.cwd, expanded),
    };
    try {
      const result = await pi.exec("uv", [
        "run", "--no-project", "--offline", "--script", helper, "record",
        "--db", join(homedir(), ".agents/var/tools/skill-activity/db"),
        "--event", JSON.stringify(eventData),
      ], { timeout: 5000 });
      if (result.code !== 0) throw new Error("Storage failed");
    } catch {
      // Best effort: do not break or change the agent's successful read.
      if (ctx.hasUI) ctx.ui.notify("skill-activity: record was not saved", "warning");
      else console.error("skill-activity: record was not saved");
    }
  });
}
