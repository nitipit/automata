# Fast request policy for Pi

A small separate extension for `/fast` toggling, explicit `/fast on|off|status`
and startup `--fast`.
**It requests a tier; it does not track the response tier or prove Fast access,
speed, quotas or billing.** No model/reasoning change, provider replacement,
response records, cost correction, global configuration or new dependency.

## Commands and startup

| Control | Effect |
| --- | --- |
| `/fast` | Toggle the active branch's desired Fast policy on/off |
| `/fast on` | Request wire tier `priority` on selected official Codex and OpenAI API routes |
| `/fast off` | Remove `service_tier` on Codex (standard request); explicitly request `default` on OpenAI API routes. Clear inherited premium values in both cases |
| `/fast status` | Show desired on/off state without changing it |
| `--fast` | Opt the initial active branch into premium at CLI startup |

OpenAI documents API `fast` and `priority` as equivalent for supported models.
Codex's `fast` **CLI/config label is not its outgoing wire value**: official
Codex normalizes it to `priority`. Its explicit standard/default selection omits
`service_tier` on the wire. This extension follows those representations, removing
any existing Codex tier when off rather than sending a literal `default`.
Omission/default selection is a request policy, not proof of the actual tier used.
The initial policy is off unless branch
history or explicit startup `--fast` enables it. There is no model whitelist:
GPT-6.1 Sol and future IDs may attempt the tier if Pi already provides them.
Actual model/account/provider eligibility is unverified; the provider can reject
or downgrade a request. No probes or automatic fallback are added.

**One current policy applies to all eligible hooked invocations**, deliberately
including native cache warming and other auxiliary calls. On may therefore request
premium on those calls too. A later `/fast off` affects future invocations, not
an already-dispatched premium request. Warming remains enabled with native
options/economics. There is no main-request snapshot for a warm response to corrupt.

Policy is custom session metadata excluded from model context. Raw active ancestry
controls tree navigation, fork/clone inheritance, resume and compaction. New
sessions without a launch override start off. Resume at CLI startup preserves
branch policy unless `--fast` explicitly opts it on; the override is recorded on
that branch. It is not reapplied by `/reload`, in-process `/new`, `/fork` or
`/resume`. Thus `/fast off` stays off after reload, even when Pi launched with
`--fast`. Omitting `--fast` does not turn a resumed on branch off; use `/fast off`.
Pi treats a present boolean flag as true, so `--fast false` is not a disable control. There is no global enabled-state migration or agent tool.

Commands confirm **Fast mode on** or **Fast mode off**. When on with an
unsupported selected route, they show **Fast mode on — unavailable for this model**.
“On” confirms the desired request policy, not delivered priority or faster replies.
The extension does not inspect provider responses to determine the actual served
tier; response-tier and premium usage/pricing caveats stay in documentation rather
than repeated notifications. Premium usage/pricing may apply to eligible conversation
and auxiliary calls. Unsupported routes remain untouched even when off; an off
confirmation does not enforce Standard on those routes. TUI/RPC use native UI
feedback; status/command feedback in print/JSON goes to stderr, not protocol stdout.
Native cost estimates remain unchanged and are not authoritative billing records
(especially Codex premium requests, missing tier metadata and Chat Completions).

## Accepted operating boundary

Use **official, directly selected OpenAI API/Codex-login routes only**. Do not use
proxy aliases/custom redirection, or change models while a request is being
dispatched. Virtual-model routing is not promised.

The best-effort selected-model guard accepts:

- `openai`, `openai-responses` or `openai-completions`,
  `https://api.openai.com/v1` with optional trailing slash.
- `openai-codex`, `openai-codex-responses`,
  `https://chatgpt.com/backend-api`, optionally ending in `/codex` or
  `/codex/responses`, with optional trailing slash.

Other static providers/APIs/endpoints and mismatched payload model IDs are
untouched. URLs with userinfo, nonstandard ports, query or fragment are rejected.
Desired on/off state can remain stored while the selected route is inactive.

**This is not robust physical-route isolation.** Pi 1.0.4's payload hook omits
the actual physical model argument, so the extension reads mutable selected
`ctx.model`. A same-ID selection switch during an awaited preceding hook can
make a proxy's already-chosen physical request look eligible. Custom redirection
can have the same problem. Static guards cannot prove this race safe. The user
must observe the operating boundary above; inactive status does not enforce a
Standard tier. The preserved v1 review evidence reproduces that limitation.

Later payload handlers may override this extension's request. Do not co-load
competing tier controllers. No prompt, payload, response, header or credential
is logged; only on/off policy entries are written to the session.

## Load/install and migration

The bundle contains `index.ts` and this README and uses Automata's existing
installer. **Do not co-load `npm:pi-openai-fast-mode`**, its `/fast`/`--fast` controls,
or another tier controller. Disabling/removing the old resource and activation
need separate approval; this source delivery does not change the installed package
or import its persisted enabled configuration.

