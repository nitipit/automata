import json
from pathlib import Path, PurePosixPath

import yaml

PACKAGE_ROOT = Path(__file__).parents[3] / "src" / "automata"
SKILLS_ROOT = PACKAGE_ROOT / "skills"
TOOLS_ROOT = PACKAGE_ROOT / "tools"
TOOL_MAPPING_KEY = "automata-tools"
CORE_SKILLS = {
    "automata-agents-md",
    "automata-agent-design",
    "automata-task-design",
    "automata-adaptive-ui",
    "automata-codex-imagegen",
    "automata-question",
    "automata-context-status",
    "automata-context-compaction",
    "automata-pi-sessions",
    "automata-delegation",
    "automata-cue",
    "automata-time-awareness",
    "automata-team-management",
    "automata-plan",
    "automata-skill-design",
    "automata-setup",
    "automata-timer",
}


def test_worklog_skill_is_not_bundled() -> None:
    assert not list(SKILLS_ROOT.rglob("automata-worklog"))


def test_bundled_skill_files_have_valid_frontmatter() -> None:
    skill_names: set[str] = set()
    for skill_file in SKILLS_ROOT.rglob("SKILL.md"):
        frontmatter = parse_frontmatter(skill_file)
        skill_dir = skill_file.parent

        assert set(frontmatter) >= {"name", "description"}, skill_file
        assert isinstance(frontmatter["name"], str), skill_file
        assert frontmatter["name"].strip(), skill_file
        assert frontmatter["name"] == skill_dir.name, skill_file
        assert frontmatter["name"].startswith("automata-"), skill_file
        assert frontmatter["name"] not in skill_names, skill_file
        skill_names.add(frontmatter["name"])
        assert isinstance(frontmatter["description"], str), skill_file
        assert frontmatter["description"].strip(), skill_file


def test_agents_md_skill_keeps_additional_instruction_location_contextual() -> None:
    text = find_skill_file("automata-agents-md").read_text()

    assert "appropriate skill-owned agent-data location" in text
    assert "use the generator's supported discovery mechanism" in text
    assert ".agents/var/skills/automata-agents-md/" not in text


def test_adaptive_ui_skill_owns_runtime_and_promotion_boundaries() -> None:
    skill_file = find_skill_file("automata-adaptive-ui")
    frontmatter = parse_frontmatter(skill_file)
    text = skill_file.read_text()
    normalized = " ".join(text.casefold().split())

    assert frontmatter["description"] == (
        "Use when generating, previewing, updating, reconnecting to, or promoting a live "
        "Adaptive UI."
    )
    assert "metadata" not in frontmatter
    for term in (
        "reuse and reconnect to a matching session",
        "discover its website root from existing setup",
        "treat installed source as read-only",
        "outside the public website root",
        "lib/example/index.html",
        "lib/example/reactive-shadow.html",
        "lib/example/chat-with-agent.html",
        "inspect only relevant examples and component contracts",
        "adapt rather than copy blindly",
        "reuse available catalog components",
        "use `base` for component boundaries",
        "adapter for component styles",
        "arrow for instance-local reactive state",
        "register components before mounting templates",
        "outgoing payload, expected reply contract, validation, and interaction state",
        "single source of truth",
        "does not redefine their schemas or conflate pending states",
        "ownership is logical",
        "adapt single-component examples",
        "keep local interactions local",
        "transport carries complete json independently of component semantics",
        "approval before fetching missing assets or installing runtimes",
        "scripts/build.py --help",
        "separate website root for experiments",
        "verify the rendered ui and relevant interactions",
        "full reloads do not guarantee transient-state preservation",
        "reflect accepted changes in session source",
        "establish process ownership and cleanup",
        "does not authorize deleting pages, histories, or evidence",
        "promote reusable components only with user approval",
        "not by patching installed copies",
        "not general browser control, installation, image generation, or transport",
        "arrow and shadow dom are not security sandboxes",
    ):
        assert term in normalized, term
    assert len(text) < 4000
    assert "build-and-preview.md" not in text
    assert ".agents/var/skills/automata-adaptive-ui/" not in text
    assert not (skill_file.parent / "references" / "build-and-preview.md").exists()


