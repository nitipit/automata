import { randomUUID } from "node:crypto";
import { access, mkdtemp, readFile, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { isAbsolute, join, resolve } from "node:path";
import { isDeepStrictEqual } from "node:util";

import {
  SessionManager,
  type ExtensionAPI,
  type ExtensionContext,
  type SessionInfo,
} from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const LISTING_LIMIT = 100;
const RECEIPT_TTL_MS = 5 * 60 * 1000;
const TRASH_TIMEOUT_MS = 10_000;

type DirectoryStatus = "exists" | "missing" | "unknown";
type Scope = "directory" | "global";

type SessionSummary = {
  id: string;
  cwd: string;
  directoryStatus: DirectoryStatus;
  selectable: boolean;
  name?: string;
  created: string;
  modified: string;
  messageCount: number;
  current: boolean;
};

type ReceiptSession = {
  cwd: string;
  directoryStatus: DirectoryStatus;
  path: string;
  mtimeMs: number;
  size: number;
  device: number;
  inode: number;
};

type ListingReceipt = {
  id: string;
  scope: Scope;
  cwd?: string;
  runtimeCwd: string;
  sessionDir?: string;
  expiresAt: number;
  sessions: Map<string, ReceiptSession>;
};

type ListingSnapshot = {
  scope: Scope;
  cwd?: string;
  runtimeCwd: string;
  sessionDir?: string;
  expiresAt: number;
  limit: number;
  sessions: Array<{ session: SessionInfo; directoryStatus: DirectoryStatus; identity?: ReceiptSession }>;
  duplicateIds: Set<string>;
};

export default function (pi: ExtensionAPI) {
  let nextPage: { token: string; offset: number; snapshot: ListingSnapshot } | undefined;
  let latestReceipt: ListingReceipt | undefined;
  let latestCopyReceipt: ListingReceipt | undefined;

  pi.registerTool({
    name: "pi_session_list",
    label: "List Pi Sessions",
    description:
      "List Pi session metadata for the runtime CWD (default), an exact cwd, or explicit global scope. " +
      "Global/other-directory searches use the default store, not custom stores. " +
      "Returns at most 100 entries per page, directory status, and separate copy/trash receipts. " +
      "Use nextCursor alone for the next page; receipts select only the latest page. " +
      "No session-file paths or conversation content. Missing directories are review candidates, not deletion permission.",
    promptSnippet: "Discover current, exact-directory or global Pi sessions with bounded pages and operation receipts",
    promptGuidelines: [
      "Use pi_session_list instead of scanning Pi session files. Omit scope/cwd for runtime CWD; obtain authority before exact-directory or global discovery. Missing or inaccessible CWDs do not authorize deletion.",
      "Treat recorded delegated-agent session IDs as primary identity; use pi_session_list for discovery or recovery.",
    ],
    parameters: Type.Object({
      cwd: Type.Optional(Type.String({
        minLength: 1,
        description: "Exact directory, relative to runtime CWD if not absolute. Cannot combine with global scope.",
      })),
      scope: Type.Optional(Type.Union([Type.Literal("directory"), Type.Literal("global")])),
      directoryStatus: Type.Optional(Type.Union([
        Type.Literal("exists"), Type.Literal("missing"), Type.Literal("unknown"),
      ])),
      limit: Type.Optional(Type.Integer({ minimum: 1, maximum: LISTING_LIMIT })),
      cursor: Type.Optional(Type.String({ minLength: 1, description: "nextCursor from the last page; supply alone." })),
    }, { additionalProperties: false }),
    async execute(_toolCallId, params, signal, _onUpdate, ctx) {
      signal?.throwIfAborted();
      if (params.cwd !== undefined &&
          (typeof params.cwd !== "string" || !params.cwd.trim() || params.cwd.includes("\u0000"))) {
        throw new Error("cwd must be a non-empty directory path.");
      }
      let snapshot: ListingSnapshot;
      let cursorPage: typeof nextPage;
      let offset = 0;
      if (params.cursor !== undefined) {
        if (Object.keys(params).some(key => key !== "cursor")) {
          throw new Error("Supply cursor alone; start a new listing to change filters.");
        }
        if (!nextPage || params.cursor !== nextPage.token ||
            Date.now() > nextPage.snapshot.expiresAt ||
            normalizePath(ctx.cwd) !== nextPage.snapshot.runtimeCwd) {
          throw new Error("Unknown, expired or superseded cursor; start a new listing.");
        }
        cursorPage = nextPage;
        snapshot = nextPage.snapshot;
        offset = nextPage.offset;
      } else {
        if (params.scope !== undefined && !["directory", "global"].includes(params.scope)) {
          throw new Error("scope must be directory or global.");
        }
        if (params.scope === "global" && params.cwd !== undefined) {
          throw new Error("Global scope cannot be combined with cwd.");
        }
        if (params.directoryStatus !== undefined &&
            !["exists", "missing", "unknown"].includes(params.directoryStatus)) {
          throw new Error("Invalid directoryStatus filter.");
        }
        const limit = params.limit ?? LISTING_LIMIT;
        if (!Number.isInteger(limit) || limit < 1 || limit > LISTING_LIMIT) {
          throw new Error("limit must be an integer between 1 and 100.");
        }
        const scope: Scope = params.scope ?? "directory";
        const cwd = scope === "global" ? undefined : resolve(ctx.cwd, params.cwd ?? ".");
        const sessionDir = cwd === normalizePath(ctx.cwd) ? ctx.sessionManager.getSessionDir() : undefined;
        const loaded = scope === "global"
          ? await SessionManager.listAll()
          : await SessionManager.list(cwd!, sessionDir);
        const candidates = loaded.filter(session => typeof session.cwd === "string" &&
          isAbsolute(session.cwd) && (cwd === undefined || normalizePath(session.cwd) === cwd));
        const counts = new Map<string, number>();
        for (const session of candidates) counts.set(session.id, (counts.get(session.id) ?? 0) + 1);
        const states = new Map<string, DirectoryStatus>();
        const sessions: ListingSnapshot["sessions"] = [];
        for (const session of candidates) {
          signal?.throwIfAborted();
          const key = normalizePath(session.cwd);
          if (!states.has(key)) states.set(key, await directoryStatus(key));
          const status = states.get(key)!;
          if (params.directoryStatus === undefined || status === params.directoryStatus) {
            const identity = await identifySession(session);
            sessions.push({ session, directoryStatus: status,
              identity: identity ? { ...identity, directoryStatus: status } : undefined,
            });
          }
        }
        sessions.sort((a, b) => b.session.modified.getTime() - a.session.modified.getTime() ||
          a.session.id.localeCompare(b.session.id) || a.session.path.localeCompare(b.session.path));
        snapshot = { scope, cwd, sessionDir, runtimeCwd: normalizePath(ctx.cwd), limit,
          expiresAt: Date.now() + RECEIPT_TTL_MS, sessions,
          duplicateIds: new Set([...counts].filter(([, count]) => count > 1).map(([id]) => id)),
        };
      }
      const page = snapshot.sessions.slice(offset, offset + snapshot.limit);
      const snapshotIdentities = new Map(page.map(item => [item.session, item.identity]));
      const listedSessions = (await identifySessions(page.map(item => item.session))).filter(item => {
        const expected = snapshotIdentities.get(item.session);
        return expected && sameIdentity(expected, item.identity);
      });
      const pageStates = new Map(page.map(item => [item.session.path, item.directoryStatus]));
      const currentSessionId = ctx.sessionManager.getSessionId();
      const currentSessionFile = ctx.sessionManager.getSessionFile();
      const summaries = listedSessions.map(({ session }) => summarizeSession(
        session, currentSessionId, currentSessionFile, pageStates.get(session.path)!,
        !snapshot.duplicateIds.has(session.id),
      ));
      signal?.throwIfAborted();
      if ((params.cursor !== undefined && nextPage !== cursorPage) ||
          Date.now() > snapshot.expiresAt || normalizePath(ctx.cwd) !== snapshot.runtimeCwd) {
        throw new Error("Listing snapshot expired, changed runtime CWD or was superseded; list again.");
      }
      const expiresAt = snapshot.expiresAt;
      latestCopyReceipt = {
        id: randomUUID(), scope: snapshot.scope, cwd: snapshot.cwd,
        runtimeCwd: snapshot.runtimeCwd, sessionDir: snapshot.sessionDir, expiresAt,
        sessions: new Map(listedSessions.filter(({ session }) => !snapshot.duplicateIds.has(session.id))
          .map(({ session, identity }) => [session.id, {
            ...identity, directoryStatus: pageStates.get(session.path)!,
          }])),
      };
      latestReceipt = { ...latestCopyReceipt, id: randomUUID() };
      const remaining = snapshot.sessions.length - offset - page.length;
      nextPage = remaining > 0 ? { token: randomUUID(), offset: offset + page.length, snapshot } : undefined;
      const currentCwd = snapshot.scope === "directory" && snapshot.cwd === normalizePath(ctx.cwd);
      const result = {
        scope: snapshot.scope, ...(snapshot.cwd ? { cwd: snapshot.cwd } : {}),
        copyReceipt: latestCopyReceipt.id, copyReceiptExpiresAt: new Date(expiresAt).toISOString(),
        receipt: latestReceipt.id, receiptExpiresAt: new Date(expiresAt).toISOString(),
        storage: currentCwd ? "runtime" : "default",
        ...(currentCwd ? {} : { limitation: "Custom session stores are not searched outside the runtime CWD scope." }),
        sessions: summaries, totalCount: snapshot.sessions.length,
        omittedCount: remaining + page.length - listedSessions.length,
        unavailableCount: page.length - listedSessions.length,
        ...(nextPage ? { nextCursor: nextPage.token } : {}),
        warning: "Pages are a snapshot, not proof of inactivity. Duplicate IDs are non-selectable; narrow to an exact CWD. Receipts cover only this page and do not grant user authorization.",
      };

      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        details: result,
      };
    },
  });

  pi.registerTool({
    name: "pi_session_copy",
    label: "Copy Pi Sessions",
    description:
      "Copy selected listed sessions to an existing destination working directory using Pi's " +
      "default session store. Requires a fresh copyReceipt from pi_session_list. Creates new IDs " +
      "and source provenance; leaves originals and historical message paths unchanged. " +
      "No project files are copied. Rejects the active session. Partial failures may leave a " +
      "destination copy; never automatically retry or delete it.",
    promptSnippet: "Copy explicitly selected sessions to another directory without changing originals",
    promptGuidelines: [
      "Obtain authorization for the selected sessions and destination; confirm source sessions are inactive before copying. The tool cannot detect other active Pi processes.",
      "Copy uses default destination session storage, not target project configuration. Report custom-store limitations and stale historical paths.",
    ],
    parameters: Type.Object({
      sessionIds: Type.Array(Type.String({ minLength: 1 }), {
        minItems: 1, maxItems: LISTING_LIMIT, uniqueItems: true,
        description: "Exact full session IDs from one listing.",
      }),
      copyReceipt: Type.String({ minLength: 1 }),
      targetCwd: Type.String({
        minLength: 1,
        description: "Existing destination directory; relative paths resolve against runtime CWD.",
      }),
    }, { additionalProperties: false }),
    async execute(_toolCallId, params, signal, _onUpdate, ctx) {
      signal?.throwIfAborted();
      const ids = params.sessionIds;
      if (!Array.isArray(ids) || ids.length === 0 || ids.length > LISTING_LIMIT ||
          ids.some(id => typeof id !== "string" || !id.length) || new Set(ids).size !== ids.length) {
        throw new Error("Supply 1–100 unique full session IDs.");
      }
      if (typeof params.targetCwd !== "string" || !params.targetCwd.trim() ||
          params.targetCwd.includes("\u0000")) {
        throw new Error("targetCwd must be a non-empty directory path.");
      }
      const targetCwd = resolve(ctx.cwd, params.targetCwd);
      if (!(await stat(targetCwd)).isDirectory()) {
        throw new Error("targetCwd must be an existing directory.");
      }
      const receipt = latestCopyReceipt;
      for (const id of ids) {
        const source = await resolveCopyCandidate(ctx, receipt, params.copyReceipt, id);
        if (normalizePath(source.cwd) === targetCwd) throw new Error("Choose a different destination directory.");
        signal?.throwIfAborted();
      }
      if (latestCopyReceipt !== receipt) {
        throw new Error("Copy receipt was consumed or superseded; list again.");
      }
      latestCopyReceipt = undefined;
      const results: Array<{
        sourceSessionId: string;
        sourceCwd?: string;
        status: "copied" | "failed" | "not_attempted";
        sessionId?: string;
        error?: string;
        destinationMayContainCopy?: boolean;
      }> = [];
      for (const id of ids) {
        let newId: string | undefined;
        try {
          signal?.throwIfAborted();
          const source = await resolveCopyCandidate(ctx, receipt, params.copyReceipt, id);
          signal?.throwIfAborted();
          newId = randomUUID();
          const copy = await forkSnapshot(source, targetCwd, newId);
          if (copy.getSessionId() !== newId || normalizePath(copy.getCwd()) !== targetCwd ||
              !copy.getSessionFile() || !(await pathExists(copy.getSessionFile()!))) {
            throw new Error("Destination identity could not be verified.");
          }
          // A concurrent writer may have changed the source while forkFrom read it.
          await resolveCopyCandidate(ctx, receipt, params.copyReceipt, id);
          results.push({ sourceSessionId: id, sourceCwd: source.cwd, sessionId: newId, status: "copied" });
        } catch (error) {
          results.push({
            sourceSessionId: id, status: "failed",
            ...(newId ? { sessionId: newId, destinationMayContainCopy: true } : {}),
            error: String(error),
          });
          for (const remaining of ids.slice(results.length)) {
            results.push({ sourceSessionId: remaining, status: "not_attempted" });
          }
          break;
        }
      }
      const failed = results.some(result => result.status !== "copied");
      const result = {
        status: failed ? "incomplete" : "copied",
        scope: receipt!.scope, sourceCwd: receipt!.cwd, targetCwd, storage: "default", results,
        warning: "Historical paths are unchanged. Custom destination session stores are not used. Originals are retained.",
      };
      return {
        ...(failed ? { isError: true } : {}),
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }], details: result,
      };
    },
  });

  pi.registerTool({
    name: "pi_session_trash",
    label: "Trash Pi Sessions",
    description:
      "Move explicitly selected Pi sessions from a current, exact-directory or global listing to the " +
      "operating-system trash. Supply sessionIds (or legacy sessionId) and one fresh pi_session_list receipt. " +
      "Validates all targets first; moves sequentially, stopping and reporting partial results on failure. " +
      "The agent establishes user authorization and inactivity from context; no tool-level confirmation dialog. " +
      "Never falls back to permanent deletion.",
    promptSnippet: "Move explicitly authorized listed sessions to recoverable trash; receipt binds source scope",
    promptGuidelines: [
      "Use pi_session_trash only after pi_session_list, within the user's authorized scope, and when ownership and inactivity are sufficiently established; the tool does not detect sessions open in other processes.",
      "For pi_session_trash, use context to decide whether clarification or permission is needed. A clear removal request or prior scoped authorization needs no repeated confirmation; otherwise present candidates, optionally as stable numbered choices mapped to full session IDs.",
      "pi_session_trash must never be replaced with rm or direct session-file deletion.",
    ],
    parameters: Type.Object(
      {
        sessionId: Type.Optional(Type.String({
          minLength: 1,
          description: "Legacy single full session ID; supply exactly one of sessionId or sessionIds.",
        })),
        sessionIds: Type.Optional(Type.Array(Type.String({ minLength: 1 }), {
          minItems: 1,
          maxItems: LISTING_LIMIT,
          uniqueItems: true,
          description: "Exact full session IDs from one listing; supply instead of sessionId.",
        })),
        receipt: Type.String({
          minLength: 1,
          description: "Fresh receipt returned by pi_session_list in this runtime.",
        }),
      },
      { additionalProperties: false },
    ),
    async execute(_toolCallId, params, signal, _onUpdate, ctx) {
      signal?.throwIfAborted();
      if ((params.sessionId === undefined) === (params.sessionIds === undefined)) {
        throw new Error("Supply exactly one of sessionId or sessionIds.");
      }
      const ids = params.sessionIds ?? [params.sessionId!];
      if (!Array.isArray(ids) || ids.length === 0 || ids.length > LISTING_LIMIT ||
          ids.some((id) => typeof id !== "string" || id.length === 0) ||
          new Set(ids).size !== ids.length) {
        throw new Error("Supply 1–100 unique full session IDs.");
      }
      const receipt = latestReceipt;
      // Preflight every target before any side effect, then claim this receipt.
      for (const sessionId of ids) {
        await resolveReceiptCandidate(ctx, receipt, { sessionId, receipt: params.receipt });
        signal?.throwIfAborted();
      }
      if (latestReceipt !== receipt) {
        throw new Error("Listing receipt was consumed or superseded; run pi_session_list again.");
      }
      latestReceipt = undefined;
      const results: Array<{
        sessionId: string;
        status: "trashed" | "failed" | "not_attempted";
        name?: string;
        cwd?: string;
        method?: "trash" | "gio trash";
        error?: string;
      }> = [];
      for (const sessionId of ids) {
        try {
          signal?.throwIfAborted();
          // Recheck after earlier moves: another process may have changed this target.
          const candidate = await resolveReceiptCandidate(ctx, receipt, {
            sessionId, receipt: params.receipt,
          });
          signal?.throwIfAborted();
          const method = await moveToRecoverableTrash(pi, normalizePath(candidate.path), signal);
          if (await pathExists(candidate.path)) {
            throw new Error("Trash command reported success but the session file is still present.");
          }
          results.push({ sessionId, status: "trashed", cwd: candidate.cwd, name: candidate.name, method });
        } catch (error) {
          if (params.sessionIds === undefined) throw error;
          results.push({ sessionId, status: "failed", error: String(error) });
          for (const remaining of ids.slice(results.length)) {
            results.push({ sessionId: remaining, status: "not_attempted" });
          }
          break;
        }
      }
      const failed = results.some((result) => result.status !== "trashed");
      const result = params.sessionIds === undefined
        ? { ...results[0], scope: receipt!.scope }
        : { status: failed ? "incomplete" : "trashed", scope: receipt!.scope, cwd: receipt!.cwd, results };
      return {
        ...(failed ? { isError: true } : {}),
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        details: result,
      };
    },
  });
}

