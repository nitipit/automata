# Web UI Starting Directory Guide

This web-stack example maps tokens → components → pages/scenes to files. Pages
can use both components and tokens directly. Use it to suggest placement and
discuss missing decisions, not as a mandatory scaffold. Reuse existing project
equivalents; create only what the approved work needs.

```text
project/
├── web/                       # Source web root
│   ├── ui/
│   │   ├── tokens/
│   │   │   ├── color.ts        # Shared colors
│   │   │   ├── space.ts        # Spacing values
│   │   │   ├── shape.ts        # Shape values, such as corner radii
│   │   │   ├── typography.ts   # Typography values
│   │   │   ├── effect.ts       # Shadows and elevation effects
│   │   │   └── motion.ts       # Animation durations and easing
│   │   └── components/
│   │       ├── base.ts         # AdapterCSS Base Web Component
│   │       └── button.ts       # Example Web Component extending base
│   ├── _base.ts               # Shared page behavior
│   └── _base.css.ts           # Shared page styles
└── dist/                      # Generated build output
```

- **Tokens** are shared design values authored in `.ts` or `.js` modules.
- **Components** own reusable structure and behavior. AdapterCSS connects styling
  to the component's contract; establish what the base provides rather than infer
  an API from its name. `button.ts` is illustrative, not a required replacement
  for a native HTML button. Keep component styling with its owner.
- **Pages** and their entry points can be added directly under `web/`. `_base.ts`
  and `_base.css.ts` hold shared behavior and styles, not a required HTML-template
  system. Establish how `.css.ts` becomes browser-applied CSS before implementing.
- **Build** with esbuild when suitable; reuse an established build system otherwise.
  Discuss page entry points, HTML delivery and style handling if unresolved.
  `web/` holds maintained inputs; `dist/` holds generated output and is not edited
  as source. Configure intended public output explicitly: a source web root does
  not mean every source file should be browser-accessible.

Asset organization and detailed component APIs or build recipes are outside this
starting guide. No external design system is required.
