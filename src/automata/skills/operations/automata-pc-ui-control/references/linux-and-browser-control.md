# Linux and browser control

This is supporting knowledge, not a mandatory platform stack. Discover the relevant local
versions, protocols and permissions. The root skill owns authority, runtime state and acceptance.

## Input mechanisms

- Use `wtype` only after verifying compositor virtual-keyboard protocol support. A bounded
  empty-text invocation can test initialization without typing. Installation or `--help` is
  not readiness. An explicit unsupported-protocol error is evidence about that compositor,
  not proof that all desktop control is unavailable.
- `ydotool` needs a reachable `ydotoold` endpoint and usable input-device access. Inspect the
  client's actual configuration/error rather than assuming `/tmp` or a service name. The
  daemon may not be managed by systemd. Preserve “inactive or absent” as uncertainty unless
  a separate observation resolves it.
- Prefer targeted application, browser or accessibility APIs when they achieve the requested
  action more reliably. Native keyboard/mouse input is not necessary for every browser task.

## A temporary ydotoold

Within an authorized control task, a necessary bounded helper need not prompt again unless the
current envelope prohibits it. Check `ydotoold --help` and existing device access. Do not grant
permissions or register a system service merely to make a test pass.

A tested pattern is:

1. Create a private temporary directory and derive a short socket path inside it.
2. Launch an owned `ydotoold --socket-path=<path> --mouse-off` for keyboard-only work when
   those flags are supported. Preserve the daemon's default restrictive socket permissions.
3. Check that this process remains alive and its socket is ready. Allow the compositor to
   recognize the newly created virtual device; socket creation alone is not end-to-end proof.
4. Set `YDOTOOL_SOCKET` only for the intended client invocation. Revalidate target/focus,
   perform bounded input, and observe the actual field or UI result.
5. Keep the process only for authorized follow-up use. Otherwise terminate that exact owned
   process, wait for exit, and remove its disposable socket directory. Use `finally` or an
   equivalent lifecycle guard so failed tests also clean up.

A failed connection to a specific path establishes that attempt's failure, not that no daemon
exists anywhere. Do not reuse stale PIDs, change a global environment variable, or stop a
pre-existing service as a shortcut. An immediate exit zero from `ydotool` is still not proof
that the intended window received text.

## Chrome and native focus

There are several boundaries: compositor → browser window → content surface → widget.
Programmatic DOM `focus()` may leave the browser's address bar or another native window active.

Playwright's Chromium integration can enable focus emulation. Before using browser focus as
part of a global-input test, disable it for that page when supported:

```python
session = context.new_cdp_session(page)
session.send("Emulation.setFocusEmulationEnabled", {"enabled": False})
page.bring_to_front()
page.locator(target_selector).click()
```

This is a candidate procedure, **not a native activation guarantee**. In a live test an older
Chrome instance reported document focus even after disabling emulation, yet real input went
to a different owned test browser. Never rely on `document.hasFocus()` alone for global input.
Reconnecting through automation may change emulation state again; revalidate rather than
assuming a previous setting remains effective.

Supported native evidence can include window-manager/accessibility focus events or, in an
owned disposable Wayland browser, a compositor `wl_keyboard.enter` event for the identified
surface with no subsequent leave. Correlate that with the exact target and widget; do not use
an arbitrary old enter event, or assume one event identifies a browser with multiple windows.
Actual observed input remains the final acceptance test.

`WAYLAND_DEBUG=client` can expose protocol activity in a deliberately instrumented disposable
process, but logs may contain input, activation tokens and other sensitive data. Never turn it
on for ordinary user browsing. Extract only bounded non-sensitive evidence, stop the owned
process and discard raw logs. Instrumentation is optional, not a universal setup requirement.

## GNOME / Wayland activation

GNOME deliberately prevents arbitrary focus stealing. `xdg-activation-v1` is the supported
handoff: an appropriately activated client obtains a fresh token and passes it to the receiving
application, commonly through `XDG_ACTIVATION_TOKEN`. Tokens are transient capabilities, not
reusable setup data. GTK/GDK app launch contexts support this; available APIs vary by version.
Do not fabricate tokens, silently enable unsafe Shell evaluation, or install an extension to
bypass a denied introspection API.

A live test succeeded with an activated GTK4 launcher, a fresh isolated Wayland Chrome,
non-emulated content/widget focus, and an owned temporary ydotoold. The exact text appeared in
the intended field. This establishes that tested combination—not that the token alone caused
success or that every existing Chrome instance accepts activation. Repeated attempts to
activate an older retained instance did not establish a working route. Preserve that limit;
prefer a targeted API or a new owned instance only when the task allows that substitution.

AT-SPI is another candidate, not a guaranteed fallback. Query the session bus's
`org.a11y.Bus.GetAddress` and verify the returned endpoint. An obsolete X11 accessibility-bus
property or an application connected to an old bus can produce a stale connection. Do not
rewrite desktop properties, restart shared accessibility services, or enable global settings
without authority. A browser may expose only a skeleton accessibility tree unless configured
appropriately; absence of a target in one discovery attempt is not proof it cannot be controlled.

## Sources and evidence scope

- [GNOME: focus stealing prevention](https://blogs.gnome.org/shell-dev/2024/09/20/understanding-gnome-shells-focus-stealing-prevention/)
- [Wayland activation protocol](https://wayland.app/protocols/xdg-activation-v1)
- [Chromium: activation-token support](https://github.com/chromium/chromium/commit/157df64a85f40819b3e3e6de36bb4ca7c5b4ac51)
- [GTK/Glib activation integration](https://palant.info/2026/02/03/supporting-waylands-xdg-activation-protocol-with-gtk/glib/)

Local tests used GNOME/Wayland, Chrome 152, GTK and ydotool. Treat these as bounded observations;
verify current behavior and adapt rather than turning this host into a portable requirement.
