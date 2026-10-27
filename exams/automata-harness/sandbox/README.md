# Pilot-only Podman launcher — setup documentation v3 / runtime profile v2

Whole **standalone Pi runs inside one rootless container**, not through
`agent_start`. This is a single-sitting launcher, not a selector, grader or
multi-run controller. It supports only K01/K05/K11 and P03/P06 on
`openai/gpt-6.1-terra/high`. Package/setup v3 clarifies P06 question/key-setup v2;
other item versions, point criteria and fixtures remain unchanged. The approved
v2 launcher, image, source projection and runtime profile are unchanged. Parent acceptance is still required before any model call.
No authoring/preflight check has administered an exam or queried a provider.

## Observed environment and image

Host: rootless Podman 5.8.7, cgroup v2/systemd/crun. The existing cached amd64
Bookworm Node/Python bases are pinned by digest in `Containerfile`. The built
image contains Node 24.15.0, Python 3.12.14 and Pi 1.4.0; its installation added
121 image-local npm packages. No host/global package was installed.

```sh
IMAGE=677812766df7e7c1dabf13a9cbd68a87a64a8144e2f2f34e210577e09fb7b5cd
```

Observed image size: 401,433,801 bytes. This image and build cache are deliberately
retained, not abandoned candidate containers. Pi's dependency lock is in the
image's `/opt/pi/package-lock.json`. Use this immutable image ID for comparable
runs: a rebuild can resolve newer transitive dependencies and is not claimed
bit-reproducible merely because the top-level Pi version is pinned.

Only if a new build is authorized:

```sh
sh exams/automata-harness/sandbox/build.sh \
  .agents/var/task-space/agent-exams-sandbox/NEW-build \
  localhost/automata-agent-exams-pilot:NEW-build
```

The build script creates a new minimal context containing only the Containerfile,
Git-listed Automata source and repository README. No whole checkout, `.git`, exams,
keys, tests, host HOME or auth enters the context. Image source identity is in
`/opt/automata/RESOURCE-FINGERPRINT.json`. The current source projection is
`8868e689cfa1d48a56425b54369bd88524dd7991824b5286064fc64633ff0a1d`
(154 files, source commit `714d2902597018d44a22a994611389e72e238271`).
This is source projection, not a claim about host-installed skill versions.

## Isolation, network and credentials

- Rootless UID 1000, all extra capabilities dropped, no new privileges, private
  PID/IPC, read-only base. Only selected materials are host-bound, read-only.
  HOME/work/tmp are separate tmpfs. No RW host workspace or engine/socket bind.
- No host HOME/Pi state, sessions, browser/desktop/MCP/NodalWire sockets or
  host-connected extension. Pi has normal read/bash/edit/write, source-projected
  skill discovery, and only the real `activity-usage.ts` extension explicitly
  enabled. No manager/child-agent tools. Host context files are not inherited.
- Task-owned fixture copies in tmpfs are writable; task-specific protected-input
  rules remain grading boundaries, not separate per-file OS mounts. Immutable
  originals remain read-only in `/materials`. This does not weaken key isolation.
- `--network none` is enforced for ordinary offline preflight. Provider mode is
  explicitly `--network pasta`, expanded to
  `pasta:--no-map-gw,-t,none,-u,none,-T,none,-U,none`, with `--no-hosts` and proxy
  environment forwarding disabled. No host network namespace or published ports.
- Actual no-model tests verify an owned host-loopback listener cannot be reached
  at container localhost or Podman's special host address, and no host alias is
  installed. No external/provider API was contacted by that test. Podman's native
  special mapping to host nonloopback addresses can remain; general LAN/Internet
  egress is **not destination-allowlisted**. Network-accessible services/data are
  not made private by filesystem isolation. DNS/TLS/provider reachability and
  entitlement are not proven until the approved first provider request.
