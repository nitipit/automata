---
name: automata-web-app
description: Use when developing a web application's routes, templates, frontend build, project structure or development setup. Includes a runnable Python/TypeScript webapp example; not UI composition alone or general browser automation.
---

# Automata Web Application

Make web applications reproducible from maintained source, with explicit boundaries
between backend state, rendered pages and browser assets. Respect an existing stack;
use the bundled example as a starting point for a new small application, not a mandate
to migrate working projects.

## Choose what runs where

Use server-rendered pages for content and navigation when they suffice. Add browser
components for local interactions and API calls for operations requiring backend state.
Keep authoritative data on its owner; a displayed value or successful request is not
proof that an operation completed. Avoid introducing a SPA, database, persistent kernel
or message relay before the task needs one.

The example combines uv-managed Python, FastAPI/Jinja2 pages, Deno-driven esbuild and
Adapter-based components from Adaptive UI. Deno is build tooling here; Python serves
HTTP. UI composition and component contracts belong to Adaptive UI, not this skill.
Use its maintained foundation rather than implementing another component framework.
Agent-connected messaging is a separate integration, not a property of this web stack.

## Start from a maintained project

Inspect `examples/webapp/README.md` for setup, source layout and verified run/check
commands. Resolve paths against this skill directory. Installed assets are read-only:
copy the example into an approved project/task directory with `scripts/create.py`.
The helper refuses existing destinations and binds imports to the selected Adaptive
UI source; it does not install dependencies or start services. Use `--adaptive-ui`
when the sibling skill is absent. Keep that dependency path available; for independent
shipping, deliberately package or publish the shared library rather than leaving a
host-specific source alias unnoticed.

Keep uv/Deno dependencies local and lockfiles with source. Obtain approval for missing
dependencies and runtimes. Inspect build permissions: the example runs trusted build
code with full Deno permissions and allows esbuild's install script. Do not treat these
permissions as appropriate for arbitrary downloaded code. Retain useful verified setup
recipes when they avoid rediscovery; recheck them after dependency or layout changes.

## Structure for change

- Routes explicitly select templates and public assets; do not mount the source tree.
- Shared templates own page structure; shared browser entries own initialization.
- Component code owns behavior and concrete CSS; native controls own basic input
  constraints. Actual-data schemas can be useful, but appearance needs no model.
- The example exposes primitive color/effect/spacing/shape/typography values, not
  a semantic role or mode system. It has Tokens, Typography and Components pages;
  see `examples/webapp/README.md` for design references and limits.
- Generated bundles, dependency trees and environments stay separate from maintained
  inputs. Rebuild from source rather than editing output.

An underscore filename is an organizational convention, not access control. Keep
credentials and private state outside served roots. For new APIs, validate inputs,
report errors explicitly and consider authentication/CSRF and deployment requirements
before exposing a local demonstration to other hosts. Do not add network exposure or
production infrastructure merely to make a preview convenient.

## Develop and verify

Build before starting a server whose static mount requires generated output. Use
loopback for local previews and identify process ownership and shutdown. Backend reload,
frontend rebuild and browser refresh are different operations; the example has no
browser hot reload; local example input is not persisted across navigation.

Check types/build, route responses and the rendered page. Exercise a relevant browser
interaction, navigation, keyboard/focus behavior and failure states. For backend
operations, verify both server-side effect and displayed result. Test copying and
building outside the source checkout when claiming portability. Report unsupported
platforms, untested deployment paths and unfinished design choices rather than calling
a runnable demo production-ready. Stop previews without deleting project source or
user data; cleanup needs its own authority.
