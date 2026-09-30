# Practical dual-runtime support checkpoint

CX012, Codex 0.159.0. This supersedes the original audit's proposed parity work,
not its historical observations. The goal is similar capacity to achieve tasks,
not identical Pi tools, delivery modes or result fields. No global activation,
real account/provider calls or live-agent trials are established here.

## Current support

- **Shared guidance and installation:** one skill catalog and existing four shared
  tools. Direct installation remains preferred; plugin export is optional and
  must not create duplicate exposure. Pi extensions stay Pi-specific. Codex's
  optional hook/helper bundle requires separate config/trust activation.
- **Awareness, activity and session operations:** accepted version-pinned helpers
  retain their coverage and consent boundaries. See the sequence, context/time,
  activity and session audits; no implementation was changed in this slice.
- **Native colleagues:** prefer actual exposed native collaboration tools and read
  returned results. Queued/submitted messages and mailbox activity are not proof
  of completed tasks. Availability varies by model/config/runtime; this review
  did not run a native multi-agent trial.
- **External browser exchange:** existing generic router client plus an owned
  task-local Node process can expose messages and accept explicit replies. The
  [short recipe](../../../src/automata/skills/bundled/automata-message-router/references/node-client.md)
  uses one live connection, not a new polling product or custom model host.
  An active/resumed agent, authorized loopback and private participant grants are
  prerequisites. No automatic model wakeup, durable inbox or replay is promised.
- **Context relief:** native automatic compaction/continuation and human `/compact`
  suffice; no wrapper. Optional Pi summary-model preferences remain on Pi. Gated
  native `new_context` skips summarization, not an equivalent continuity tool.
- **Images:** accepted offline native invocation and workspace copy; live quality,
  entitlement and every runtime's tool exposure remain unproven. Native one-image
  consent is guidance, not Pi's bridge confirmation gate.
- **Account/resource inspection:** native login status reports local auth mode;
  human `/status` can show account labels, usage/reset snapshots and refresh where
  supported. Do not echo masked key fragments or equate context tokens with quota.
  Autonomous fresh quota and authenticated identity inspection remain unproven.
- **Effort:** launch-time selection and native human controls remain. Dynamic
  thinking control stays retired; installation does not remove old global copies.

## Focused finishing evidence

The installed router fixture extracts the exact JavaScript example from the
installed Markdown skill and runs it in a real child PTY with synthetic local
participants. A page request is forwarded, appears in JSON output, and gets an
explicit stdin reply on the same live client. The page receives the correlated
answer. Wrong/duplicate reply IDs fail; the owned process exits on interrupt.
The existing generic Node client exchange also runs in that same fixture.

This proves mechanical client/stdio/PTY composition, **not a Codex model invoking
exec_command/write_stdin**. Codex's process interface is source-supported:
`core/src/unified_exec/process_manager.rs` sets `stdin_open: tty`, and
`tools/handlers/unified_exec/write_stdin.rs` accepts input or empty polls for an
existing execution session. Thus the recipe requires `tty:true`. No mock-provider
or real-model request was needed; no additional native experiment was run.

The updated archive smoke check covers the new Markdown resource in wheel/sdist,
installed skill references, the existing Pi extension selection, all four shared
tools and Codex helper installation with external state and no activation. Source
review found no production installer change necessary. Discovery/file placement
is not runtime trust, actual model tool exposure or task completion.

Focused commands:

```sh
uv run --offline pytest -q tests/integration/automata/tools/message_router_test.py::test_installed_router_without_ui_and_private_static_boundaries
uv run --offline pytest -q tests/integration/automata/package_test.py::test_built_archives_ship_pi_resources_only_at_new_paths tests/cli/automata/codex_test.py
git diff --check
```

No full browser sweep, unchanged portable-skill behavioral tests, global install,
retired-asset cleanup or speculative framework was needed. The seven untracked
research scripts remain outside this finishing commit; the TLS helper was not run.

## Before real use

- Confirm intended runtime, actual exposed tools, installation roots and selected
  assets; separately authorize activation and effects.
- Confirm loopback/file permissions and participant grants rather than relaxing
  real-user sandbox settings. Keep private endpoints outside public roots.
- Read actual replies/results. Do not promote external payloads into authority or
  infer successful handling from transport acknowledgments.
- Label stale/missing resource information and source-only compatibility honestly.
  Revalidate version-dependent contracts after upgrades.