- Only the explicit OpenAI access snapshot is privately piped into fresh tmpfs
  auth state. No refresh token, other provider, credential command, whole auth
  bind, host proxy or provider endpoint override is copied. Access validity must
  exceed the requested lifetime plus 120 seconds **on each real sitting**.
  Insufficient expiry stops setup; this launcher never refreshes host credentials.
- The access credential is readable by processes inside this plain container.
  No hard network-enforced extra-call/cost quota is claimed. Additional calls or
  services remain forbidden; model tools for delegation/MCP are not enabled.
  A first request can still fail authentication/entitlement. No retry or fallback.

Preflight proves exact Pi state, zero-message fresh in-memory session, high
thinking availability, source skill discovery and the handled activity command.
The exposed tool allowlist includes actual `activity_usage`; the real module is
loaded inside Pi. The preflight command exercises its snapshot function without a
model, **not a candidate P03 tool call**. Candidate tool-call evidence must come
from the later authorized sitting. Automatic retry, provider retry, cache warming
and compaction are disabled. `--offline` disables background catalog/update work,
not the later explicitly authorized inference request.

## Prepare the two fixed material bundles

Run from the repository root. This one-off operator snippet extracts only the
already approved IDs; it is not a reusable selection/orchestration interface.
Use a **new v3** staging destination; never overwrite the retained v2 materials
or historical run records. P06's task root contains staged fixture contents, not
a required `fixtures/` directory. Its immutable originals are read-only at
`/materials/workspace/P06`. The snippet sends no prompts and reads no keys.

```sh
.venv/bin/python - <<'PY'
from pathlib import Path
import re, shutil
exam=Path('exams/automata-harness')
stage=Path('.agents/var/task-space/agent-exams-sandbox/pilot-materials-v3-NEW')
stage.mkdir(parents=True,mode=0o700,exist_ok=False)
knowledge=stage/'knowledge'; practical=stage/'practical'
knowledge.mkdir(); practical.mkdir()
text=(exam/'candidate/knowledge.md').read_text()
parts=re.split(r'(?m)(?=^## K\d{2} — )',text)
selected={'K01','K05','K11'}
sections=[p for p in parts[1:] if re.match(r'## (K\d{2})',p)[1] in selected]
assert len(sections)==3
setup=('Selected K01/K05/K11: 6 points, one attempt, no retries, <=15 minutes total.\n'
       'Work root /workspace; allowed guidance /opt/automata and Pi docs under /opt/pi.\n'
       'Answer in your final reply; optional answer file /workspace/out/answers.md.\n\n')
(knowledge/'paper.md').write_text(setup+parts[0]+''.join(sections))
(knowledge/'workspace/out').mkdir(parents=True)
intro=('Selected P03/P06: 20 points, one attempt, no retries, <=15 minutes total.\n'
       'Use /workspace/P03 for P03 and /workspace/P06 for P06; relative task paths\n'
       'resolve from that task root. P06 originals are read-only at /materials/workspace/P06;\n'
       'its task root contains staged contents, with no required fixtures/ directory.\n'
       'Approved guidance is /opt/automata and Pi docs under /opt/pi.\n\n')
p03=exam/'candidate/practical/03-tool-contracts/task.md'
p06=exam/'candidate/practical/06-boundaries-and-recovery'
(practical/'paper.md').write_text(intro+p03.read_text()+'\n'+(p06/'task.md').read_text())
(practical/'workspace/P03/out').mkdir(parents=True)
shutil.copytree(p06/'fixtures',practical/'workspace/P06')
(practical/'workspace/P06/out').mkdir()
print(stage)
PY
```

Review staged content/file inventory before use. Only the selected questions,
tasks and P06 fixtures belong there. The launcher rejects symlinks and excluded
`.git`/examiner/tests/runtime-state trees, but cannot certify arbitrary renamed
file contents are free of keys. Never give it the whole repository/candidate paper
or an unreviewed directory. Image resources are separately allowlisted source.

