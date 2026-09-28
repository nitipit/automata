# Webboard example

A small board with a counter, local increment/reset buttons, and a notification
that the human can review and send to the assigned agent. The response is plain
text. The card is native HTML/CSS/JS, not a registered conversation component.

This is a reference/template. Its runtime copy is independent project content;
editing either copy does not update the other automatically.

## Provision and preview

From the repository root, choose an isolated absolute runtime:

```sh
export WORKSPACE_RUNTIME_ROOT="$(mktemp -d /tmp/workspace-example.XXXXXX)"
python src/automata/apps/workspace/provision_webboard.py \
  "$WORKSPACE_RUNTIME_ROOT/northstar/main/web"
```

The helper copies only `index.html`, `board.css`, and `board.js`. It refuses an
existing destination or symlink ancestor. It does not build/start the app, create
credentials, connect an agent, or change any existing board. Use a trusted
operator-owned destination; if a copy fails, preserve/review the partial directory
rather than overwriting it.

Follow the app [build/run guide](../../README.md#build-and-run) for shell assets
and preview setup. The current host maps only `project-northstar` / `main` to
`northstar/main/web`; copying elsewhere does not register another board.
Opening the HTML standalone can demonstrate the counter, but agent sharing needs
its Workspace host and an explicitly connected assigned agent. The board receives
no credentials and cannot directly access parent state. Sharing requires a second,
host-owned confirmation; it does not post into a conversation.

See [sandbox and event authority](../../README.md#sandbox-and-event-authority)
for the protocol and limits. The iframe is not a complete network/resource jail.

## Isolated browser verification

Pass this source directory as `WORKSPACE_BOARD_SEED` to the app's existing
`tests/apps/workspace/browser_acceptance.py` recipe. That exercises the counter,
host confirmation, mock reply, mobile layout, and isolation without a real agent.
Do not use a live browser/profile or project database as the test fixture.