After approval, a selected installation is:

```sh
uv run automata pi-extension install --extension fast-mode --target-root ~/.pi/agent/extensions
```

Alternatively load explicitly from a checkout. These are usage examples, not a
claim the extension is installed, active or your chosen model is available:

```sh
E="$PWD/src/automata/runtimes/pi/extensions/fast-mode"
pi --no-extensions -e "$E" --fast                       # interactive
pi --no-extensions -e "$E" --print --fast -- "Your task" # text, one shot
pi --no-extensions -e "$E" --mode json --fast -- "Your task"
pi --no-extensions -e "$E" --mode rpc --fast
pi --no-extensions -e "$E" --continue --fast              # opt resumed branch on
```

Explicit `-e` still loads with `--no-extensions`; discovery and built-ins are
otherwise disabled. Use `--` before a positional prompt so Pi's unknown-extension
flag parser does not consume it as the boolean flag's value. Add your normal
`--model`/`--thinking` options without changing the intended selection/effort.
For tmux, after approving the path and launch:

```sh
tmux new-session -s fast 'pi --no-extensions -e /absolute/path/to/fast-mode --fast'
```

Check `/fast status` before use. Off omits `service_tier` for Codex and requests
`default` for OpenAI API routes; notifications show only the concise mode state.
Without `--fast`, a resumed branch still follows its saved policy. Removing the
extension also removes its off-policy override; it does not alter provider/project
defaults.

Existing v1 branch entries store only on/off, not a tier string, so no session
migration is needed. A separately approved install/reload applies this corrected
mapping to future invocations, including eligible warming; in-flight requests
remain unchanged. The already-installed copy is not corrected by editing source.

## Verification

Offline tests cover syntax/flag precedence, raw session branch lifecycle, static
guards, native CLI argument parsing, SDK registration and native OpenAI streams
with fetch/SSE stubs. Eligible real native warming receives the deliberate current
policy, including overlap/error/idle/slow-tool cases; no response-observer state
exists. See `tests/integration/automata/extensions/fast_mode_test.py`. Set
`PI_TEST_PACKAGE_ROOT` if installed Pi discovery fails. Package/install checks
cover both bundle files. No live access, pricing, latency or race-isolation claim.

## Primary wire-tier evidence

Verified 6 October 2026 against official `openai/codex` commit
`822e58cc3d666166c7446c5b1ea2e52f5d09594c`:

- [Config types, lines 533–550](https://github.com/openai/codex/blob/822e58cc3d666166c7446c5b1ea2e52f5d09594c/codex-rs/protocol/src/config_types.rs#L533-L550):
  `ServiceTier::Fast.request_value()` returns `"priority"`; both `"fast"` and
  `"priority"` parse as Fast. `"default"` is a config/request sentinel for an
  explicit standard selection, not a catalog tier ID.
- [Config normalization, lines 3981–3996](https://github.com/openai/codex/blob/822e58cc3d666166c7446c5b1ea2e52f5d09594c/codex-rs/core/src/config/mod.rs#L3981-L3996):
  parsed Fast becomes `ServiceTier::Fast.request_value().to_string()`.
- [Request resolution, lines 998–1002](https://github.com/openai/codex/blob/822e58cc3d666166c7446c5b1ea2e52f5d09594c/codex-rs/protocol/src/openai_models.rs#L998-L1002):
  `service_tier_for_request` filters out the explicit `"default"` sentinel.
  [Client, lines 979–1007](https://github.com/openai/codex/blob/822e58cc3d666166c7446c5b1ea2e52f5d09594c/codex-rs/core/src/client.rs#L979-L1007)
  uses that result as the outgoing request's `service_tier`.
- [HTTP serializer, lines 279–285](https://github.com/openai/codex/blob/822e58cc3d666166c7446c5b1ea2e52f5d09594c/codex-rs/codex-api/src/common.rs#L279-L285)
  and [WebSocket serializer, lines 330–337](https://github.com/openai/codex/blob/822e58cc3d666166c7446c5b1ea2e52f5d09594c/codex-rs/codex-api/src/common.rs#L330-L337):
  `#[serde(skip_serializing_if = "Option::is_none")]` omits that field.

Pi AI 1.0.4's native `dist/api/openai-codex-responses.js` invokes `onPayload`
then serializes the returned body, with no Fast-label conversion. Offline native
SSE tests check `priority` when on and field absence when off, including overriding
an inherited provider `serviceTier: "priority"`. Fixture success proves payload
construction, not backend acceptance, account/model entitlement, observed tier,
latency or billing. No live provider tests were performed.

[Codex speed](https://developers.openai.com/codex/speed/) documents the `fast`
config label and eligibility caveats; it is not a wire serialization specification.
[API Fast mode](https://developers.openai.com/api/docs/guides/fast-mode) documents
API `fast`/`priority` equivalence. Codex backend acceptance of literal `default`
was not established; off follows the official client's omission instead.
