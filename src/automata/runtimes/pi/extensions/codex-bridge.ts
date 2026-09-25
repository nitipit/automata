import { spawn } from "node:child_process";
import { copyFile, mkdir, stat } from "node:fs/promises";
import { createInterface } from "node:readline";
import { dirname, join, relative, resolve } from "node:path";

import {
  withFileMutationQueue,
  type ExtensionAPI,
} from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const CLIENT_INFO = { name: "automata-codex-bridge", version: "0.1.0" };
const REQUEST_TIMEOUT_MS = 10_000;
const IMAGE_GENERATION_TIMEOUT_MS = 180_000;
const IMAGEGEN_DEVELOPER_INSTRUCTIONS = [
  "You are a bounded Codex image-generation worker.",
  "Use the native image generation tool for exactly one raster image.",
  "Do not use the CLI fallback, request an API key, browse, delegate, run shell commands, or edit project files.",
  "After the native image generation tool completes, stop and report the result.",
].join(" ");

type JsonRecord = Record<string, unknown>;
type AppServerNotificationHandler = (message: JsonRecord) => void;
type AppServerClosedHandler = (error: Error) => void;

type RateLimitWindow = {
  remainingPercent: number;
  resetsAt?: string;
  usedPercent: number;
  windowDurationMins?: number;
};

type RateLimit = {
  id: string;
  name?: string;
  primary?: RateLimitWindow;
  secondary?: RateLimitWindow;
};

type CodexAccountStatus = {
  account?: {
    planType?: string;
    type: string;
  };
  rateLimits: RateLimit[];
  requiresOpenaiAuth: boolean;
};

type CodexImageGeneration = {
  revisedPrompt?: string;
  savedPath: string;
};

type CodexImagegenDetails = {
  outputPath?: string;
  revisedPrompt?: string;
  status: "cancelled" | "completed";
};

type PendingRequest = {
  reject: (error: Error) => void;
  resolve: (result: unknown) => void;
  timer: ReturnType<typeof setTimeout>;
};

class CodexAppServerClient {
  private readonly child = spawn("codex", ["app-server", "--stdio"], {
    stdio: ["pipe", "pipe", "pipe"],
  });
  private readonly pending = new Map<number, PendingRequest>();
  private readonly closedHandlers = new Set<AppServerClosedHandler>();
  private readonly stderr: string[] = [];
  private readonly lineReader = createInterface({ input: this.child.stdout });
  private requestId = 0;
  private closed = false;
  private closedError: Error | undefined;

  constructor(
    private readonly signal?: AbortSignal,
    private readonly onNotification?: AppServerNotificationHandler,
  ) {
    this.lineReader.on("line", (line) => this.handleLine(line));
    this.child.stderr.on("data", (data: Buffer) => this.stderr.push(data.toString()));
    this.child.once("error", (error) => {
      this.fail(new Error(`Codex CLI unavailable: ${error.message}`));
    });
    this.child.once("exit", (code, exitSignal) => {
      if (!this.closed) {
        this.fail(
          new Error(
            `Codex app-server exited unexpectedly (${exitSignal ?? `code ${code ?? "unknown"}`}).${formatStderr(this.stderr)}`,
          ),
        );
      }
    });

    if (signal) {
      const abort = () => this.fail(new Error("Cancelled"));
      signal.addEventListener("abort", abort, { once: true });
      this.abortHandler = abort;
    }
  }

  private abortHandler?: () => void;

  onClosed(handler: AppServerClosedHandler): () => void {
    if (this.closed) {
      handler(this.closedError ?? new Error("Codex app-server closed."));
      return () => undefined;
    }

    this.closedHandlers.add(handler);
    return () => this.closedHandlers.delete(handler);
  }