def test_agent_data_skill_defines_owned_storage_default() -> None:
    skill_file = find_skill_file("automata-agent-data")
    text = skill_file.read_text()

    assert ".agents/var/skills/<skill-name>/" in text
    assert ".agents/var/tools/<tool-name>/" in text
    assert "This skill governs data used by agent capabilities" in text
    assert "not application, source, project,\nor user data" in text
    assert "Follow an explicit agent-data convention" in text
    assert "Outside a repository context, ask" in text


def test_agent_evaluation_skill_covers_runtime_behavior() -> None:
    skill_file = find_skill_file("automata-agent-evaluation")
    frontmatter = parse_frontmatter(skill_file)
    text = skill_file.read_text()
    normalized = " ".join(text.casefold().split())

    assert frontmatter["description"] == (
        "Use when behaviorally evaluating an agent's runtime behavior with fresh sessions, "
        "realistic scenarios, boundary checks, and observable evidence."
    )
    assert "# Automata Agent Evaluation" in text
    assert "The\nsubject may be a new or changed skill" in text
    for term in (
        (
            "require direct verification of the first subject's actual cwd, model/effort, "
            "discovered source or installation, and isolation boundary"
        ),
        "before launching remaining scenario probes",
        "if runtime identity differs from the contract, stop remaining launches",
        "allow normal read-only discovery of applicable instructions, skills, and capabilities",
        "a prompt that prohibits such inspection cannot establish activation failure",
        "classify it as a harness confound/failure or inconclusive",
        "fully bounded synchronous-return run contract",
        "record both watchdog paths as `not applicable — bounded synchronous return`",
        "supported worker-to-coordinator and coordinator-to-user watchdog paths",
        "including the user-visible notification path",
        "mandatory for asynchronous or persistent subjects",
        "agent under test separate from the evaluator",
        "whether scored results will be retained and their owner-scoped destination",
        "follow `references/scoring.md`",
        "start from `templates/evaluation-record.json`",
        "do not count harness or environment failures as agent-ability history",
    ):
        assert term in normalized, term
    assert len(text) < 8_000


def test_agent_evaluation_scoring_contract_is_reusable() -> None:
    skill_root = find_skill_file("automata-agent-evaluation").parent
    scoring = (skill_root / "references" / "scoring.md").read_text()
    normalized_scoring = " ".join(scoring.casefold().split())
    template = json.loads((skill_root / "templates" / "evaluation-record.json").read_text())

    for term in (
        "`activation`",
        "`judgment`",
        "`capability_use`",
        "`outcome`",
        "`boundaries`",
        "`recovery`",
        "`0`: absent",
        "`1`: partially correct",
        "`2`: correct without repair",
        "critical gates separate from numeric scores",
        "defaulting to 80 percent",
        "passed runs over valid scored runs",
        "arithmetic mean percentage",
        "minimum percentage",
        ".agents/var/skills/automata-agent-evaluation/runs/",
        "one valid json record per completed `pass`, `fail`, or genuine `inconclusive` run",
        "a harness or environment failure is not an agent-ability score",
        "do not maintain one growing json array",
    ):
        assert term in normalized_scoring, term

    assert template["schema_version"] == 1
    assert template["rubric"]["threshold_percent"] == 80
    assert template["criteria"][0]["maximum"] == 2
    assert template["critical_gates"][0]["status"] == "PASS"
    assert template["score"] == {"earned": 2, "maximum": 2, "percent": 100.0}
    assert template["verdict"] == "PASS"


def test_context_status_skill_covers_checkpoint_and_signal_modes() -> None:
    skill_file = find_skill_file("automata-context-status")
    frontmatter = parse_frontmatter(skill_file)
    text = skill_file.read_text()

    assert frontmatter["name"] == "automata-context-status"
    assert "# Automata Context Status" in text
    assert frontmatter["description"] == (
        "Use when interpreting runtime context signals or checking context pressure, "
        "elapsed time, or model-token usage."
    )
    assert "silently creates a task checkpoint" in text
    assert "`context_status` remains an optional manual diagnostic" in text
    assert "latest Pi input message" in text
    assert "hidden context signal" in text
    assert "## Read status" in text
    assert "do not automatically delegate, stop, or change ownership" in text


