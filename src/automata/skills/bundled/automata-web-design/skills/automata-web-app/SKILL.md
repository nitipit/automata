---
name: automata-web-app
description: Use for web application routes, templates, frontend builds, project structure and development setup. Not for UI composition alone or browser automation.
---

# Automata Web Application

Build reproducible applications from maintained source. Respect existing stacks;
the bundled example starts new small apps, not migrations of working projects.

1. **Choose what runs where.** Server-rendered pages suit content/navigation;
   browser components suit local interaction, APIs suit backend operations. Keep
   authoritative state with its owner and verify actual effects, not displayed values
   or successful requests alone. Add no SPA/database/kernel/relay before needed.
   The example uses uv/Python, FastAPI/Jinja2 and Deno/esbuild with Adaptive UI;
   Deno builds, Python serves. UI contracts and agent messaging retain separate owners.

2. **Start from source.** Read `examples/webapp/README.md` for layout and commands.
   Use `scripts/create.py` to copy read-only installed examples into an approved
   destination; it refuses existing paths, binds Adaptive UI imports and installs/
   starts nothing. Use `--adaptive-ui` if the sibling is absent. Keep selected source
   paths available or intentionally package/publish them for independent shipping.
   Keep dependencies local and lockfiles maintained. Missing packages/runtimes need
   approval. The trusted example build has full Deno permissions and esbuild install
   scripts; these are not appropriate defaults for arbitrary downloaded code.
   Retain useful authorized setup and recheck it after layout/dependency changes.

3. **Structure for change.** Routes select explicit pages/assets, never source-tree
   mounts. Shared templates own structure, browser entries own initialization,
   components own behavior/CSS and native controls own basic constraints. Actual-data
   schemas may help; appearance needs no model. The example provides primitive tokens
   and Tokens/Typography/Components pages, not semantic modes. Rebuild generated
   bundles rather than editing them. Underscore filenames are not access control;
   keep private state outside served roots. Validate new API inputs and errors;
   assess authentication/CSRF/deployment before exposure beyond a local demo. Do not
   add network exposure or production infrastructure merely for convenient preview.

4. **Build and verify.** Build before static-mount server startup. Use owned loopback
   previews with shutdown paths. Backend reload, frontend rebuild and browser refresh
   differ; the example has no browser hot reload or input persistence across navigation.
   Check relevant types/build/routes and actual rendering, navigation, keyboard/focus
   and failures. Backend operations need effect and display checks. Claims of portability
   need copy/build outside the checkout. Report untested platforms/deployments and
   unfinished design instead of calling demos production-ready. Stop previews without
   deleting source/user data; cleanup requires its own authority.