  request(method: string, params?: unknown, timeoutMs = REQUEST_TIMEOUT_MS): Promise<unknown> {
    if (this.closed) {
      return Promise.reject(this.closedError ?? new Error("Codex app-server closed."));
    }
    if (this.signal?.aborted) {
      return Promise.reject(new Error("Cancelled"));
    }

    const id = ++this.requestId;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Timed out waiting for Codex app-server (${method}).`));
      }, timeoutMs);
      this.pending.set(id, { resolve, reject, timer });

      this.child.stdin.write(
        `${JSON.stringify({ jsonrpc: "2.0", id, method, ...(params === undefined ? {} : { params }) })}\n`,
        (error) => {
          if (!error) return;
          const pendingRequest = this.pending.get(id);
          if (!pendingRequest) return;
          this.pending.delete(id);
          clearTimeout(pendingRequest.timer);
          reject(error);
        },
      );
    });
  }

  close(): void {
    if (!this.closed) {
      this.fail(new Error("Codex app-server closed."));
    }
    this.abortHandler && this.signal?.removeEventListener("abort", this.abortHandler);
    this.lineReader.close();
    this.child.kill();
  }

  private handleLine(line: string): void {
    if (!line.trim()) return;

    let message: JsonRecord;
    try {
      message = JSON.parse(line) as JsonRecord;
    } catch {
      return;
    }

    const id = message.id;
    if (typeof id === "number") {
      const pendingRequest = this.pending.get(id);
      if (!pendingRequest) return;

      this.pending.delete(id);
      clearTimeout(pendingRequest.timer);
      if (message.error) {
        pendingRequest.reject(new Error(errorMessage(message.error)));
      } else {
        pendingRequest.resolve(message.result);
      }
      return;
    }

    this.onNotification?.(message);
  }

  private fail(error: Error): void {
    if (this.closed) return;
    this.closed = true;
    this.closedError = error;

    for (const pendingRequest of this.pending.values()) {
      clearTimeout(pendingRequest.timer);
      pendingRequest.reject(error);
    }
    this.pending.clear();

    for (const handler of this.closedHandlers) handler(error);
    this.closedHandlers.clear();
  }
}

export default function (pi: ExtensionAPI) {
  let explicitImagegenAuthorization = false;

  pi.on("input", (event) => {
    if (event.source !== "extension") {
      explicitImagegenAuthorization = hasExplicitImagegenIntent(event.text);
    }
    return { action: "continue" };
  });

  pi.registerCommand("codex-status", {
    description: "Show the current Codex account and rate-limit status.",
    handler: async (_args, ctx) => {
      try {
        const status = await readCodexAccountStatus();
        ctx.ui.notify(formatStatus(status), "info");
      } catch (error) {
        ctx.ui.notify(`Codex status unavailable: ${errorMessage(error)}`, "error");
      }
    },
  });

  pi.registerTool({
    name: "codex_account_status",
    label: "Codex Account Status",
    description:
      "Read the signed-in Codex account type, plan, current rate-limit usage, and reset times.",
    promptSnippet: "Read current Codex account status and remaining quota",
    promptGuidelines: [
      "Use codex_account_status when Codex account status or remaining quota would help; avoid repeated checks during the same task.",
    ],
    parameters: Type.Object({}),
    async execute(_toolCallId, _params, signal) {
      const status = await readCodexAccountStatus(signal);

      return {
        content: [{ type: "text", text: formatStatus(status) }],
        details: status,
      };
    },
  });

  pi.registerTool({
    name: "codex_imagegen",
    label: "Codex Imagegen",
    description:
      "Generate exactly one new raster image with Codex's native image-generation capability and copy it into the current workspace.",
    promptSnippet: "Generate one new raster image with native Codex imagegen",
    promptGuidelines: [
      "Use codex_imagegen for new raster images; do not use it for deterministic SVG, HTML/CSS, canvas, or existing vector assets.",
      "codex_imagegen treats a clear current-turn user request to generate an image as authorization for one call; ambiguous or agent-inferred calls require confirmation.",
      "codex_imagegen currently generates new images only and does not edit local image files.",
    ],
    parameters: Type.Object({
      prompt: Type.String({
        description: "A complete image brief including subject, intended use, composition, style, and constraints.",
        minLength: 1,
      }),
      output_path: Type.Optional(
        Type.String({
          description: "Optional workspace-relative destination; defaults to output/imagegen/generated-<timestamp>.png.",
        }),
      ),
    }),
    async execute(_toolCallId, params, signal, onUpdate, ctx) {
      if (signal?.aborted) throw new Error("Cancelled");

      const outputPath = resolveImageOutputPath(ctx.cwd, params.output_path);
      if (await pathExists(outputPath)) {
        throw new Error(`Refusing to overwrite an existing image: ${outputPath}`);
      }

      const explicitlyAuthorized = explicitImagegenAuthorization;
      explicitImagegenAuthorization = false;

      if (!explicitlyAuthorized) {
        if (!ctx.hasUI) {
          throw new Error("codex_imagegen requires interactive confirmation before consuming Codex quota.");
        }

        const confirmationText = `This will use native Codex image generation and may consume quota.\n\nPrompt: ${params.prompt}\n\nDestination: ${relative(ctx.cwd, outputPath)}`;
        const confirmed = signal
          ? await ctx.ui.confirm("Generate image with Codex?", confirmationText, { signal })
          : await ctx.ui.confirm("Generate image with Codex?", confirmationText);
        if (!confirmed) {
          return {
            content: [{ type: "text", text: "Codex image generation cancelled; no image was generated." }],
            details: { status: "cancelled" } satisfies CodexImagegenDetails,
          };
        }
      }

      onUpdate?.({
        content: [{ type: "text", text: "Starting native Codex image generation..." }],
        details: { status: "generating" },
      });
      const generated = await generateCodexImage(params.prompt, ctx.cwd, signal, onUpdate);
      const savedPath = await copyGeneratedImage(generated.savedPath, outputPath);
      const workspacePath = relative(ctx.cwd, savedPath) || savedPath;

      return {
        content: [
          {
            type: "text",
            text: `Generated one image with native Codex imagegen and saved it to ${workspacePath}.`,
          },
        ],
        details: {
          outputPath: workspacePath,
          revisedPrompt: generated.revisedPrompt,
          status: "completed",
        } satisfies CodexImagegenDetails,
      };
    },
  });
}

function hasExplicitImagegenIntent(text: string): boolean {
  const normalized = text.toLowerCase().replace(/\s+/g, " ").trim();
  if (!normalized) return false;

  const asksForExplanation = /^(how|why|what is|what does|should i|can i)\b/.test(normalized)
    || /\b(explain|discuss|plan|consider|whether)\b/.test(normalized);
  if (asksForExplanation) return false;

  const deniesGeneration = /\b(don't|do not|never|not yet|without generating|no image)\b/.test(normalized);
  if (deniesGeneration) return false;

  const hasImageTarget = /\b(image|picture|illustration|photo|artwork|visual|graphic|bitmap|sprite|texture)\b/.test(normalized);
  const hasGenerationAction = /\b(generate|create|make|produce|draw|render|design|paint|illustrate)\b/.test(normalized);
  const namesImagegen = /\b(imagegen|image generation|image_gen)\b/.test(normalized);
  const invokesImagegen = /\b(use|call|run|invoke)\b/.test(normalized) && namesImagegen;

  return (hasGenerationAction && hasImageTarget) || invokesImagegen;
}

async function readCodexAccountStatus(signal?: AbortSignal): Promise<CodexAccountStatus> {
  const client = new CodexAppServerClient(signal);

  try {
    await client.request("initialize", { clientInfo: CLIENT_INFO });
    const account = asRecord(await client.request("account/read", { refreshToken: false }));
    const limits = asRecord(await client.request("account/rateLimits/read"));
    return normalizeStatus(account, limits);
  } finally {
    client.close();
  }
}

async function generateCodexImage(
  prompt: string,
  cwd: string,
  signal: AbortSignal | undefined,
  onUpdate: ((update: { content: Array<{ type: "text"; text: string }>; details?: unknown }) => void) | undefined,
): Promise<CodexImageGeneration> {
  let generated: CodexImageGeneration | undefined;
  let resolveTurn!: (result: CodexImageGeneration) => void;
  let rejectTurn!: (error: Error) => void;
  const turnFinished = new Promise<CodexImageGeneration>((resolve, reject) => {
    resolveTurn = resolve;
    rejectTurn = reject;
  });
  turnFinished.catch(() => undefined);

  const client = new CodexAppServerClient(signal, (message) => {
    const method = stringValue(message.method);
    const params = asRecord(message.params);

    if (method === "error") {
      rejectTurn(new Error(errorMessage(params?.error ?? params?.message ?? message)));
      return;
    }

    const item = method === "item/completed" || method === "rawResponseItem/completed"
      ? extractImageGeneration(params?.item)
      : method === "turn/completed"
        ? extractImageGenerationFromItems(params?.turn)
        : undefined;
    if (item) {
      generated = item;
      onUpdate?.({
        content: [{ type: "text", text: "Native Codex image generation completed; copying the saved image into the workspace..." }],
        details: { status: "generated" },
      });
    }

    if (method !== "turn/completed") return;

    const turn = asRecord(params?.turn);
    const status = stringValue(turn?.status);
    if (status !== "completed") {
      const turnError = asRecord(turn?.error);
      rejectTurn(new Error(stringValue(turnError?.message) ?? `Codex image generation ${status ?? "failed"}.`));
      return;
    }
    if (!generated) {
      rejectTurn(new Error("Codex completed without returning a saved image path."));
      return;
    }
    resolveTurn(generated);
  });
  const removeClosedHandler = client.onClosed((error) => rejectTurn(error));
  let timeout: ReturnType<typeof setTimeout> | undefined;

  try {
    const initialized = asRecord(await client.request("initialize", { clientInfo: CLIENT_INFO }));
    const capabilities = asRecord(
      await client.request("modelProvider/capabilities/read", { modelProvider: "openai" }),
    );
    if (capabilities?.imageGeneration !== true) {
      throw new Error("This Codex runtime does not expose native image generation.");
    }

    const codexHome = stringValue(initialized?.codexHome);
    const imagegenSkillPath = codexHome
      ? join(codexHome, "skills", ".system", "imagegen", "SKILL.md")
      : undefined;
    const input: Array<JsonRecord> = [
      {
        type: "text",
        text: [
          "Generate exactly one new raster image with the native Codex image-generation tool.",
          "Do not edit existing files or use a fallback CLI.",
          `Image brief:\n${prompt}`,
        ].join("\n\n"),
        text_elements: [],
      },
    ];
    if (imagegenSkillPath) {
      input.push({ type: "skill", name: "imagegen", path: imagegenSkillPath });
    }

    const threadResponse = asRecord(
      await client.request("thread/start", {
        cwd,
        developerInstructions: IMAGEGEN_DEVELOPER_INSTRUCTIONS,
        ephemeral: true,
        approvalPolicy: "never",
        sandbox: "read-only",
      }),
    );
    const thread = asRecord(threadResponse?.thread);
    const threadId = stringValue(thread?.id);
    if (!threadId) throw new Error("Codex app-server did not return a thread ID.");

    await client.request("turn/start", {
      threadId,
      input,
    });
    timeout = setTimeout(() => rejectTurn(new Error("Timed out waiting for native Codex image generation.")), IMAGE_GENERATION_TIMEOUT_MS);
    return await turnFinished;
  } finally {
    if (timeout) clearTimeout(timeout);
    removeClosedHandler();
    client.close();
  }
}

function extractImageGeneration(value: unknown): CodexImageGeneration | undefined {
  const item = asRecord(value);
  if (!item || item.type !== "imageGeneration") return undefined;

  const savedPath = stringValue(item.savedPath);
  if (!savedPath) return undefined;

  return {
    revisedPrompt: stringValue(item.revisedPrompt),
    savedPath,
  };
}

function extractImageGenerationFromItems(value: unknown): CodexImageGeneration | undefined {
  const record = asRecord(value);
  const items = record?.items;
  if (!Array.isArray(items)) return undefined;

  for (const item of items) {
    const generated = extractImageGeneration(item);
    if (generated) return generated;
  }
  return undefined;
}

function resolveImageOutputPath(cwd: string, requestedPath?: string): string {
  const requested = requestedPath?.trim().replace(/^@/, "");
  const filename = requested || join(
    "output",
    "imagegen",
    `generated-${new Date().toISOString().replace(/[.:]/g, "-")}.png`,
  );
  const outputPath = resolve(cwd, filename);
  const relativePath = relative(cwd, outputPath);
  if (!relativePath || relativePath === ".." || relativePath.startsWith("../") || relativePath.startsWith("..\\")) {
    throw new Error("codex_imagegen output_path must stay inside the current workspace.");
  }
  return outputPath;
}

async function copyGeneratedImage(sourcePath: string, outputPath: string): Promise<string> {
  const source = resolve(sourcePath);
  const sourceStats = await stat(source);
  if (!sourceStats.isFile()) throw new Error(`Codex returned a non-file image path: ${source}`);

  await withFileMutationQueue(outputPath, async () => {
    if (await pathExists(outputPath)) {
      throw new Error(`Refusing to overwrite an existing image: ${outputPath}`);
    }
    await mkdir(dirname(outputPath), { recursive: true });
    await copyFile(source, outputPath);
  });
  return outputPath;
}

async function pathExists(path: string): Promise<boolean> {
  try {
    await stat(path);
    return true;
  } catch (error) {
    if (asRecord(error)?.code === "ENOENT") return false;
    throw error;
  }
}

function normalizeStatus(accountResponse: JsonRecord | undefined, limitsResponse: JsonRecord | undefined): CodexAccountStatus {
  const account = asRecord(accountResponse?.account);
  const limitsById = asRecord(limitsResponse?.rateLimitsByLimitId);
  const rateLimits = limitsById
    ? Object.entries(limitsById).map(([id, value]) => normalizeRateLimit(id, asRecord(value)))
    : [normalizeRateLimit(stringValue(asRecord(limitsResponse?.rateLimits)?.limitId) ?? "default", asRecord(limitsResponse?.rateLimits))];

  return {
    account: account && typeof account.type === "string"
      ? { type: account.type, planType: stringValue(account.planType) }
      : undefined,
    rateLimits,
    requiresOpenaiAuth: Boolean(accountResponse?.requiresOpenaiAuth),
  };
}

function normalizeRateLimit(id: string, snapshot: JsonRecord | undefined): RateLimit {
  return {
    id,
    name: stringValue(snapshot?.limitName),
    primary: normalizeWindow(asRecord(snapshot?.primary)),
    secondary: normalizeWindow(asRecord(snapshot?.secondary)),
  };
}

function normalizeWindow(window: JsonRecord | undefined): RateLimitWindow | undefined {
  const usedPercent = numberValue(window?.usedPercent);
  if (usedPercent === undefined) {
    return undefined;
  }

  const resetsAt = numberValue(window?.resetsAt);
  return {
    usedPercent,
    remainingPercent: Math.max(0, Math.min(100, 100 - usedPercent)),
    resetsAt: resetsAt === undefined ? undefined : new Date(resetsAt * 1_000).toISOString(),
    windowDurationMins: numberValue(window?.windowDurationMins),
  };
}

function formatStatus(status: CodexAccountStatus): string {
  const account = status.account
    ? `Codex account: ${status.account.type}${status.account.planType ? ` (${status.account.planType})` : ""}.`
    : "Codex account: not signed in.";
  const limits = status.rateLimits.map(formatRateLimit).join("\n");

  return limits ? `${account}\n${limits}` : `${account}\nNo rate-limit data is available.`;
}

function formatRateLimit(limit: RateLimit): string {
  const label = limit.name || limit.id;
  const windows = [
    formatWindow("primary", limit.primary),
    formatWindow("secondary", limit.secondary),
  ].filter((window): window is string => Boolean(window));

  return windows.length > 0 ? `${label}: ${windows.join("; ")}` : `${label}: no usage window reported.`;
}

function formatWindow(name: string, window: RateLimitWindow | undefined): string | undefined {
  if (!window) {
    return undefined;
  }
  const reset = window.resetsAt ? `, resets ${window.resetsAt}` : "";
  return `${name} ${window.remainingPercent}% remaining (${window.usedPercent}% used${reset})`;
}

function asRecord(value: unknown): JsonRecord | undefined {
  return value && typeof value === "object" && !Array.isArray(value) ? value as JsonRecord : undefined;
}

function numberValue(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  const record = asRecord(error);
  return stringValue(record?.message) ?? "Unknown error";
}

function formatStderr(stderr: string[]): string {
  const output = stderr.join("").trim();
  return output ? ` ${output.slice(0, 500)}` : "";
}
