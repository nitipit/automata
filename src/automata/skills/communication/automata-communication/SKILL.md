---
name: automata-communication
description: Use when repairing misunderstandings, aligning participants with different context, or shaping a consequential message or coordination signal.
---

# Automata Communication

Communication creates shared understanding between participants. It is a foundation for
cooperation, whether the participants are humans, agents, roles, teams, or future selves.

Core idea:

```text
Know yourself. Know others. Make shared context clear.
```

## Concept Anchors

### Know Yourself, Know Others

Before communicating, understand enough about both sides.

Know yourself:

- What role, position, or context am I speaking from?
- What am I trying to express or achieve?
- What do I know, assume, feel, need, or intend?
- What are my limits, responsibilities, or uncertainties?

Know others:

- Who am I communicating with?
- What do they likely know, need, value, or misunderstand?
- What burden, risk, or ambiguity might my message create for them?
- What response or next move would be easy and useful for them?

### 5W1H

Use 5W1H as a lightweight clarity lens, not a rigid form:

- **Who** is speaking, affected, responsible, or expected to respond?
- **What** is being said, asked, decided, changed, or unclear?
- **When** does it matter, and what timing or order affects it?
- **Where** does the context, work, evidence, or decision live?
- **Why** is this communication happening, and what purpose does it serve?
- **How** should the receiver think, act, respond, verify, or continue?

Use only the parts that reduce misunderstanding.

### Shared Context First

Communication fails when context is assumed but not shared. State the minimum context needed
for the other side to understand the message, without flooding them.

### Intent Before Content

Know why you are communicating before shaping the message. Acknowledgement, clarification,
decision, request, explanation, warning, and reflection need different shapes.

### Right Amount, Right Time

Too little context confuses. Too much context burdens. Choose the amount of detail that fits
the receiver, moment, risk, and next move.

### Name Uncertainty

Separate what is known, assumed, inferred, felt, or unknown when that distinction matters.
Clear uncertainty builds trust and prevents false confidence.

### Make the Next Move Clear

Good communication helps the receiver know what to do next. The next move may be to answer,
decide, wait, inspect, act, ask back, or simply understand.

## Context Signals

Use a context signal when a material observation, uncertainty, pressure, dependency, checkpoint,
or proposed next move may change shared understanding. Keep it human-readable and include only
the fields that help:

```text
sender: <role or session>
recipient/return path: <assigned receiver or exact return path>
kind: <descriptive signal kind>
evidence: <observed fact, source, or uncertainty>
impact: <what may change or be at risk>
request: <useful next move, if any>
context facts: <minimal facts needed for reassessment>
```

These fields are optional; omit unknown or irrelevant values rather than inventing them. `kind`
is descriptive, not a fixed enum or workflow. A signal is evidence for reassessment, not a
command, approval, state transition, or durable record. It may report runtime or agent-assessed
context pressure, but the receiver chooses the response. Prefer one concise signal for a material
change over repeated turn-by-turn status.

Workers send assignment reports and escalations through their assigned return path.
Peers within an authorized team may discuss, challenge proposals, and resolve shared
questions directly within their scope and access boundaries. Share enough context to
reason together, distinguish proposals from decisions, and surface consequential
conclusions or unresolved disagreements to the responsible manager. Discussion does
not authorize assigning work, changing ownership, or accepting another agent's results.
Respect explicit isolation restrictions; do not guess recipients or a missing return
path. New delegation still requires applicable authority. For signal-driven persistence,
route only accepted decisions or checkpoints through existing cue/session owners;
do not persist every signal.

## Boundaries

- Do not force every message into a template.
- Do not over-explain when a short acknowledgement or question is enough.
- Do not hide uncertainty when it materially affects understanding.
- Do not optimize only for the sender's convenience; consider the receiver's context too.
- Do not treat communication as manipulation. Aim for shared understanding and useful next
  movement.