def test_context_compaction_skill_preserves_state_before_native_execution() -> None:
    skill_file = find_skill_file("automata-context-compaction")
    frontmatter = parse_frontmatter(skill_file)
    text = skill_file.read_text()
    normalized = " ".join(text.casefold().split())

    assert frontmatter["description"] == (
        "Use when an agent or user is considering intentional Pi context compaction after "
        "context-pressure observations, long-running work, or a stable task boundary."
    )
    for term in (
        "request intentional compaction only when measured context usage exceeds 75%",
        "pressure sets urgency and task boundaries determine timing",
        "compact automatically at the next stable boundary, before substantial new work",
        "at ≥90%",
        "earliest safe boundary",
        "fresh measurement showing usage above 75%",
        "time, long output, or a new work phase alone is not enough",
        "without asking for per-use confirmation",
        "bring existing, authorized task state current",
        "do not create records solely for compaction",
        "do not mark unfinished work complete",
        "compaction does not finish, accept, cancel, or transfer active work",
        "sole final tool action when practical",
        "only after `agent_settled`",
        "brief focus notes, not a hand-written summary or a substitute for durable state",
        "do not route `/compact` through tmux",
        "do not retry automatically",
        "does not change pi settings, measure context",
    ):
        assert term in normalized, term

    assert len(text) < 3_000


def test_pi_sessions_skill_requires_exact_cwd_and_recoverable_cleanup() -> None:
    text = find_skill_file("automata-pi-sessions").read_text()

    for term in (
        "exact Pi runtime current working directory (CWD)",
        "recorded session ID is the primary identity",
        "`pi_session_list`",
        "short-lived listing receipt",
        "does not prove that a session is owned, finished, or closed",
        "`pi_session_trash`",
        "clear removal request or prior scoped authorization",
        "does not itself authorize removal",
        "bind each number to an exact full session ID",
        "not positions in a refreshed list",
        "does not detect sessions open in another",
        "a new receipt alone does",
        "at most 100 sessions",
        "does not fall back to permanent deletion",
        "Do not use raw paths, `rm`, `unlink`",
    ):
        assert term in text


def test_team_management_skill_defines_progress_reporting_contract() -> None:
    text = find_skill_file("automata-team-management").read_text()
    normalized = " ".join(text.casefold().split())

    for term in (
        "one or more delegated children",
        "only the root manager sends consolidated status to the user",
        "non-root manager aggregates direct-child evidence and reports to its direct parent",
        "aggregate progress",
        "build estimates from direct-child evidence",
        "report at meaningful transitions or an agreed reporting deadline",
        "supporting evidence, material risks, and the next useful move",
        "use the recipient's required format",
        "a blocked report is relative",
        "at a non-root node",
        "at the root",
        "aggregate progress",
        "manager-loss reporting climbs parent-by-parent",
        "non-root nodes do not bypass their direct parent to report to the user",
    ):
        assert term in normalized, term

    assert "exactly one canonical `status`" not in normalized

    assert "every delegated execution" not in normalized
    assert "10–20 minutes" not in normalized
    assert "otherwise keep presentation natural and concise" in normalized
    assert "peers within an authorized team may collaborate directly" in normalized
    assert "without separate approval for ordinary discussion" in normalized
    assert "never transfers management authority" in normalized
    assert "peers cannot assign each other work or expand scope" in normalized
    assert "surface material decisions and unresolved disagreements" in normalized
    assert "respect isolation restrictions; do not contact unrelated agents" in normalized
    assert len(text) < 8000


