# Fast request policy for Pi

A small separate extension for `/fast on|off|status` and startup `--fast`.
**It requests a tier; it does not track the response tier or prove Fast access,
speed, quotas or billing.** No model/reasoning change, provider replacement,
response records, cost correction, global configuration or new dependency.

## Commands and startup

| Control | Effect |
| --- | --- |
| `/fast on` | Request `fast` on selected official Codex routes; `priority` on selected official OpenAI API routes |
| `/fast off` | Explicitly request `default` on eligible hooked invocations, not inherited `auto`/premium |
| `/fast status` or `/fast` | Show desired policy, selected-route eligibility and requested tier; no toggle |
| `--fast` | Opt the initial active branch into premium at CLI startup |

OpenAI documents API `fast` and `priority` as equivalent for supported models;
Codex uses its documented `fast` value. The initial policy is off unless branch
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

Status says **request policy** and **response tier not tracked**. An inactive
route says **tier not enforced**, never Standard enforced. TUI/RPC use native UI
feedback; status/command feedback in print/JSON goes to stderr, not protocol stdout.
Native cost estimates remain unchanged and are not authoritative billing records
(especially Codex `fast`, missing tier metadata and Chat Completions).

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

Check `/fast status` before use. Without `--fast`, a resumed branch still follows
its saved policy. Removing the extension also removes its explicit-default guard;
it does not alter provider/project defaults.

## Verification

Offline tests cover syntax/flag precedence, raw session branch lifecycle, static
guards, native CLI argument parsing, SDK registration and native OpenAI streams
with fetch/SSE stubs. Eligible real native warming receives the deliberate current
policy, including overlap/error/idle/slow-tool cases; no response-observer state
exists. See `tests/integration/automata/extensions/fast_mode_test.py`. Set
`PI_TEST_PACKAGE_ROOT` if installed Pi discovery fails. Package/install checks
cover both bundle files. No live access, pricing, latency or race-isolation claim.

Official references: [Codex speed](https://developers.openai.com/codex/speed/),
[API Fast mode](https://developers.openai.com/api/docs/guides/fast-mode).
