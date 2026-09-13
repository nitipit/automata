import type {
  ExtensionAPI,
  ExtensionContext,
} from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

export const CONTEXT_COMPACTION_MESSAGE_TYPE = "automata-context-compaction";

interface PendingCompaction {
  id: number;
  customInstructions?: string;
}

function notify(
  ctx: ExtensionContext,
  message: string,
  level: "info" | "error",
): void {
  if (ctx.hasUI) ctx.ui.notify(message, level);
}

export default function (pi: ExtensionAPI) {
  let nextRequestId = 1;
  let pending: PendingCompaction | undefined;
  let compactionInProgress = false;

  const reset = (): void => {
    pending = undefined;
    compactionInProgress = false;
  };

  pi.on("session_start", reset);
  pi.on("session_tree", reset);
  pi.on("session_shutdown", reset);

  pi.on("session_compact", (_event, ctx) => {
    if (!pending || compactionInProgress) return;

    const requestId = pending.id;
    pending = undefined;
    notify(
      ctx,
      `Context compaction request ${requestId} was satisfied by another compaction.`,
      "info",
    );
  });

  pi.on("agent_settled", async (_event, ctx) => {
    if (!pending || compactionInProgress) return;
    if (!ctx.isIdle() || ctx.hasPendingMessages()) return;

    const request = pending;
    pending = undefined;
    compactionInProgress = true;
    notify(ctx, `Context compaction ${request.id} started.`, "info");

    await new Promise<void>((resolve) => {
      let finished = false;
      const finish = (): void => {
        if (finished) return;
        finished = true;
        resolve();
      };

      const fail = (error: Error): void => {
        compactionInProgress = false;
        notify(
          ctx,
          `Context compaction ${request.id} failed: ${error.message}`,
          "error",
        );
        pi.sendMessage(
          {
            customType: CONTEXT_COMPACTION_MESSAGE_TYPE,
            content:
              `The requested context compaction failed after the agent settled: ${error.message}. ` +
              "Do not retry automatically; reassess whether compaction is still useful.",
            display: false,
            details: {
              status: "failed",
              requestId: request.id,
              error: error.message,
            },
          },
          { deliverAs: "nextTurn" },
        );
        finish();
      };

      try {
        ctx.compact({
          customInstructions: request.customInstructions,
          onComplete: () => {
            compactionInProgress = false;
            notify(ctx, `Context compaction ${request.id} completed.`, "info");
            finish();
          },
          onError: fail,
        });
      } catch (error) {
        fail(error instanceof Error ? error : new Error(String(error)));
      }
    });
  });

  pi.registerTool({
    name: "context_compact",
    label: "Compact Context",
    description:
      "Queue one intentional Pi context compaction after the current agent run fully settles.",
    promptSnippet:
      "Compact context at a stable boundary after preserving durable task state",
    promptGuidelines: [
      "Treat context signals as observations, not automatic compaction commands. Call context_compact only when compaction is materially useful at a stable boundary.",
      "Preserve durable decisions, constraints, ownership, validation state, and next steps before calling. Use context_compact as the only final tool action when practical.",
      "Do not call immediately after a successful compaction or merely because usage is unknown unless the user explicitly requests it.",
    ],
    parameters: Type.Object(
      {
        customInstructions: Type.Optional(
          Type.String({
            description:
              "Optional focus passed unchanged to Pi's native compaction summary. Prefer concise guidance; keep durable state outside this field.",
          }),
        ),
      },
      { additionalProperties: false },
    ),
    async execute(_toolCallId, params, signal) {
      signal?.throwIfAborted();
      const { customInstructions } = params;

      if (compactionInProgress) {
        return {
          content: [{
            type: "text",
            text: "Context compaction is already in progress.",
          }],
          details: { status: "in_progress" },
          terminate: true,
        };
      }

      if (pending) {
        return {
          content: [
            {
              type: "text",
              text:
                `Context compaction request ${pending.id} is already queued; ` +
                "the existing request was kept unchanged.",
            },
          ],
          details: { status: "already_queued", requestId: pending.id },
          terminate: true,
        };
      }

      pending = {
        id: nextRequestId,
        customInstructions,
      };
      nextRequestId += 1;

      return {
        content: [
          {
            type: "text",
            text: `Queued context compaction request ${pending.id}. ` +
              "It will run after the agent fully settles.",
          },
        ],
        details: { status: "queued", requestId: pending.id },
        terminate: true,
      };
    },
  });
}