def test_team_management_recognizes_redesign_and_enacts_authorized_transitions() -> None:
    text = find_skill_file("automata-team-management").read_text()
    normalized = " ".join(text.casefold().split())

    for term in (
        "changed scope, dependencies, context needs, availability",
        "task design owns the proposed arrangement and transition",
        "management supplies current evidence and enacts authorized changes",
        "launch, replacement, and rebalancing need no per-worker approval",
        "user or parent's visibility of material changes",
        "apply redesign through bounded assignments and verified ownership transfers",
        "delegation owns the transfer mechanics",
        "keep active work and cleanup accounted for",
        "preserve manager accountability and direct-parent boundaries",
    ):
        assert term in normalized, term
    assert "must always separate" not in normalized


def test_team_management_skill_owns_adaptive_visibility_and_dialogue_priority() -> None:
    text = find_skill_file("automata-team-management").read_text()
    normalized = " ".join(text.casefold().split())

    for term in (
        "one or more direct children",
        "adaptive user/parent visibility",
        "visibility appropriate to duration, risk, milestones, and recipient needs",
        "reporting commitments distinct from worker-evidence deadlines",
        "neither requires polling",
        "next meaningful evidence drives asynchronous work",
        "synchronous work needs no watchdog",
        "user/parent reports are separate",
        "keep each direct child's next evidence",
        "watchdog current",
        "users/parents do not watch workers",
        "when expected evidence is overdue or a concrete failure needs diagnosis",
        "one bounded passive observation",
        "explicitly owned direct child",
        "relevant artifact or message",
        "pane/process metadata",
        "capture diagnostic output once",
        "observation is diagnosis, not a way to wait for completion",
        "activity or output is not completion or acceptance",
        "preserve the agreed callback and watchdog",
        "active user or parent alignment",
        "preserve and queue ordinary child evidence",
        "until a stable boundary",
        "urgent safety",
        "time-sensitive consequences",
        "invalidated active scope",
        "blocker needing immediate input",
        "manager availability supports clarification",
        "design discussion, progress interpretation, and course correction",
    ):
        assert term in normalized, term


def test_team_management_skill_defines_envelopes_and_recovery_contract() -> None:
    text = find_skill_file("automata-team-management").read_text()
    normalized = " ".join(text.casefold().split())

    for term in (
        "direct-parent management only",
        "missing `depth` = `0`",
        "missing `child_limit` = **no children**",
        "equal-or-narrower",
        "parent approval",
        "never transfers management authority",
        "pause new work",
        "preserve completed",
        "replacement",
        "reparent",
        "closure",
        "manager loss is distinct from missing worker evidence",
        "cleanup owner",
        "planning owns",
        "applicable `agents.md` files own",
        "delegation owns each caller-to-worker handoff",
        "result review, acceptance, and cleanup",
        "timer, model, and transport skills own",
    ):
        assert term in normalized, term


def test_delegation_skill_owns_handoff_and_no_polling_contract() -> None:
    text = find_skill_file("automata-delegation").read_text()
    normalized = " ".join(text.casefold().split())

    assert "exact return path" in text
    for term in (
        "verify exact runtime identifiers when availability is uncertain",
        "model and supported thinking settings match the agreed assignment",
        "task design owns selection judgment",
        "report mismatches and obtain approval before substituting outside the agreed choices",
    ):
        assert term in normalized, term
    assert "Prefer tmux for\ndelegated agent or persistent worker communication" in text
    assert "explicitly owned detached worker session" in text
    assert "exact\nworker target and return pane" in text
    assert "agreed return-capable transport or bounded synchronous execution" in text
    assert "dispatch + coordinator-targeted watchdog notice" in text
    for term in (
        "for asynchronous delegated work, use an event-driven sequence",
        "pair each asynchronous dispatch with one bounded watchdog",
        "bounded synchronous delegated execution returns directly",
        "does not require a communication watchdog",
        "hard process or time limit",
        "separate safety backstop",
        "not a watchdog or callback",
    ):
        assert term in normalized, term
    assert "end the current agent turn" in text
    assert "watchdog notice begin the next coordination turn" in normalized
    assert "normal completion trigger" in normalized
    for term in (
        "address its notice to the coordinator's wakeable input, not to the worker",
        "ending the turn leaves the session available for callbacks",
        "do not keep the turn open with sleep calls",
        "constrain additional discovery to authorized paths",
    ):
        assert term in normalized
    assert "Keep completed evidence" in text
    assert "initial result, and any resend" in text
    assert "original return path" in text
    assert "responsible coordinator's wakeable input" in text
    assert "leaving the recovery decision to that coordinator" in text
    assert "On notice, the coordinator" in text
    assert "Process or pane observation is bounded diagnosis" in text
    assert "when evidence is overdue or a concrete failure needs investigation" in normalized
    assert "Task design owns proposed responsibilities, context ownership, and transitions" in text
    assert "planning owns work decomposition and acceptance criteria" in text
    assert "Applicable `AGENTS.md` files own" in text
    assert "`automata-" not in text


