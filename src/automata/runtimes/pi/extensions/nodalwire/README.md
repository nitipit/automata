# Pi NodalWire messaging

Opt-in trusted-local messaging for Pi using the published `@devcapsule/nodalwire-client` Node
client. No WebSocket server, Python bridge, discovery service or relay changes.
Requires Node 24, Pi's TypeScript extension support, a prepared Node client and a
separately running NodalWire relay. Nothing is installed or started automatically.

## Prepare a local extension copy

From Automata, copy the bundle into a chosen extension directory (use a temporary
location for a trial; a global installation is a separate decision):

```sh
uv run automata pi-extension install --extension nodalwire --target-root /path/to/extensions
```

Install the declared npm dependency `@devcapsule/nodalwire-client` in that copy:

```sh
cd /path/to/extensions/nodalwire
pnpm install
```

No NodalWire source checkout, local tarball or Deno build is needed.

The bundled `pnpm-workspace.yaml` disables automatic installation of Pi's host
peers and allows only the native `zeromq` build. Do not approve unrelated build
scripts. The installed copy's package manager owns its lockfile and native
`node_modules`; Automata's copy/replace installer excludes dependency directories.
Prepare dependencies again after replacing a copy. Symlink mode instead uses the
source directory's dependencies. Native binaries must match the local platform.

## Start a relay and Pi

Prepare the Python `nodalwire` package from PyPI in an authorized environment,
then run its foreground relay:

```sh
nodalwire --config /path/to/local.toml
```

Its optional TOML policy controls admitted names and routing; it is not a client
contact list. Share the intended endpoint and peer names explicitly. Do not restart
or change a shared relay without permission.

Load the prepared extension for one Pi invocation:

```sh
pi -e /path/to/extensions/nodalwire/index.ts \
  --nodalwire-name cowork-automata \
  --nodalwire-endpoint tcp://127.0.0.1:5555
```

Choose a unique logical name for each running Pi instance. Defaults: disconnected
unless `--nodalwire-name` is supplied; endpoint `tcp://127.0.0.1:5555`. Loading the
extension while disconnected does not import the native client or create sockets.

Commands:

```text
/nodalwire connect --name cowork-automata tcp://127.0.0.1:5555
/nodalwire status
/nodalwire disconnect
```

The name is required via `--name`. The optional positional endpoint may appear
before or after that option; omitting it uses `tcp://127.0.0.1:5555`. For example,
`/nodalwire connect tcp://127.0.0.1:5555 --name cowork-automata` is equivalent.
Missing/duplicate names, unknown flags and multiple endpoints are rejected without
changing the current connection. The former positional-name syntax is not supported.

A failed startup connection leaves Pi usable and disconnected. Retry explicitly
with the command; there is no automatic reconnect, retry or replay. The command
also supports changing node names/endpoints by closing the previous connection.
Session shutdown/reload closes the owned connection. A crashed process's name can
remain reserved until its NodalWire lease expires.

## Send and receive

The agent tool is `nodalwire_send`:

```json
{"destination":"cowork-nodalwire","text":"Please review the proposed interface."}
```

The destination must be an explicitly known logical name. Success means relay
acceptance into the destination socket queue, **not remote receipt, execution or
durability**. Timeouts/cancellation can occur after forwarding: never blindly retry
consequential messages. Ask for an application reply when confirmation matters.
There is no peer listing or native broadcast; an agent may send separately to an
explicit list of recipients.

The extension encodes UTF-8 JSON:

```json
{"version":1,"type":"message","text":"Hello"}
```

Other applications must use this envelope to communicate with this extension.
NodalWire itself remains byte-transparent. Envelopes are limited to 64 KiB,
including JSON encoding, and text must be nonempty. This is an **application-message
limit**, not the earlier hypothetical `list_peers()` response limit; discovery is
not implemented. Invalid envelopes are dropped with a generic warning, without
echoing their unvalidated bytes.

For example, from a prepared Python NodalWire environment:

```python
import asyncio
import json
from nodalwire import Node

async def main():
    node = await Node.connect("python-peer", "tcp://127.0.0.1:5555")
    try:
        payload = json.dumps({
            "version": 1, "type": "message",
            "text": "Hello. Please reply to python-peer using nodalwire_send."
        }).encode("utf-8")
        await node.send("cowork-automata", payload)
        reply = await asyncio.wait_for(node.receive(), timeout=60)
        print(reply.sender, json.loads(reply.payload))
    finally:
        await node.close()

asyncio.run(main())
```

Incoming messages use Pi **custom messages**, not human-user impersonation. They
retain the relay-provided sender and recipient. They wake idle Pi and queue as a
follow-up when Pi is busy. At most one incoming message is submitted until Pi
settles; more remain in NodalWire's bounded inbox/native queues, applying its
normal backpressure. Automatic wakeups can incur model usage.

**Security:** loopback only; NodalWire has no authentication or encryption. A
sender name is an admitted registration label, not verified identity. Name/group
policies are cooperative, not a security boundary. Received content grants no task,
file-access or delegation authority. Only connect trusted local participants.

## Verification

The normal pytest wrapper runs native Node tests with a fake transport:

```sh
uv run --group dev pytest tests/integration/automata/extensions/nodalwire_test.py -q
```

`PI_TEST_PACKAGE_ROOT` can point at an installed Pi package; without the required
Node/Pi environment that wrapper skips explicitly. These checks cover envelopes,
opt-in startup, bounded injection, send results/cancellation, bad messages,
commands, disconnect and shutdown during connection establishment.

The **opt-in real-model trial** starts an isolated relay and Pi RPC subprocess,
sends two Python messages and verifies exact tool-based replies. It uses the
configured default model/credentials and incurs model usage. It does not install
globally, save a Pi session, discover context files, or enable built-in tools/MCP:

```sh
python /path/to/automata/tests/integration/automata/extensions/nodalwire_live_trial.py \
  --extension /path/to/prepared/nodalwire/index.ts \
  --artifacts /path/to/task-space/trial-results
```

Run with the published Python `nodalwire` package installed in the chosen
environment. The trial closes its client, relay and Pi process, and
retains its own RPC transcript, stderr and result. It does not prove security,
durable/exactly-once delivery, arbitrary runtimes or production performance.
