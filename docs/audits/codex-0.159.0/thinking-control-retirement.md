# CX-008R — dynamic thinking-control retirement

Approved 2026-09-30. This decision supersedes the original nine-capability parity
scope, not the historical observations in this directory. Automata retires its Pi
`thinking_control` extension and `automata-thinking-control` skill and stops the
Codex port. Dynamic effort control is **retired, not successfully ported**.

## Evidence and decision boundary

Isolated Codex 0.159.0 mock-provider research established a native settings
primitive: captured efforts were low, low, medium, with the model unchanged.
Thread settings affected later turns, not a captured request already in flight.
Turn settings were feature-gated. A separate app-server could not control the
owning thread; ordinary embedded `codex exec` exposed no proven control endpoint.

An owned stock daemon and real native TUI attached over WebSocket-over-UDS. Under
an inherited read-only filesystem and restricted network profile, the TUI's own
shell still could not access its exactly allowlisted control socket. An unlisted
fixture socket remained denied and writes failed EROFS. Actual user-thread
requests stayed low/low; an internal title request was counted separately.
This established a permission/integration gap, not agent-reached effort control.
No network enablement, wildcard socket rule or sandbox bypass was attempted.

A separate unsandboxed fixture controller could read a sibling fixture thread
and receive an acknowledgement for a no-op approval-policy update. This is
controller evidence, not authority reached by the sandboxed agent. Socket mode
0600 and peer credentials establish OS access/identity, not per-thread or
per-method isolation. A capability-filtered adapter was only an unproven option;
it was not adopted or implemented, and no further investigation is in scope.

Research used synthetic state and a mock provider, not real credentials, user
histories or live model judgment. Four research-only `thinking_*` fixture scripts
and task-owned evidence remain separate from the retirement commit. No successful
control capability or production adapter is claimed by their presence.

## Retained support

Eight runtime capabilities remain in scope:

| Capability | Codex status at this decision |
| --- | --- |
| Token awareness | Verified offline, bounded version-pinned hook/helper contract |
| Context status | Verified offline, labelled last-known telemetry |
| Message timestamps | Verified offline, bounded native item/lifecycle annotations |
| Skill activity | Verified offline, native insertion observer and session-scoped controls |
| Session management | Verified offline, receipt-scoped copy/fork/OS-trash/native restore |
| Context compaction | Native human alternative; advanced Pi contract not ported |
| Message routing | Shared service/assets; no Codex agent adapter |
| Account status and image generation (`codex-bridge`) | Both retained in scope; use exposed native interfaces only, with neither Codex implementation claimed complete |

Five have offline Codex verification, not live behavioral certification. Their
accepted contracts and the existing Pi implementations are retained unchanged.

## Effort selection and installation

Choose the approved model and a supported effort at launch:

- Pi: `--model <provider/id> --thinking <level>`. Pi 0.99.1 documents clamping to
  model capabilities; verify effective settings, not just requested flags.
- Codex: `--model <model> -c 'model_reasoning_effort="medium"'`. Do not use Pi's
  `--thinking` flag for Codex.
- Native human Pi `/model` and `/thinking`, and Codex `/model`, remain available.
  Later worker-setting changes must stay within the approved scope and use
  native human controls or relaunch, not a request to call the retired tool.
- Compaction-summary effort, imagegen parameters, child-launch effort and model
  preferences are independent and remain supported.

The shared skill catalog changes from 41 to 40. Source discovery/default Pi
installation omits only `thinking-control`; all eight other extension entries
remain. Explicit selection of the removed bundled extension fails before writes.
The installer does **not** uninstall existing copies, alter global configuration
or reload live sessions. Installed retirement/activation requires separate
permission; no migration or cleanup is performed by this source change.

## Retirement verification

- 145 focused installer, CLI, skill/catalog, wheel-resource, Pi regression and
  source-view/browser checks passed with no skips. One dependency deprecation
  warning remains; no application/browser implementation changed.
- Both source and isolated installed-wheel manifests contain the eight retained
  Pi extensions and 40 skills. Retired selections fail before writes; existing
  installed copies survive default installation. Retired viewer routes return 404.
- Existing compaction tests pass, including an additional explicitly pinned
  Pi 0.99.1 installed-runtime invocation without provider I/O. Retained runtime
  implementations and independent effort parameters were not changed.
- Initial test setup selected an old Pi SDK and lacked optional viewer packages;
  explicit current-SDK test overrides and cached isolated dependencies resolved
  these environment failures without global changes or source workarounds.