def test_delegation_skill_supports_adaptive_visibility() -> None:
    text = find_skill_file("automata-delegation").read_text()
    normalized = " ".join(text.casefold().split())

    for term in (
        "set intermediate evidence and deadlines from duration, risk, dependencies",
        "workers report meaningful changes through the agreed return path",
        "do not substitute periodic activity reports for useful evidence",
        "keep evidence timing contextual",
        "a callback may queue during active dialogue",
        "still-needed asynchronous watchdog transport becomes unsafe or unavailable",
        "establish an agreed replacement before removing coverage",
        "canceling stale delivery must not silently leave active work unwatched",
    ):
        assert term in normalized, term
    assert "manager visibility around 10 minutes" not in normalized


def test_delegation_keeps_assignment_updates_bounded() -> None:
    text = find_skill_file("automata-delegation").read_text()
    normalized = " ".join(text.casefold().split())

    for term in (
        "accepted decisions made during ongoing alignment with a user or parent",
        "explicit bounded assignment updates with the same correlation",
        "state changed scope, evidence, and eta",
        "for asynchronous delegated work, re-arm the watchdog",
        "revised next meaningful evidence",
        "avoid concurrent manager edits to worker-owned files",
    ):
        assert term in normalized, term
    assert "ongoing manager/user discussion" not in normalized


def test_tmux_transport_does_not_poll_for_completion() -> None:
    communication = find_skill_file("automata-tmux-communication").read_text()
    background = find_skill_file("automata-tmux-background").read_text()

    assert "Do not poll for responses" in communication
    assert "Observed pane output is not a received reply" in communication
    assert "## Results and Acceptance" not in communication
    assert "watchdog" not in communication.casefold()
    assert "uv run --script .agents/tools/tmux-message/tmux_message.py send --help" in communication
    assert "not as a mandatory step before every" in communication
    assert len(communication) < 4000
    assert "sleep`-and-poll loop" in background


def test_tmux_transport_requires_safe_async_receiver() -> None:
    text = find_skill_file("automata-tmux-communication").read_text()
    normalized = " ".join(text.casefold().split())

    for term in (
        "ownership does not prove receiver readiness",
        "submitted text can execute in a shell or interfere with a user typing",
        "confirm the receiver can safely accept input",
        "does not resolve application prompts or provide a safe asynchronous inbox",
        "verified queue-capable path",
        "do not blindly dismiss prompts or inject into a busy editor",
        "when a reply is expected, establish a reachable, safe return path",
        "never guess it from nearby panes or session names",
        "one-way delivery needs no manufactured return path",
        "do not blindly duplicate a message",
    ):
        assert term in normalized, term


def test_question_skill_distinguishes_response_intent_and_authority() -> None:
    text = find_skill_file("automata-question").read_text()
    normalized = " ".join(text.casefold().split())

    for term in (
        "consequential or ambiguous question",
        "clear choices, consent scope, or stable answer references",
        "clarification or open discovery",
        "selection, preference, priority, trade-off, or scope",
        "confirmation of shared understanding",
        "authorization, consent, or permission to proceed",
        "acceptance, rejection, or revision of completed work",
        "diagnostic evidence, recovery choice, ownership, timing, or focused feedback",
        "confirmation verifies understanding; it does not authorize action",
        "permission to proceed covers only the action and scope named",
        "acceptance of a result does not also authorize a commit",
        "explicit consent when privacy, accounts, external effects, destructive actions",
        (
            "does not decide the underlying product policy, safety threshold, plan, or "
            "action authority"
        ),
    ):
        assert term in normalized, term


