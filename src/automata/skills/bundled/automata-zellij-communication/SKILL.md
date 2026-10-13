---
name: automata-zellij-communication
description: Use for sending messages/replies through Zellij or diagnosing uncertain terminal delivery. Not for process lifecycle or task acceptance.
---

# Automata Zellij Communication

Deliver bounded terminal messages through an authorized route, not workflow authority.

1. **Establish a safe route.** Verify named session, explicit `terminal_N` pane,
   receiver and permission. Creation/assignment establishes ownership, not familiarity.
   When identity is unknown or changed, use that session's `action list-panes --json`;
   match numeric ID, `is_plugin: false`, command and CWD. Plugin IDs may share numbers.
   Verify a clear input field and no competing human input; shells/editors can execute
   or corrupt messages. Working-agent safety requires established queued input, not
   process presence. Prior idle/working Pi checks cover one sender with clear input,
   not concurrent writers or other interfaces. Replies need a safe reachable return
   route; one-way delivery needs none. Never inspect neighbors to find recipients.

2. **Send once, exclusively.** With one writer owning paste through submission:
   ```bash
   zellij --session "$RECEIVER_SESSION" action paste \
     --pane-id "$RECEIVER_PANE" "$MESSAGE" &&
   zellij --session "$RECEIVER_SESSION" action send-keys \
     --pane-id "$RECEIVER_PANE" "Enter"
   ```
   Both calls target the same pane; message is one bounded literal argument. Paste
   is neither submission nor guaranteed safe inbox. Verify the submit key/help when
   needed. Operations are not atomic or locked; do not send without exclusive writing.
   Different receivers are independent. Verified Enter does not establish other
   generated key combinations as equivalent to physical keyboard input.

3. **Interpret and recover.** CLI success means acceptance of operations, not receiver
   handling, understanding or task completion. Correlated acknowledgement supports
   receipt; capture alone is not returned delivery. Inspect owned-route evidence before
   retrying partial/interleaved sends; never blindly resend or poll. Pause on uncertain
   identity, readiness, return path or writer ownership. Do not dismiss prompts,
   switch focus or create workers to repair delivery.

4. **Reuse verified setup.** Keep useful methods/limits within authorized owner storage,
   separate from live recipients and requests. Recheck affected facts after restart
   or delivery failure; saved knowledge grants no sending authority. Installing this
   skill provides neither a transport tool nor recipient permission.
