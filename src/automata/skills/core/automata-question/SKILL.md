---
name: automata-question
description: Use when a consequential or ambiguous question needs clear choices, consent scope, or stable answer references.
---

# Automata Question

Shape questions so the user can understand what decision is needed and answer with little
friction. Ask only when the response materially affects the next move; stop once there is
enough context to use judgment.

## Identify the Response

Understand the intended response before wording the question. Common intents include:

- clarification or open discovery;
- selection, preference, priority, trade-off, or scope;
- confirmation of shared understanding;
- authorization, consent, or permission to proceed;
- acceptance, rejection, or revision of completed work;
- diagnostic evidence, recovery choice, ownership, timing, or focused feedback.

Treat these as useful distinctions, not labels that must appear in the conversation.
Confirmation verifies understanding; it does not authorize action. Permission to proceed
covers only the action and scope named in that question. Acceptance of a result does not also
authorize a commit, installation, push, deletion, or other next action unless stated. Use
explicit consent when privacy, accounts, external effects, destructive actions, or other
material consequences are involved.

## Make the Answer Clear

Ask a direct open question when free-form context is needed; do not force options that would
constrain the discussion. For a single confirmation with one clear action or proposition,
ask a short yes/no question without unnecessary numbering.

When presenting alternatives, put each answer option on its own numbered line so the user can
reply with just a number. Number the answers, not merely the question, even when there is only
one question. Do not bury alternatives inside a question or paragraph. State whether the user
should choose one, choose any that apply, rank the options, or add a free-form answer.

For several independent questions, number the questions and use nested choice references such
as `1.1`, `1.2`, `2.1`, and `2.2`. Keep those references stable during follow-up discussion;
do not reuse a number for a different meaning.

Make options concrete and distinguishable. Name material consequences where they affect the
decision, include an `Other` path when the options are not exhaustive, and mark a recommendation
when useful without disguising it as the only valid choice. Avoid ambiguous `yes` or `no` when
several proposals or actions are in view; name what would be confirmed or authorized.

Ask one unlocking question at a time when later questions depend on its answer. Group a small
set of independent questions when that reduces unnecessary turns. Do not turn exploration into
an interrogation or ask the user to decide details that can safely remain adaptive.

## Boundaries

This skill owns the clarity, response shape, and stable references of explicit questions. It
does not decide the underlying product policy, safety threshold, plan, or action authority.
Do not force ordinary acknowledgements or low-intent conversation into numbered choices, and
do not expose internal question-type labels unless they help the user respond.
