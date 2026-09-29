# Workspace concept

The previous implementation was retired because its code organization did not
meet the project's maintainability standard. This concept remains valid, but no
replacement implementation is approved. Existing private conversations, webboards
and runtime data are retained separately; retirement does not authorize deleting
or replaying them.

Workspace is a flexible place for humans and agents to work together, not a fixed
workflow. These are development principles, not a finished architecture or a
claim about what the current prototype supports.

A project can have multiple webboards and conversations. Conversations and
artifacts need not be tied to one webboard; they can be used across webboards
as the work requires.

Context engineering is central:

- Each interaction should carry its project and, when applicable, webboard and
  conversation context, along with who acted and what they referred to.
- Capture where an event happened at the time it happened. Its origin may differ
  from the target of a requested action.
- Make relevant context available without automatically sending all history to
  every agent. Distinguish what exists from what an agent actually received.
- Keep identity, order, provenance and access boundaries clear. Context alone is
  not permission to act.

The app provides reliable context and flexible ways to collaborate. Humans and
agents decide what to do with it. Keep the detailed structure open as we develop.
