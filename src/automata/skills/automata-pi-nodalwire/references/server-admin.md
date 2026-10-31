# Optional relay and administration operations

Read only for an authorized server, inspection, administration or migration task.
This reference grants no authority to install, start services or mutate policy.
The Pi bridge and Node SDK have no admin API; use the published Python **0.3.0**
CLI/API (Python **3.12+**). Check `nodalwire --help`, `serve --help` and
`admin --help` in the intended environment before acting. Exact contracts live in
[upstream administration](https://github.com/keenlycode/nodalwire/blob/v0.3.0/src/docs-src/reference/admin/index.html),
[configuration](https://github.com/keenlycode/nodalwire/blob/v0.3.0/src/docs-src/reference/config/index.html)
and [migration notes](https://github.com/keenlycode/nodalwire/blob/v0.3.0/RELEASE_NOTES.md).

## Explicit startup, readiness and shutdown

- Reuse a suitable approved relay; do not start one merely because this skill was
  loaded. Start only on demand for approved active use, not as an automatic service.
  Record the owner, process handle, actual endpoints and bounded lifetime.
- Supply a strong private `NODALWIRE_ADMIN_TOKEN` through an approved protected
  environment, or use a private config with `admin_verifier`. Never print/read back
  secrets or put bearer values in command arguments, prompts, logs or task reports.
  Disable shell tracing. Network join credentials and admin credentials are distinct.
  An environment token overrides the configured verifier; an invalid override fails.
- Start explicitly with `nodalwire serve`, or `nodalwire serve --config /approved/relay.toml`.
  A custom v2 TOML can set `config_version = 2`, `endpoint` and `admin_endpoint`.
  Both endpoints must be loopback; choose approved unoccupied ports, not a shared
  relay's ports. Defaults are data 5555/admin 5556, not permission to use them.
  Without a config path, administrative changes are memory-only.
- Observe the bound endpoint and `serving` status, then verify the intended relay
  using an authorized bounded read below. A live process/open socket alone proves
  neither readiness nor admin authentication. For messaging readiness also confirm
  the recipient is connected and has membership; the Pi bridge needs open `default`.
  A protected default can admit a client without allowing sends.
- On completion, stop only the owned relay: Ctrl-C for its foreground process or
  orderly signalling via the retained owned handle. Await exit and confirm owned
  listeners are absent; escalate only against a verified still-owned process.
  Never stop another owner's relay. Remove ephemeral secrets by their retention
  policy; do not remove shared configuration or credentials.

## Safe read-only inspection

Use the separately approved **admin endpoint** and an already supplied credential.
These are read operations, not peer discovery authority or authenticated identities:

```sh
nodalwire admin config.get --endpoint "$ADMIN_ENDPOINT"
nodalwire admin network.list --endpoint "$ADMIN_ENDPOINT"
nodalwire admin network.get --network default --endpoint "$ADMIN_ENDPOINT"
nodalwire admin member.list --network default --endpoint "$ADMIN_ENDPOINT"
```

The default credential variable is `NODALWIRE_ADMIN_TOKEN`; `--token-env NAME`
selects another variable by name, never its value. Reads omit expected revision.
`config.get` redacts bearer values/verifiers; still treat routing/policy/member
results as task-private. Do not inspect private config or environment files to
recover a missing credential. Report missing access to its owner instead.

Equivalent Python API: `async with await AdminClient.connect(admin_endpoint,
token=admin_token) as admin:` followed by `await admin.call("network.list")` or
`await admin.call("member.list", {"network": "default"})`, importing `AdminClient`
from `nodalwire`. Obtain endpoint/token through approved protected inputs.
`connect` opens transport only; a successful call authenticates. Calls return
`AdminReceipt(revision, result)`; serialize one bounded call at a time and close
the owned client. Do not dump client objects or credentials.

## Administrative changes require separate explicit approval

Before any mutation, agree on the exact relay, network/member, intended policy,
persistence and impact. Read current state and revision first. CLI mutations need
`--expected-revision REVISION` with the observed integer; Python uses
`admin.call(op, args, expected_revision=current.revision)`. Reads reject this field.
Use official operations rather than editing live verifier/config files:

- `network.create`: `--network`; omit credential for open, or use
  `--credential-env NAME` for protected.
- `network.update`: `--network` and explicit `--protected`/`--no-protected`;
  new protection needs a credential. `network.rotate` needs network and a new
  credential variable. Python argument objects use `network`, `protected`,
  `credential`; pass the credential value only in memory.
- `network.delete`: `--network`, nondefault only. `member.remove`: `--network`
  and `--member NAME` (Python key `name`). Removal is ephemeral and does not
  increment config revision; it still requires the current expected revision.
- `admin.rotate`: `--credential-env NAME`; configuration-managed only.
  Environment-managed admin authority must be changed by its lifecycle owner,
  not bypassed. The new credential authenticates subsequent calls.

With `serve --config`, commits rewrite the same regular file, losing comments/
formatting; protect/back up it within authority first. Without it, changes vanish
on shutdown. Rotation/protection affects future joins, not existing memberships;
removal cannot recall accepted messages. On revision conflict, reconsider intent.
On timeout/cancellation or `persistence_indeterminate`, preserve the unknown outcome,
read/reconcile deliberately and report; never automatically reconnect/retry/replay
or claim no effect. A successful receipt is not proof of downstream work.

## Coordinated migration and rollback

Stop old messaging applications/relay under their owners' approval. Upgrade the
relay and **every** messaging peer to 0.3.0 together: NWM3 cannot mix with 0.2.x
AR2. NA1 administration and `config_version = 2` are unchanged; no automatic
config conversion is needed. Pi application envelope v2 and tool arguments stay
unchanged. External clients remove NWR1 codecs; payloads are raw bytes, native
`id`/`reply_to` carry correlation, and `send`/`reply` return accepted ID strings.
Regenerate old saved CLI message-event inputs before using 0.3 reply commands.

Prepare the extension's locked dependencies and native ZeroMQ with authority;
start a **fresh Pi process**, not just `/reload`, which may retain imported
external/native modules. Verify actual package versions, recipient membership
and bounded no-provider-I/O messaging before reopening approved traffic. No
model-backed wake trial or automatic replay is implied. Retain previous artifacts
and a protected config backup for an approved coordinated rollback: stop all new
messaging peers/relay, restore matching old artifacts/config, then restart them
together. Do not pair old clients with a new relay or replay uncertain messages.
