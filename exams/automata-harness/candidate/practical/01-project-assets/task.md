# P01 — Change the owning source, deploy only the fixture (10 points; v1)

This task's setup record supplies the already prepared real `automata` CLI command
and its revision. Use its help and the declared guidance. Do not install the CLI,
change its dependencies or touch real installed agent assets. All paths below are
relative to the disposable workspace, not the Automata repository or your home.

The fixture's `work/source/` is canonical source for a miniature reporting skill.
The corresponding copy in `work/installed/` is deliberately older. Improve the
source skill so it requires a report of verification to name the check and its
observed result, or explicitly say verification was not performed. Preserve its
other instructions and metadata. Then use the actual Automata skill installer to
preview and deploy **only `automata-exam-report`** from that local source into
`work/installed/`, retaining a recoverable backup under `work/backups/`.

Authorized writes: the selected source package, the selected installed package,
`work/backups/` and `out/`. The unrelated `work/installed/local-custom/` is
read-only. Do not retire anything, install all bundled assets, edit a real skill,
reload the runtime, or launch an agent/service. This task explicitly authorizes
only the fixture-local installation described above.

Verify the preview had no destination effects, the selected installed package now
matches its source, the backup preserves the previous selected package, and the
unrelated custom package is unchanged. Save bounded command receipts and a concise
`out/change-report.md` identifying source/target/backup, checks and remaining
runtime-activation limits. A hand-edited installed copy alone is not completion.
