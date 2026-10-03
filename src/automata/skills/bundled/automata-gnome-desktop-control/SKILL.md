---
name: automata-gnome-desktop-control
description: Use when viewing or controlling applications, windows, or pointer input on a Linux GNOME desktop.
---

# GNOME Desktop Control

Prefer direct app interfaces/launchers for app-specific tasks, AT-SPI for semantic
controls and accessible state, and the user-approved GNOME Remote Desktop portal
with ScreenCast for screen images and pointer/keyboard input on Wayland. AT-SPI
coverage may be incomplete. An alternative must actually support the task; otherwise
report the missing capability instead of substituting unverified input methods.

Reuse the owner's available helper/help and verified setup before rebuilding
connection mechanics. Check readiness, selected monitor, target, and focus; saved
handles are not current evidence. Check installed support before proposing installs.
See the [portal contract](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html)
when implementing or repairing the connection. Keep helpers/preferences with their
operational owner, not in packaged source without promotion approval.

Let the user approve sharing and request only needed devices/monitor. Keep ongoing
control sessions open across turns until stopped or their scope ends; close bounded
tests when finished. Capture on demand, not continuous recording by default. Track
live ownership/readiness and provide graceful stop; do not silently reconnect or
replay uncertain input. Sharing permission is not authority for unrelated actions.

Preserve image aspect ratio and map image pixels to the selected stream's logical
coordinates using current metadata. Verify actions through screen or accessible
state; command success or granted permission alone is not observed success.