def test_question_skill_makes_response_targets_clear_without_interrogation() -> None:
    text = find_skill_file("automata-question").read_text()
    normalized = " ".join(text.casefold().split())

    for term in (
        "ask a direct open question when free-form context is needed",
        "do not force options that would constrain the discussion",
        "ask a short yes/no question without unnecessary numbering",
        "put each answer option on its own numbered line",
        "reply with just a number",
        "number the answers, not merely the question",
        "do not bury alternatives inside a question or paragraph",
        "choose one, choose any that apply, rank the options, or add a free-form answer",
        "use nested choice references",
        "`1.1`, `1.2`, `2.1`, and `2.2`",
        "do not reuse a number for a different meaning",
        "include an `other` path when the options are not exhaustive",
        "mark a recommendation when useful",
        "avoid ambiguous `yes` or `no`",
        "ask one unlocking question at a time",
        "group a small set of independent questions",
        "do not turn exploration into an interrogation",
        "do not force ordinary acknowledgements or low-intent conversation into numbered choices",
    ):
        assert term in normalized, term

    assert "do not add numbering when only one question or choice" not in normalized
    assert len(text) < 5000


def test_software_development_skill_uses_modular_assurance() -> None:
    text = find_skill_file("automata-software-development").read_text()

    assert "## Modular Assurance" in text
    assert "composable activities rather than a fixed" in text
    for level in ("Direct", "Focused", "Independent", "Full"):
        assert f"**{level}**" in text
    assert "full-suite run by default" in text
    assert "scope, expected evidence, and non-goals clear" in text
    assert "not as a routine presentation template" in text


def test_bundled_skills_do_not_ship_provider_specific_metadata() -> None:
    assert not list(SKILLS_ROOT.rglob("openai.yaml"))


def test_core_skills_are_bundled() -> None:
    bundled = {path.parent.name for path in SKILLS_ROOT.rglob("SKILL.md")}

    assert CORE_SKILLS.issubset(bundled)


def test_bundled_skills_do_not_ship_runtime_state_dirs() -> None:
    assert not list(SKILLS_ROOT.rglob("config"))
    assert not list(SKILLS_ROOT.rglob("generated"))


def test_declared_skill_tool_mappings_resolve_to_bundled_entries() -> None:
    for skill_file in SKILLS_ROOT.rglob("SKILL.md"):
        text = skill_file.read_text()
        _, _, body = text.split("---\n", 2)
        frontmatter = parse_frontmatter(skill_file)

        for runtime_path in parse_tool_mappings(frontmatter, skill_file):
            path = PurePosixPath(runtime_path)
            assert path.parts[:2] == (".agents", "tools"), skill_file
            assert len(path.parts) >= 4, skill_file
            assert ".." not in path.parts, skill_file
            assert runtime_path in body, skill_file
            assert "src/automata/tools" not in body, skill_file

            source_entry = TOOLS_ROOT.joinpath(*path.parts[2:])
            assert source_entry.is_file(), source_entry


def test_bundled_skills_document_boundaries() -> None:
    for skill_file in SKILLS_ROOT.rglob("SKILL.md"):
        assert "\n## Boundaries\n" in skill_file.read_text(), skill_file


def test_removed_autonomy_and_role_packages_are_not_bundled() -> None:
    assert not list(SKILLS_ROOT.rglob("automata-roles/SKILL.md"))
    assert not list(SKILLS_ROOT.rglob("automata-next-improvement/SKILL.md"))


def test_estimation_skills_and_references_are_not_bundled() -> None:
    for name in ("automata-time-estimation", "automata-token-estimation"):
        assert not list(SKILLS_ROOT.rglob(name))
        for skill_file in SKILLS_ROOT.rglob("SKILL.md"):
            assert name not in skill_file.read_text(), skill_file
    assert not list(SKILLS_ROOT.rglob("calibration-records.md"))