function summarizeSession(
  session: SessionInfo,
  currentSessionId: string,
  currentSessionFile: string | undefined,
  status: DirectoryStatus,
  selectable: boolean,
): SessionSummary {
  const current = session.id === currentSessionId ||
    (currentSessionFile !== undefined &&
      normalizePath(session.path) === normalizePath(currentSessionFile));
  return {
    id: session.id,
    cwd: normalizePath(session.cwd),
    directoryStatus: status,
    selectable: selectable && !current,
    ...(session.name ? { name: session.name } : {}),
    created: session.created.toISOString(),
    modified: session.modified.toISOString(),
    messageCount: session.messageCount,
    current,
  };
}

async function resolveReceiptCandidate(
  ctx: ExtensionContext,
  receipt: ListingReceipt | undefined,
  params: { sessionId: string; receipt: string },
): Promise<SessionInfo> {
  return resolveCandidate(ctx, receipt, params.receipt, params.sessionId, "trash");
}

async function forkSnapshot(source: SessionInfo, targetCwd: string, id: string) {
  // Pi's loader repairs missing final newlines. Never hand it the original file.
  const content = await readFile(source.path, "utf8");
  const entries = parseCopyEntries(content);
  const header = entries[0];
  if (header?.type !== "session" || header.id !== source.id ||
      typeof header.cwd !== "string" || normalizePath(header.cwd) !== normalizePath(source.cwd) ||
      entries.slice(1).some(entry => entry.type === "session")) {
    throw new Error("Source session header does not match the listing.");
  }
  const staging = await mkdtemp(join(tmpdir(), "automata-session-copy-"));
  try {
    const snapshot = join(staging, "snapshot.jsonl");
    await writeFile(snapshot, content.endsWith("\n") ? content : `${content}\n`, { mode: 0o600 });
    const copy = SessionManager.forkFrom(snapshot, targetCwd, undefined, { id });
    const output = copy.getSessionFile();
    if (!output) throw new Error("Fork did not produce a session file.");
    const copied = parseCopyEntries(await readFile(output, "utf8"));
    if (copied[0]?.id !== id || copied[0]?.cwd !== targetCwd ||
        !isDeepStrictEqual(copied.slice(1), entries.slice(1))) {
      throw new Error("Copied session identity or history differs from the source snapshot.");
    }
    // Only the new header is adjusted; conversation entries keep their original paths.
    copied[0].parentSession = source.path;
    await writeFile(output, copied.map(entry => JSON.stringify(entry)).join("\n") + "\n");
    return copy;
  } finally {
    // Private staging only, never an original or destination session store.
    await rm(staging, { recursive: true, force: true });
  }
}

