<section class="lesson">

## One service, explicitly addressed participants

The Message Router carries bounded JSON between browser pages and agent sessions.
Each participant connects to one central service with its own private credential.
A sender names a destination; the service checks permission and forwards the
message to that connected participant.

It is transport—not an agent launcher, a task manager, a shared transcript, or
proof that a recipient acted. Components and agents own the meaning of the payload
and the authority to act on it.

<protocol-diagram data-diagram="connections" aria-label="Physical connections: desk and viewer pages, worker and reviewer agents each connect to one central Router service. The service is not a participant."></protocol-diagram>

</section>

<section class="lesson">

## A connection is not a grant

Being online makes a participant reachable; it does not let that participant
initiate toward everyone else. A directed grant says who may **start** a message
toward whom. Here desk may start toward viewer or worker; worker and reviewer may
each start toward the other.

<protocol-diagram data-diagram="grants" aria-label="Initiation grants only, not physical connections: desk may start toward viewer and worker; worker and reviewer may start toward each other."></protocol-diagram>

A reply uses a capability tied to an existing request and its connections. It does
not require a reverse initiation grant and does not create one.

</section>

<section class="lesson">

## Start a message; choose whether a reply is needed

- **Initiation:** an allowed sender starts a new message to an explicit destination.
- **Optional reply:** a reply-capable request lets its recipient respond or reject
  using the exact delivered message ID. This is a return path, not a new independent
  initiation.
- **One-way:** `expectReply: false` creates no reply capability. The generic browser
  client supports this; the native Pi adapter ignores one-way messages rather than
  creating a model turn.

<div class="result">

**Forwarded ≠ handled.** Acceptance confirms forwarding, not application success.
Correlate the terminal reply when one is requested; an uncertain send must not be
blindly replayed.

</div>

</section>

<section class="lesson">

## Follow the reference

1. [Configure](./configure.html) private credentials and directed grants.
1. [Connect](./connect.html) the intended browser or agent clients.
1. [Discover](./discover.html) caller-visible, allowed destinations.
1. [Send](./send.html) independent requests, replies, and one-way messages.
1. [Handle failures](./failures.html) without confusing rejection, cancellation,
   and uncertain effects.

This site is a self-contained learning reference, not a dashboard or simulator.
Its diagrams and examples use a fixed illustrative topology; no page sends a
router message or reads live status.

</section>

<a class="next" href="./configure.html">Next: configure permissions →</a>