def test_skill_install_is_consolidated_into_setup() -> None:
    assert not list(SKILLS_ROOT.rglob("automata-skill-install/SKILL.md"))
    for skill_file in SKILLS_ROOT.rglob("SKILL.md"):
        assert "automata-skill-install" not in skill_file.read_text(), skill_file


def test_cue_skill_uses_skill_owned_agent_data() -> None:
    text = find_skill_file("automata-cue").read_text()

    assert ".agents/var/skills/automata-cue/cues.md" in text
    assert "Cue owns anchor selection, retrieval, and maintenance" in text
    assert ".agents/cues.md" not in text
    assert ".agents/roles/" not in text
    assert "active role" not in text


def test_plan_owns_work_and_summarizes_team_design_without_dispatch() -> None:
    text = find_skill_file("automata-plan").read_text()
    normalized = " ".join(text.casefold().split())

    for term in (
        "owns work decomposition, dependencies, constraints, and acceptance criteria",
        "task design owns responsibility distribution",
        "delegation owns handoff readiness",
        "management owns active coordination",
        "adapt within agreed scope without asking again",
        "seek approval before exceeding authority",
        "rather than duplicating their procedures",
        "planning does not require a team or a separate plan document",
    ):
        assert term in normalized, term
    assert "Ask before launching any agent" not in text
    assert "Design temporary agent responsibilities" not in text


def test_skill_design_supports_modularity_and_contextual_composition() -> None:
    text = find_skill_file("automata-skill-design").read_text()
    normalized = " ".join(text.casefold().split())

    for term in (
        "stand independently within its scope and compose through context",
        "activation cues, inputs, outputs, and ownership boundaries",
        "not mandatory invocation chains",
        "let the agent decide which capabilities to combine",
        "do not make one skill orchestrate its neighbors",
        "dependencies only where a concrete interface, handoff, or safety boundary needs them",
        "keep one coherent scope",
        "split independent responsibilities, not every subtopic",
    ):
        assert term in normalized, term


def test_skill_design_shortens_wording_without_losing_meaning() -> None:
    text = find_skill_file("automata-skill-design").read_text()
    normalized = " ".join(text.casefold().split())
    for term in (
        "remove filler, repeated ideas, and unnecessary qualifiers",
        "preserving conditions, exceptions, and authority boundaries",
        "prefer clarity over the shortest text",
        "avoid cryptic abbreviations",
        "preserve intended decisions, not word count alone",
        "moving always-read prose does not reduce context cost",
    ):
        assert term in normalized, term


def test_skill_design_keeps_approved_execution_and_checks_proportionate() -> None:
    text = find_skill_file("automata-skill-design").read_text()
    normalized = " ".join(text.split())
    for term in (
        "approved changes and verification without repeated permission",
        "Ask before exceeding scope",
        "Discussion alone does not authorize mutation",
        "check changeable prerequisites when evidence warrants it",
        "wording tests alone do not establish agent behavior",
        "Replace or remove overlapping guidance",
    ):
        assert term in normalized, term
    assert "without discovery or preflight scans" not in text
    # Review threshold for the expanded design contract, not a quality measure.
    assert len(text) < 8_000


def test_skill_design_uses_ownership_before_location() -> None:
    text = find_skill_file("automata-skill-design").read_text()

    assert "Identify ownership before location" in text
    assert "applicable owner-scoped data convention" in text
    assert "generator implement concrete discovery paths" in " ".join(text.split())


def test_skills_keep_internal_process_out_of_routine_presentation() -> None:
    skill_design = find_skill_file("automata-skill-design").read_text()
    assert "internal decisions separate from user-visible presentation" in skill_design


def test_routing_and_align_are_not_bundled() -> None:
    for name in ("automata-action-routing", "automata-align"):
        assert not list(SKILLS_ROOT.rglob(f"{name}/SKILL.md"))


