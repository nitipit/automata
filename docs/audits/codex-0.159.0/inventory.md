# Complete inventory and support matrix

Classification: **U** unchanged shared guidance/tool; **G** guidance adaptation;
**A** runtime adapter required; **N** native/alternative with different semantics;
**X** unavailable under the current ordinary-CLI contract. Classification is not
behavioral certification. All 40 skill bodies were read; all 40 candidate-installed
skills were discovered by the isolated native loader. Supporting assets were
inspected selectively at runtime boundaries, not exhaustively behavior-tested.

## Bundled skills (40)

Each name resolves to the exact evidence path
`src/automata/skills/bundled/<name>/SKILL.md`. The evidence column identifies its
relevant contract. Supporting links below are relative to the repository root.

| Skill | Class | Evidence / Codex limit |
| --- | --- | --- |
| automata-adaptive-ui | U/G | Compose/Build shared TS/Python assets; optional Chat uses separate router, whose Pi client is not portable |
| automata-agent-design | U | Capability placement and authority, no Pi API |
| automata-agent-evaluation | U | Runtime verification deliberately generic; live trials require their own authority |
| automata-agents-md | U | Explicit runtime/surface discovery; Codex precedence differs from Pi |
| automata-browser-use | U | Isolated browser/profile judgment; socket/profile access must fit sandbox |
| automata-capability-research | U | Evidence/readiness/authority separation, no Pi API |
| automata-codex-imagegen | G/N | Workflow names Pi `codex_imagegen`; Codex has native `image_gen` capability and bundled imagegen skill, not this wrapper contract |
| automata-communication | U | Channel/recipient judgment independent of runtime |
| automata-context-compaction | G/A/N | Pi `context_compact` and summary-model/effort/resume semantics; native Codex compact is not parity |
| automata-context-status | G/A | Pi input-anchor, pressure and elapsed telemetry contract requires runtime adapter; native UI status is alternative |
| automata-cue | U | Plain-file retention/retrieval; no session API |
| automata-delegation | U | Generic model/runtime verification and owned transport; Codex launch/queue readiness still needs evidence |
| automata-git-worktree | U | Git CLI ownership/placement; unchanged (worktree is not sandbox) |
| automata-gnome-desktop-control | U | AT-SPI/ydotool depends on OS permissions, not Pi |
| automata-goal | U | Durable goal files and explicit AGENTS linking |
| automata-journal | U | File retrieval/capture; read/search tool names are conceptual, optional yq prerequisite |
| automata-line-use | U | Explicit shared line_cli.py mapping; Playwright/browser access and send consent still required |
| automata-message-router | G/A | Shared service, but tool calls and receipt/admission semantics explicitly Pi |
| automata-model-selection | U | Runtime/model availability distinguished from preferences; no automatic runtime switch |
| automata-pi-sessions | X/N | Correctly Pi-specific; leave named Pi. Codex resume/fork/archive are separate native alternatives |
| automata-plain-text-writing | U | Format-safe edits independent of runtime |
| automata-plan | U | Planning judgment independent of runtime |
| automata-question | U | Consent/choice shaping independent of runtime |
| automata-runtime-environment | U | Explicitly discovers unknown runtime facts without assumed Pi APIs |
| automata-setup | G | Roots shared, but general setup currently offers Pi extensions; add runtime-specific selection without replacing Pi |
| automata-skill-activity | G/A | Pi complete `read` observer and Pi helper location; Codex loading is not that event contract |
| automata-skill-design | U | Skill frontmatter/contracts/shared tool metadata; Codex does not execute metadata mappings |
| automata-software-development | U | Generic engineering checks and isolated dependencies |
| automata-stateful-workflow | U | Storage/runtime-independent state and external-effects reasoning |
| automata-storage | U | Owner-scoped shared paths, not Pi store paths |
| automata-task-space | U | Shared task placement/lifecycle, no runtime API |
| automata-team-management | U | Parent authority/reporting independent of runtime; wakeable transport must be proven |
| automata-teamwork-design | U | Context/model ownership judgment independent of runtime |
| automata-thinking-control | G/A/N | Calls Pi `thinking_control`; native model controls differ and API effort validation is not equivalent |
| automata-timer | U | Shell scheduler; subprocess/signal access and delivery transport must be separately available |
| automata-tmux-background | U | Generic tmux lifecycle; sandbox may prohibit host socket access |
| automata-tmux-communication | U/G | Generic literal send, but a Pi-safe inbox does not establish Codex queue/input readiness |
| automata-tmux-observation | U | Owned-pane read-only evidence; no Pi integration |
| automata-toolsmith | U | Shared CLI-first tooling and dependencies |
| automata-work-pause | U | Runtime-independent stop/resume authority; native stop mechanism must exist |

