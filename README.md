# Automata

Local-first capabilities for AI agents: character, skills, shell tools and runtime
integrations. Detailed guidance and contracts live with their owning source files.

## Directory structure

```text
automata/
├── src/automata/          # Python package and bundled agent capabilities
│   ├── character/        # Identity, language and behavior components
│   ├── skills/           # Agent skills and their supporting references
│   ├── tools/            # Shell tools and their assets
│   ├── runtimes/         # Runtime-specific integrations
│   ├── install/          # Asset discovery and installation
│   └── plugin/           # Plugin export
├── tests/                # Software and capability verification
│   ├── unit/             # Isolated component tests
│   ├── integration/      # Checks across components and runtime boundaries
│   ├── cli/              # Command-line interface tests
│   ├── behavior/         # Agent behavior checks
│   └── tools/            # Tool-specific test suites and helpers
└── exams/                # Agent evaluation materials
    └── automata-harness/  # Knowledge and practical harness exams
```

The map treats `src/automata/` as the source root. Local environments, caches,
private state and task scratch are omitted.

License: [MIT](LICENSE).