def test_planning_assignment_sizing_and_handoff_context_have_distinct_owners() -> None:
    contracts = {
        "automata-plan": (
            "the goal gives direction; the plan is a provisional route toward it",
            "coherent outcomes and their dependencies, not a rigid worker-sized task list",
        ),
        "automata-task-design": (
            "coherent, verifiable outcomes",
            "manageable working context",
            "not arbitrary task counts, file counts, or token limits",
            "splitting would duplicate reasoning",
            "context benefit outweighs briefing, handoff, and integration costs",
            "smaller assignments are not automatically more efficient",
        ),
        "automata-delegation": (
            "provide sufficient context, not the whole conversation",
            "include essential facts directly",
            "supporting material for selective reading",
            "pointers are accessible within the worker's authorized context",
            "brevity must not hide information needed to act correctly",
            "revisit its boundary with task design rather than merely shortening the brief",
        ),
    }
    for name, terms in contracts.items():
        normalized = " ".join(find_skill_file(name).read_text().casefold().split())
        for term in terms:
            assert term in normalized, (name, term)


def test_plan_is_contextual_and_preserves_execution_boundaries() -> None:
    text = find_skill_file("automata-plan").read_text()
    normalized = " ".join(text.casefold().split())
    for term in (
        "clear, bounded work does not need a formal plan",
        "work decomposition, dependencies, constraints, and acceptance criteria",
        "discussion does not itself authorize implementation or delegation",
        "working hypothesis, not a fixed script",
        "keep later steps coarse until evidence makes detail useful",
        "constraints come from goals, authorization, and real dependencies—not speculative steps",
        "irreversible actions",
        "reassess the affected decision when evidence changes",
        "keep the working reasoning separate from the user-facing response",
        "do not routinely present exhaustive steps, estimates, or team details",
        "not a mandatory response format",
    ):
        assert term in normalized, term
    assert "every execution-plan heading is required" not in normalized
    assert "team: none" not in normalized
    assert "watchdog" not in normalized
    assert len(text.split()) < 350


def test_install_skills_defaults_to_bundled_source(tmp_path: Path) -> None:
    from automata.install.skills import install_skills

    target_root = tmp_path / "dest"

    results = install_skills(target_root=target_root, skill_names=["automata-setup"])

    assert [result.name for result in results] == ["automata-setup"]
    assert (target_root / "automata-setup" / "SKILL.md").is_file()


def test_install_skills_copies_bundled_adaptive_ui_skill(tmp_path: Path) -> None:
    from automata.install.skills import install_skills

    target_root = tmp_path / "dest"

    results = install_skills(target_root=target_root, skill_names=["automata-adaptive-ui"])

    assert [result.name for result in results] == ["automata-adaptive-ui"]
    assert (target_root / "automata-adaptive-ui" / "SKILL.md").is_file()


def find_skill_file(name: str) -> Path:
    matches = [path for path in SKILLS_ROOT.rglob("SKILL.md") if path.parent.name == name]
    assert len(matches) == 1, (name, matches)
    return matches[0]


def parse_frontmatter(skill_file: Path) -> dict[str, object]:
    text = skill_file.read_text()
    assert text.startswith("---\n"), skill_file

    try:
        _, frontmatter, body = text.split("---\n", 2)
    except ValueError as exc:
        raise AssertionError(f"Missing closing frontmatter delimiter: {skill_file}") from exc

    assert body.strip(), skill_file
    parsed = yaml.safe_load(frontmatter)
    assert isinstance(parsed, dict), skill_file
    return parsed


def parse_tool_mappings(frontmatter: dict[str, object], skill_file: Path) -> tuple[str, ...]:
    metadata = frontmatter.get("metadata", {})
    assert isinstance(metadata, dict), skill_file

    value = metadata.get(TOOL_MAPPING_KEY)
    if value is None:
        return ()

    assert isinstance(value, str), skill_file
    paths = tuple(path.strip() for path in value.split(",") if path.strip())
    assert paths, skill_file
    assert len(paths) == len(set(paths)), skill_file
    return paths
