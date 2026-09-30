# CX-009 — native image generation; separate account-status checkpoint

Checked 2026-09-30 against stock Codex 0.159.0. The user clarified that an existing
native capability counts: do not rebuild Pi wrappers merely for parity. This slice
adds guidance and evidence, **not a generator, artifact publisher, account wrapper,
new host, permission change or global activation**. Pi's bridge is unchanged.

## Image generation: actual ordinary-CLI path

An isolated ordinary `codex exec --json` session invoked `image_gen.imagegen` with
one prompt. The native implementation called `/v1/images/generations` with
`model: gpt-image-2`, consumed one synthetic PNG response, decoded it, saved it under
`$CODEX_HOME/generated_images/<thread>/<call>.png`, and returned image content plus
the actual path to the model. Its own shell then copied identical bytes into
`output/imagegen/synthetic.png` using exclusive file creation. The native original
remained present. No workspace destination argument or extra generator was needed.

The fixture used `gpt-6-astra`, `features.image_generation=true`, synthetic ChatGPT
Pro auth, a local mock Responses/images endpoint, stock workspace-write with
restricted network, and a bubblewrap private network with synthetic HOME. Native
image handling, not a shell API-key script, made the image request. Model replies
were scripted: this proves invocation and file handling, not agent judgment,
image quality, live entitlement or availability for every model/account/provider.

### Native contract versus guidance

- The pinned native namespace is `image_gen`, tool `imagegen`. Follow the actual
  exposed schema; a model name or skill alone does not establish availability.
  Source gates include feature, provider capabilities, image input support and
  account restrictions. They were not exhaustively varied in this bounded proof.
- One native call, one image request and one generated artifact were observed.
  This is **not** a native hard limit of one call per user turn. Consent and the
  one-image authorization boundary remain agent guidance, not Pi's confirmation
  mechanism. No regex-based authorization or hard-gate retrofit was added.
- For project use, copy the actual returned artifact with normal filesystem tools.
  Check the resolved destination, including symlink parents, stays in the allowed
  workspace and refuse unintended overwrites. There is no new publisher providing
  additional enforced containment or collision guarantees.
- Copy failure is not generation failure: retain/report the native artifact and
  repair the copy within scope; do not automatically consume quota again.
- An early fixture contained invalid PNG bytes. Native handling retained the file
  and returned an image-content omission instead of a decoded image. Later valid
  CRC PNG fixtures passed. A path alone is not proof of a usable image; earlier
  optimistic prototype markers are superseded by the separate verifier.
- No silent API-key, provider or model fallback is allowed by Automata guidance.
  Collision/hostile-path cases and live-agent consent compliance were not separately
  exercised by this final native fixture; no stronger enforcement claim is made.

## Account status: retained, separately incomplete

A turn-free standalone native app-server query returned controlled rate-limit
windows: 25% used over 300 minutes and 60% over 10080 minutes, with explicit reset
values and a provider-reported Pro plan. This was **controller evidence**, not a
successful ordinary tool-shell account reader or proof of a real signed-in account.

The same native account-server startup from the ordinary restricted shell failed:
first SQLite initialization under read-only CODEX_HOME; then, after a supported
task-local `sqlite_home` override, another read-only-filesystem error. Native source
requires `installation_id` to be opened read/write/create even when it already
exists (`core/src/installation_id.rs`, called by `app-server/src/lib.rs`). No native
home write grant, auth copy, shadow credential home or alternate host was adopted.

Full `account/read` identity was not proven even in the controller fixture: its
HTTP mock did not satisfy native HTTPS workspace-routing requirements. A private
TLS fixture helper was prepared but **not executed** before scope narrowed; it is
preserved as research, not evidence of success. This fixture limitation must not be
presented as proof that native account identity is intrinsically unavailable.

Existing native rollout `token_count.rate_limits` records were inspected in the
owned fixture. They had null windows/plan in that run. Source also supports
`codex.rate_limits` events carrying plan/windows; those would be last-observed
provider data, not fresh account authentication. No agent-facing observation reader
was implemented or proven here. Never infer signed-in identity or quota from
context-token counts or model names. Other native account interfaces were not
exhaustively assessed; the tested route's gap is not a blanket CLI limitation.

Native startup additionally attempted models/plugin/workspace/settings requests
and MCP initialization against the controlled local mock. These incidental requests
are preserved in evidence, not represented as a pure one-endpoint account lookup.
No real credentials, real account/provider requests or external network were used.

## Evidence and verification

Task-owned `account-image-3` and `account-image-4` fixtures preserve valid PNGs,
mock requests, native output and the account failure diagnostics. The explicit,
read-only verifier is:

```sh
python tests/integration/automata/codex_runtime/verify_account_image_probe.py \
  --state-root <owned-fixture-directory>
```

It checks actual ordinary exec invocation, one image request, native decoded image
content, matching source/workspace bytes, retained original, credential-sentinel
exclusion and the separately labelled account gap. It does not call a provider,
read auth files or certify consent enforcement. Both valid fixtures pass; the early
invalid/omitted-image fixture is rejected. The 67 focused skill, guidance and
isolated-wheel/package checks pass; catalog 40 and retained Pi implementations
remain unchanged. No broad browser suite was repeated.

Research fixture scripts remain
separate and uncommitted; the original four thinking-control scripts are preserved.

Image generation has a verified offline native path without a custom wrapper.
Account status remains a separate unresolved requirement. The combined bridge
capability is not marked complete and the five-completed-of-eight count is unchanged.
