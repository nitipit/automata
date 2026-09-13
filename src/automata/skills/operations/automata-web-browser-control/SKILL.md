---
name: automata-web-browser-control
description: Use when setting up or controlling a real browser with Python Playwright, Chrome CDP, Firefox WebDriver BiDi via puppeteer-core, headless/headful automation, persistent browser sessions, or step-by-step interactive browsing.
---

# Automata Web Browser Control

Control a real browser through the smallest reliable automation path. Prefer Python
Playwright for Chromium/Chrome, especially ad-hoc commands through
`uv run --with playwright python ...`. Use `puppeteer-core` with WebDriver BiDi when Firefox
control is requested and that is the better fit.

## Operating Style

- Act as the browser operator: translate the user's request into one focused browser action,
  run it, report the result, then wait.
- Treat browser and interaction tools as convenient paths, not capability limits. When a
  tool cannot support the intended action, choose another safe browser-control path or offer
  to improve the tool rather than constraining the task to its current interface.
- Recommend a better next step when the current path is limited, but keep steps small and
  reversible.
- Be interactive when setup choices affect privacy, persistence, install state, profile
  choice, or user control.
- Confirm ambiguous targets, account actions, payments, destructive actions, credentials,
  form submissions, package installs, file creation, persistent browser launches, and use of
  real/default profiles.

## Setup

Diagnose only what is needed for the requested control path:

- `uv` and ad-hoc Python Playwright availability for Chromium/Chrome
- Node/package-manager and `puppeteer-core` availability for Firefox WebDriver BiDi
- browser executable, existing CDP/WebSocket endpoint, or launch capability
- headless/headful display constraints
- whether persistence or a managed terminal session is useful

For ad-hoc browser control, prefer temporary runtime locations outside the repository, such
as `/tmp/automata-browser-<hex>/`, generated at runtime. Use stable or named temporary
locations only when the user wants a reusable session. Do not add browser-control
dependencies to the repository unless the project itself needs them.

Verify the chosen connection and intended browser/profile ownership before recording setup
as working. Executable presence alone is not a successful connection. Report the working stack
concisely: automation library, browser, protocol, profile/data-directory type,
endpoint/session/process name, and how future actions can reconnect.

On reuse, check only changeable prerequisites: the endpoint still reaches the intended browser,
profile and ownership still match, and the requested target is available. Treat recorded
coordinates as hints to verify, not permanent identity. Recover only the affected setup within
existing authorization; ask before new installations, profile changes, or broader repairs.

## Profile and Session Choice

- For Chrome/Chromium, always use an isolated automation profile/session. Do not use the
  user's real/default Chrome profile.
- For Firefox, ask whether to use the default Firefox profile/session or an isolated
  automation profile/session, then launch with WebDriver BiDi support.
- Never silently switch between isolated and real/default profiles.
- Do not assume modern Chrome/Chromium can be automated through the default user data
  directory with remote debugging. Use a custom `--user-data-dir`, Chrome for Testing, or
  another isolated setup.
- Keep a persistent browser alive only when useful. Otherwise prefer short-lived commands
  that connect, act, report, and disconnect.

## Persistent Visible Browsers

When a visible browser should stay available across turns, use the terminal multiplexer
workflow if available. Prefer a managed session such as `tmux` with a descriptive name and a
matching isolated profile or confirmed Firefox profile choice. Report the session name,
profile directory, endpoint/port, URL, and log or PID details. Do not create unmanaged
background browsers or reuse profiles, ports, or sessions from another task without
confirmation.

## Control Strategy

Choose the simplest reliable path for the environment:

- Connect to an existing Chromium CDP endpoint with Python Playwright when available.
- Launch or attach to Chromium/Chrome with an isolated profile when no endpoint exists and
  persistence is useful.
- Use Playwright persistent-context APIs when Playwright should own the profile.
- For watched headful Chromium/Chrome, prefer native window sizing such as `no_viewport=True`
  when applicable.
- For Firefox control, prefer Node `puppeteer-core` with WebDriver BiDi over command-line URL
  opening. Treat `firefox --new-tab` as a fallback or one-off launch action, not full control.
- Use headful mode when the user wants to watch or participate; use headless mode for
  background automation, scraping, tests, or screenshots.
- Treat raw CDP as a fallback for simple actions. Prefer Playwright for multi-step
  interaction, locators, forms, downloads, screenshots, and repeated browser operation.
- Use screenshots when needed to understand the page or finish the task.

Typical action loop:

1. connect to the browser/context/page,
2. perform one focused action,
3. print useful state such as title, URL, visible result, screenshot path, or error,
4. disconnect or keep the browser according to the agreed setup.

## Safety and Privacy

- Do not enter credentials, submit forms, buy items, delete data, or change account settings
  without explicit instruction.
- Do not read cookies, localStorage, sessionStorage, passwords, form values, account data, or
  full page text unless explicitly requested or necessary for the confirmed task.
- Ask before extracting full page text, saving page content, or inspecting sensitive pages.
- Avoid storing sensitive browser content unless the user asks.

## Recovery

If an action fails, inspect only enough state to diagnose the issue, explain the likely cause
briefly, and propose the next small step. If setup changed or a fallback was used, report
exactly what changed.

## Boundaries

- Do not generate UI components, application code, or visual assets.
- Do not install packages, create files, launch persistent browsers, or use real/default
  profiles without confirmation.
- Do not inspect or store sensitive browser data unless explicitly requested or necessary for
  the task and confirmed.