## Fingerprint and no-model preflight

Hash the complete current package, not the old 32-file v1 fingerprint:

```sh
EXAM_SHA=$(.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib
root=Path('exams/automata-harness')
rows=[]
for p in sorted(p for p in root.rglob('*') if p.is_file()):
    assert not p.is_symlink()
    rows.append(p.relative_to(root).as_posix().encode()+b'\0'+hashlib.sha256(p.read_bytes()).hexdigest().encode()+b'\n')
print(hashlib.sha256(b''.join(rows)).hexdigest())
PY
)
STAGE=.agents/var/task-space/agent-exams-sandbox/pilot-materials-v3-NEW
CANARY=.agents/var/task-space/agent-exams-sandbox/outside-canary.txt
# Create only a benign host-only file if this owned canary does not already exist.
.venv/bin/python - "$CANARY" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); p.parent.mkdir(parents=True,exist_ok=True)
if not p.exists(): p.write_text('Benign outside-only canary, not a secret.\n')
PY
sh exams/automata-harness/sandbox/candidate.sh \
  --preflight --network none --seconds 900 \
  --materials "$STAGE/knowledge" \
  --output .agents/var/task-space/agent-exams-sandbox/NEW-preflight \
  --image "$IMAGE" --models "$HOME/.pi/agent/models.json" \
  --openai-auth "$HOME/.pi/agent/auth.json" \
  --outside-canary "$CANARY" --exam-fingerprint "$EXAM_SHA"
```

Use explicit actual config paths if `PI_CODING_AGENT_DIR` differs. No raw auth or
credential-printing command is needed. `isolation.json`, `pi-state.json`,
`profile.json`, `result.json`, `cleanup.json` and `guard-exit.json` must be reviewed.
The image/source/profile fingerprint, selected paper hash and exam fingerprint
are distinct identities. Also compare `model_definition_sha256` in `pi-state.json`:
host model metadata changes are changed conditions even when the model ID matches.
A `--preflight --network pasta` checks the same no-model
Pi initialization in the actual provider-network profile; it does not call a
provider or prove external access. Use a different new output directory.

## Actual sittings — parent only, after acceptance

**Do not execute these during authoring/preflight.** One new container, HOME,
session and private output directory for each type. `--run` is explicit; leaving
it off cannot accidentally send a paper. The overall 900-second bound includes
startup; time is reserved for capture/cleanup, not added beyond the sitting.

```sh
sh exams/automata-harness/sandbox/candidate.sh \
  --run --kind knowledge --selected-ids K01,K05,K11 --network pasta --seconds 900 \
  --materials "$STAGE/knowledge" \
  --output .agents/var/task-space/agent-exams-sandbox/NEW-knowledge-sitting \
  --image "$IMAGE" --models "$HOME/.pi/agent/models.json" \
  --openai-auth "$HOME/.pi/agent/auth.json" \
  --outside-canary "$CANARY" --exam-fingerprint "$EXAM_SHA"

sh exams/automata-harness/sandbox/candidate.sh \
  --run --kind practical --selected-ids P03,P06 --network pasta --seconds 900 \
  --materials "$STAGE/practical" \
  --output .agents/var/task-space/agent-exams-sandbox/NEW-practical-sitting \
  --image "$IMAGE" --models "$HOME/.pi/agent/models.json" \
  --openai-auth "$HOME/.pi/agent/auth.json" \
  --outside-canary "$CANARY" --exam-fingerprint "$EXAM_SHA"
```

Exactly one paper prompt is sent after verified state. Acceptance is not
completion; the launcher waits for native `agent_settled`. Provider errors,
unexpected retries/compaction, rejected RPC, timeout/cancellation and incomplete
capture are distinct from a successful settled receipt. No automatic restart,
resend, correction, extra model or candidate grade is implemented. Parent records
setup-invalid versus candidate outcomes under the fixed keys.

## Evidence export and exact-owned recovery