## Shared tools (all four packages)

| Package / exact entry | Class | Evidence and limit |
| --- | --- | --- |
| `tools/line/line_cli.py` | U | PEP 723 Python CLI; Playwright, Cyclopts, Dictify; uses browser/profile state, no Pi import. Browser/send not tested here |
| `tools/timer/timer.py` | U | PEP 723 Cyclopts/APScheduler; owns process state/locks and Linux `/proc` identity. Scheduler not a runtime inbox |
| `tools/tmux-message/tmux_message.py` | U/G | `deliver_message`, `--owned-pane`, literal send and bounded pacing; no hardcoded Pi runtime. `sent` proves transport only, not safe Codex handling |
| `tools/message-router/message_router.py` | U/A | Python server/CLI and generic browser client shared; agent session admission adapter is runtime-specific |

Paths above are under `src/automata/`. Router companion entries
`agent_browser_bridge.py` (legacy CLI) and `automata_router/{cli,legacy,protocol,
router,server}.py` remain the same package. Browser `client.js`, `page.js`,
`protocol.js`, and `legacy-client.js` are transport assets;
`browser/pi-client.js` explicitly sends `metadata.pi` and interprets Pi receipts.
It must not be relabeled as Codex-compatible without a new delivery contract.

Adaptive UI is a skill-owned library/builder, not a fifth shared tool package.
The skill-activity `store.py` helper currently belongs to the Pi extension, not
`tools/`; potential sharing requires an intentional owner decision.

All shell tools need executable/dependency availability, allowed local paths,
network/socket permissions where applicable, and cleanup. A shared codebase is
not permission to bypass Codex sandbox or a claim the environment is ready.

## Every Pi integration (nine)

Evidence paths below are under `src/automata/runtimes/pi/extensions/`.

| Integration | Ordinary Codex disposition | Exact reference boundary |
| --- | --- | --- |
| `codex-bridge.ts` | G/N; optional A | `registerTool` account status/imagegen; Pi confirmation and child Codex invocation. Codex native imagegen/account status are alternatives, not a need to port the Pi bridge back into Codex |
| `context-compaction.ts` | N; A for richer contract | `agent_settled`, `session_before_compact`, `ctx.compact`; model selection/no fallback/resume queue not in Codex compact schema |
| `context-status.ts` | A/N | `getContextUsage`, `context`, message/turn events and queued signals; no native CLI plugin access to equivalent hooks established |
| `message-timestamps.ts` | X exact; G/A reduced | `annotateMessage` + Pi `context` transforms copies without rewriting stored text; Codex hooks append persistent developer messages |
| `message-router/index.ts` | A | Pi `sendMessage`, `sendUserMessage`, branch admission and session lifecycle; shared service is not the adapter |
| `pi-sessions.ts` | X/N | Pi SessionManager, copy/trash receipts and OS recoverable trash; Codex fork/archive not drop-in replacement |
| `skill-activity/index.ts` + `store.py` | A/G | Watches successful full `read` calls with no pagination; ignores shell reads and explicit skill commands. Codex shell/code-mode/explicit skill loads need different provenance/coverage |
| `thinking-control/{index,local}.ts` | N/A | Native Pi support validation + next-model-request state. Codex settings acceptance alone is insufficient |
| `token-awareness.ts` | X exact; A research | `scanBranch`, custom entries, `turn_end` checkpoint, `context` replay; no exact Codex CLI ancestry/projection mechanism proven |

Pi extensions are not Codex plugins. No TypeScript extension was copied into
Codex or removed from Pi. No forced parity or unavailable named tool was added.