function parseCopyEntries(content: string): Array<Record<string, unknown>> {
  return content.split("\n").filter(line => line.trim()).map((line, index) => {
    try {
      const entry = JSON.parse(line);
      if (!entry || typeof entry !== "object" || Array.isArray(entry) ||
          typeof entry.type !== "string") throw new Error("Invalid entry");
      return entry;
    } catch {
      // Do not leak malformed conversation content through parser diagnostics.
      throw new Error(`Malformed session entry ${index + 1}; copying stopped.`);
    }
  });
}

async function resolveCopyCandidate(
  ctx: ExtensionContext,
  receipt: ListingReceipt | undefined,
  token: string,
  sessionId: string,
): Promise<SessionInfo> {
  return resolveCandidate(ctx, receipt, token, sessionId, "copy");
}

async function resolveCandidate(
  ctx: ExtensionContext,
  receipt: ListingReceipt | undefined,
  token: string,
  sessionId: string,
  operation: "copy" | "trash",
): Promise<SessionInfo> {
  if (!receipt || receipt.id !== token) {
    throw new Error(`Unknown or superseded ${operation} receipt; run pi_session_list again.`);
  }
  if (Date.now() > receipt.expiresAt) throw new Error("Listing receipt expired; list again.");
  if (normalizePath(ctx.cwd) !== receipt.runtimeCwd) {
    throw new Error("Runtime working directory changed; list again.");
  }
  const identity = receipt.sessions.get(sessionId);
  if (!identity) throw new Error("Session ID was not present in the referenced listing.");
  const sessions = await SessionManager.list(identity.cwd, receipt.sessionDir);
  const matches = sessions.filter(session => session.id === sessionId &&
    session.cwd !== "" && normalizePath(session.cwd) === identity.cwd);
  if (matches.length !== 1) throw new Error("Session is missing or its ID is not unique.");
  const source = matches[0];
  const currentFile = ctx.sessionManager.getSessionFile();
  if (source.id === ctx.sessionManager.getSessionId() ||
      (currentFile && normalizePath(source.path) === normalizePath(currentFile))) {
    throw new Error(`The currently active Pi session cannot be ${operation === "copy" ? "copied" : "trashed"}.`);
  }
  const currentIdentity = await identifySession(source);
  if (currentFile && currentIdentity) {
    let activeStats: { dev: number; ino: number } | undefined;
    try {
      activeStats = await stat(currentFile);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") {
        throw new Error("Cannot verify active-session file identity; no mutation performed.");
      }
    }
    if (activeStats && activeStats.dev === currentIdentity.device && activeStats.ino === currentIdentity.inode) {
      throw new Error("The currently active Pi session file cannot be copied or trashed through an alias.");
    }
  }
  if (!currentIdentity || !sameIdentity(identity, currentIdentity)) {
    throw new Error(operation === "copy"
      ? "Source session changed since listing; list again."
      : "Session changed since it was listed; list again.");
  }
  return source;
}

