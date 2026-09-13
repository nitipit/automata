import { randomUUID } from "node:crypto";
import { access, stat } from "node:fs/promises";
import { resolve } from "node:path";

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

type SessionSummary = {
  id: string;
  name?: string;
  created: string;
  modified: string;
  messageCount: number;
  current: boolean;
};

type ReceiptSession = {
  path: string;
  mtimeMs: number;
  size: number;
  device: number;
  inode: number;
};

type ListingReceipt = {
  id: string;
  cwd: string;
  expiresAt: number;
  sessions: Map<string, ReceiptSession>;
};

export default function (pi: ExtensionAPI) {
  let latestReceipt: ListingReceipt | undefined;

  pi.registerTool({
    name: "pi_session_list",
    label: "List Pi Sessions",
    description:
      "List up to 100 Pi sessions attributed to the exact current working directory. " +
      "Uses trusted runtime context, returns no session paths or conversation content, and " +
      "issues a short-lived receipt required by pi_session_trash.",
    promptSnippet: "List Pi sessions for the exact current working directory",
    promptGuidelines: [
      "Use pi_session_list instead of scanning Pi session files when identifying sessions for the current working directory.",
      "Treat recorded delegated-agent session IDs as primary identity; use pi_session_list for discovery or recovery.",
    ],
    parameters: Type.Object({}, { additionalProperties: false }),
    async execute(_toolCallId, _params, signal, _onUpdate, ctx) {
      signal?.throwIfAborted();
      const cwd = normalizePath(ctx.cwd);
      const allSessions = await listExactCwdSessions(ctx);
      const listedSessions = await identifySessions(allSessions.slice(0, LISTING_LIMIT));
      const currentSessionId = ctx.sessionManager.getSessionId();
      const currentSessionFile = ctx.sessionManager.getSessionFile();

      const summaries = listedSessions.map(({ session }) =>
        summarizeSession(session, currentSessionId, currentSessionFile),
      );
      const now = Date.now();
      latestReceipt = {
        id: randomUUID(),
        cwd,
        expiresAt: now + RECEIPT_TTL_MS,
        sessions: new Map(
          listedSessions.map(({ session, identity }) => [session.id, identity]),
        ),
      };

      const result = {
        cwd,
        receipt: latestReceipt.id,
        receiptExpiresAt: new Date(latestReceipt.expiresAt).toISOString(),
        sessions: summaries,
        omittedCount: Math.max(0, allSessions.length - listedSessions.length),
      };

      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        details: result,
      };
    },
  });

  pi.registerTool({
    name: "pi_session_trash",
    label: "Trash Pi Session",
    description:
      "Move one non-current Pi session from the exact current working directory to the " +
      "operating-system trash. Requires an exact session ID and a fresh pi_session_list receipt. " +
      "The agent establishes user authorization and inactivity from context; no tool-level confirmation dialog. " +
      "Never falls back to permanent deletion.",
    promptSnippet: "Safely move one listed current-CWD Pi session to recoverable trash",
    promptGuidelines: [
      "Use pi_session_trash only after pi_session_list, within the user's authorized scope, and when ownership and inactivity are sufficiently established; the tool does not detect sessions open in other processes.",
      "For pi_session_trash, use context to decide whether clarification or permission is needed. A clear removal request or prior scoped authorization needs no repeated confirmation; otherwise present candidates, optionally as stable numbered choices mapped to full session IDs.",
      "pi_session_trash must never be replaced with rm or direct session-file deletion.",
    ],
    parameters: Type.Object(
      {
        sessionId: Type.String({
          minLength: 1,
          description: "Exact full session ID returned by pi_session_list.",
        }),
        receipt: Type.String({
          minLength: 1,
          description: "Fresh receipt returned by pi_session_list in this runtime.",
        }),
      },
      { additionalProperties: false },
    ),
    async execute(_toolCallId, params, signal, _onUpdate, ctx) {
      signal?.throwIfAborted();
      const revalidated = await resolveReceiptCandidate(ctx, latestReceipt, params);
      signal?.throwIfAborted();
      const method = await moveToRecoverableTrash(pi, revalidated.path, signal);
      if (await pathExists(revalidated.path)) {
        throw new Error("Trash command reported success but the session file is still present.");
      }

      latestReceipt = undefined;
      const result = {
        status: "trashed",
        sessionId: revalidated.id,
        name: revalidated.name,
        cwd: normalizePath(ctx.cwd),
        method,
      };
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
        details: result,
      };
    },
  });
}

async function listExactCwdSessions(ctx: ExtensionContext): Promise<SessionInfo[]> {
  const cwd = normalizePath(ctx.cwd);
  const sessions = await SessionManager.list(ctx.cwd, ctx.sessionManager.getSessionDir());
  return sessions.filter((session) => session.cwd !== "" && normalizePath(session.cwd) === cwd);
}

function summarizeSession(
  session: SessionInfo,
  currentSessionId: string,
  currentSessionFile: string | undefined,
): SessionSummary {
  return {
    id: session.id,
    ...(session.name ? { name: session.name } : {}),
    created: session.created.toISOString(),
    modified: session.modified.toISOString(),
    messageCount: session.messageCount,
    current:
      session.id === currentSessionId ||
      (currentSessionFile !== undefined &&
        normalizePath(session.path) === normalizePath(currentSessionFile)),
  };
}

async function resolveReceiptCandidate(
  ctx: ExtensionContext,
  receipt: ListingReceipt | undefined,
  params: { sessionId: string; receipt: string },
): Promise<SessionInfo> {
  if (!receipt || receipt.id !== params.receipt) {
    throw new Error("Unknown or superseded listing receipt; run pi_session_list again.");
  }
  if (Date.now() > receipt.expiresAt) {
    throw new Error("Listing receipt expired; run pi_session_list again.");
  }

  const cwd = normalizePath(ctx.cwd);
  if (receipt.cwd !== cwd) {
    throw new Error("The current working directory changed; run pi_session_list again.");
  }

  const listed = receipt.sessions.get(params.sessionId);
  if (!listed) {
    throw new Error("Session ID was not present in the referenced current-CWD listing.");
  }

  const matches = (await listExactCwdSessions(ctx)).filter(
    (session) => session.id === params.sessionId,
  );
  if (matches.length !== 1) {
    throw new Error("Session is missing or its ID is not unique in the current CWD.");
  }

  const candidate = matches[0];
  const candidatePath = normalizePath(candidate.path);
  const currentIdentity = await identifySession(candidate);
  if (!currentIdentity || !sameIdentity(listed, currentIdentity)) {
    throw new Error("Session changed since it was listed; run pi_session_list again.");
  }

  const currentSessionFile = ctx.sessionManager.getSessionFile();
  if (
    candidate.id === ctx.sessionManager.getSessionId() ||
    (currentSessionFile !== undefined &&
      candidatePath === normalizePath(currentSessionFile))
  ) {
    throw new Error("The currently active Pi session cannot be trashed.");
  }

  return candidate;
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
  } catch {
    return false;
  }
}

function normalizePath(path: string): string {
  return resolve(path);
}