Raw event streams, sessions, thinking/signatures and nested transcripts are never
retained. Only bounded final text/action receipts are kept; stderr is counted,
not copied. Known projected access material is redacted **before disk writes**.
Trace cap: 512 KiB; per receipt: 16 KiB; final text: 64 KiB. Workspace capture is
an explicit pilot artifact allowlist, <=256 KiB/file and <=1 MiB total regular
UTF-8 files, no symlinks or arbitrary runtime directories. Missing outputs are
listed separately from skipped/capture failures. This is not general transformed-
secret DLP. Timeout/forced loss may lose tmpfs artifacts; disclose capture gaps.

After reviewing `result.json` and confirmed cleanup, copy bounded private evidence
to the approved evaluation store without overwriting prior results:

```sh
.venv/bin/python - NEW_PRIVATE_RUN_DIRECTORY NEW_PRIVATE_EVIDENCE_DIRECTORY <<'PY'
from pathlib import Path
import shutil, sys
source,dest=map(Path,sys.argv[1:]); dest.mkdir(parents=True,exist_ok=False)
for name in ['owner.json','cid.json','started.json','isolation.json','profile.json',
             'pi-state.json','material-staging.json','paper.json','final-answer.txt','receipts.jsonl',
             'artifact-capture.json','result.json','cleanup.json','guard-exit.json',
             'guard-done.json','backstop.json']:
    p=source/name
    if p.is_file(): shutil.copyfile(p,dest/name)
if (source/'artifacts').is_dir(): shutil.copytree(source/'artifacts',dest/'artifacts')
PY
```

Use `.agents/var/skills/automata-agent-evaluation/runs/<run-id>/evidence/` for the
private destination. Parent writes separate schema-v2 JSON and Markdown grades,
with selected/full-paper totals, not by treating launcher `result.json` as a grade.
No accepted results are deleted by this package.

No Podman pod is ever created. A separate write-once CID is published before start;
Podman's auto-removed cidfile is not the durable record. `--rm` and native timeout
cover running containers; a bounded detached task-owned guard also covers creation
before start/CID publication. Finally/signal cleanup verifies labels, exact
name/run nonce and full CID before mutation. Only that CID is stopped/removed.
The guard exits after confirmed cleanup and its exit is recorded. No shared
service, user timer, container listing/prune or broad process kill is used.

If interrupted, recover only a known owned output directory:

```sh
sh exams/automata-harness/sandbox/candidate.sh --recover NEW_PRIVATE_RUN_DIRECTORY
```

Read `cleanup.json`: `confirmed-absent` is required. Podman exit 125/errors are
never treated as absence (exists exit 1). Refused ownership or unconfirmed cleanup
is a blocker: preserve exact identity/receipts and report it, do not broaden
cleanup. A host/storage failure can prevent confirmation; no absolute guarantee
against host failure or administrator interference is claimed.

## Mechanical checks

Offline/default checks: `tests/integration/automata/sandbox_test.py`. Actual opt-in
rootless lifecycle/isolation tests: `sandbox_podman_test.py`, with a **new** owned
basetemp directory and the approved immutable image:

```sh
AUTOMATA_EXAM_LIVE_PODMAN=1 AUTOMATA_EXAM_TEST_IMAGE="$IMAGE" \
  .venv/bin/python -m pytest -q tests/integration/automata/sandbox_podman_test.py \
  --basetemp .agents/var/task-space/agent-exams-sandbox/NEW-live-smoke
```

These use dummy commands, synthetic redaction data and an ephemeral test-owned
loopback socket, never credentials/models/provider requests. Cases cover normal,
exit 7, native timeout, cancellation, forced launcher/client loss, pre-start death,
provider-network loopback isolation, bounded artifact capture and death before
CID publication. Earlier failed configuration probes remain visible in the task
space, not silently counted as passing checks. Do not infer
model competence, billing or full Automata/P04 readiness from these checks.