async function moveToRecoverableTrash(
  pi: ExtensionAPI,
  path: string,
  signal?: AbortSignal,
): Promise<"trash" | "gio trash"> {
  const trash = await pi.exec("trash", [path], { signal, timeout: TRASH_TIMEOUT_MS });
  if (trash.code === 0) return "trash";

  const gio = await pi.exec("gio", ["trash", path], { signal, timeout: TRASH_TIMEOUT_MS });
  if (gio.code === 0) return "gio trash";

  const diagnostic = [trash.stderr, gio.stderr]
    .map((value) => value.trim())
    .filter(Boolean)
    .join("; ")
    .slice(0, 300);
  throw new Error(
    `No recoverable trash command succeeded; the session was not deleted${diagnostic ? `: ${diagnostic}` : "."}`,
  );
}

async function identifySessions(
  sessions: SessionInfo[],
): Promise<Array<{ session: SessionInfo; identity: ReceiptSession }>> {
  const identified = await Promise.all(
    sessions.map(async (session) => {
      const identity = await identifySession(session);
      return identity ? { session, identity } : undefined;
    }),
  );
  return identified.filter(
    (item): item is { session: SessionInfo; identity: ReceiptSession } => item !== undefined,
  );
}

async function identifySession(session: SessionInfo): Promise<ReceiptSession | undefined> {
  try {
    const path = normalizePath(session.path);
    const stats = await stat(path);
    return {
      cwd: normalizePath(session.cwd),
      directoryStatus: await directoryStatus(normalizePath(session.cwd)),
      path,
      mtimeMs: stats.mtimeMs,
      size: stats.size,
      device: stats.dev,
      inode: stats.ino,
    };
  } catch {
    return undefined;
  }
}

function sameIdentity(left: ReceiptSession, right: ReceiptSession): boolean {
  return (
    left.cwd === right.cwd &&
    left.directoryStatus === right.directoryStatus &&
    left.path === right.path &&
    left.mtimeMs === right.mtimeMs &&
    left.size === right.size &&
    left.device === right.device &&
    left.inode === right.inode
  );
}

async function pathExists(path: string): Promise<boolean> {
  try {
    await access(path);
    return true;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return false;
    throw new Error("Cannot verify whether the session file remains; inspect the outcome before retrying.");
  }
}

async function directoryStatus(cwd: string): Promise<DirectoryStatus> {
  try {
    return (await stat(cwd)).isDirectory() ? "exists" : "unknown";
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code;
    return code === "ENOENT" || code === "ENOTDIR" ? "missing" : "unknown";
  }
}

function normalizePath(path: string): string {
  return resolve(path);
}
