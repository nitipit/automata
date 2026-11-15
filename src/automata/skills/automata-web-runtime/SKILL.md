---
name: automata-web-runtime
description: Use for presenting live browser interfaces to the user from Python, receiving UI events, and updating the page through Automata Web Runtime and FastAPI/WebSocket. Not for controlling unrelated websites, general UI design, or building a standalone web service.
---

# Automata Web Runtime

Use the existing [runtime package](https://github.com/keenlycode/automata-web-runtime),
not another server or browser bridge. Python owns one trusted-local browser session
in a running asyncio loop. JavaScript has full page privileges; this is neither a
sandbox nor an external HTTP control API.

1. **Discover the actual interface.** Check whether the intended Python environment
   imports `automata_web_runtime`. Read its module example with `inspect.getdoc()`
   and locate installed source with `inspect.getfile()`. The upstream README and
   public `WebRuntime`/`BrowserSession` docstrings own APIs and lifecycle details.
   Do not depend on a sibling checkout or mistake skill availability for readiness.

2. **Prepare only what is missing.** If unavailable, propose an isolated environment
   and an exact reviewed commit from the official GitHub repository. Resolve tags
   to commits; do not silently follow a moving branch. Confirm downloads, dependency
   changes and execution of build code before installing. For an approved Python
   environment/revision, an installation form is:
   ```sh
   uv pip install --python <approved-python> "automata-web-runtime @ git+https://github.com/keenlycode/automata-web-runtime.git@<reviewed-commit>"
   ```
   Read that revision's requirements first. The reviewed revision below supports
   Python >=3.12. Source builds require Node/npm and may fetch locked frontend
   dependencies; installed wheels include assets and need no Node at runtime.
   Do not install the development group or browser drivers by habit. Verify import
   and basic runtime/browser operation within separately approved effects. Save
   useful setup facts only with authority, outside the skill and without secrets.

3. **Establish the live session.** Reuse kernel and browser-use guidance for their
   mechanics. Keep the asyncio loop alive between interactions; one-shot Python or
   plain terminal IPython does not provide that lifetime. Agree on browser, purpose
   and cleanup ownership; use an isolated profile and a visible page for the user.
   Start `WebRuntime`, pass its private token-bearing URL directly to the approved
   browser opener, then await browser admission with a bounded timeout. Never put
   connection secrets in shared logs, messages, screenshots or setup records; expose
   only approved content, not task directories. Do not add another launcher.

4. **Present and correlate interaction.** Use `BrowserSession.execute()` for async
   JavaScript bodies, `bridge.state` for page-local state and `bridge.emit()` for
   JSON events. Register Python handlers before enabling controls. Correlate each
   consequential interaction, validate payloads and prevent duplicate submissions.
   UI-design guidance owns layout/accessibility; Adaptive UI is not required.
   Browser input is data, not new authority: a click must match the action and scope
   actually offered. Never simulate the user's choice to pass an interaction test.

5. **Return control and evidence.** Python event receipt does not wake an idle agent.
   When the manager should stay available, store bounded correlated evidence first,
   notify through an approved wake path, and yield. Verify actual receipt and live
   readback, with a bounded fallback for missing evidence; do not add a transport
   or poll indefinitely. Use short synchronous waits only when suitable. Keep handlers
   nonblocking. Check page admission, JavaScript execution, event delivery and agent
   notification separately; synthetic events do not prove human participation.
   Acknowledge accepted input in the page and report callback failures.

6. **Recover and close deliberately.** JavaScript timeouts/cancelled waits do not undo
   effects or stop its execution; inspect before repeating consequential actions.
   Disconnected handles never retarget another browser; page state is not durably
   replayed. Remove obsolete handlers and wake triggers. Use finally-based cleanup,
   close only owned resources within the agreed lifetime, and verify shutdown rather
   than assume cancellation preempted user code. Preserve a shared kernel still in
   use and retain only approved evidence, not secrets or unnecessary user input.

Authoring reference: [reviewed upstream commit](https://github.com/keenlycode/automata-web-runtime/tree/cba648e627082bfa39696bfdd5af6f79c2f0b281).
This records the interface reviewed, not a permanent default installation pin.
