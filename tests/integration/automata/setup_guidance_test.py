"""Check targeted setup/reuse boundaries without requiring a live environment."""
from importlib.resources import files


def skill(group: str, name: str) -> str:
    return " ".join(
        files("automata").joinpath("skills", group, name, "SKILL.md").read_text().split()
    )


def test_skill_design_distinguishes_verified_setup_from_normal_use() -> None:
    text = skill("skill-ops", "automata-skill-design")
    for term in (
        "distinguish establishing a working setup from normal use",
        "separate files or phases are optional",
        "verify the chosen approach before persisting environment-specific facts",
        "lightweight checks of changeable prerequisites",
        "recover only the affected setup within existing authority",
        "Do not rediscover known mapped tool entries as ceremony",
        "or require setup for judgment-only skills",
    ):
        assert term in text


def test_browser_reuse_verifies_identity_and_limits_repair_scope() -> None:
    text = skill("operations", "automata-web-browser-control")
    for term in (
        "Verify the chosen connection and intended browser/profile ownership",
        "Executable presence alone is not a successful connection",
        "On reuse, check only changeable prerequisites",
        "coordinates as hints to verify, not permanent identity",
        "Recover only the affected setup within existing authorization",
    ):
        assert term in text


def test_setup_distinguishes_installation_discovery_and_selected_readiness() -> None:
    text = skill("skill-ops", "automata-setup")
    for term in (
        "preparing a global or repo-local agent environment for use",
        "Installation and capability readiness are different outcomes",
        "Offer relevant environment-dependent setup, not every installed skill",
        "Respect installation-only requests",
        "Judgment-only skills do not need a setup ceremony",
        "Distinguish files installed from skills/extensions discovered",
        "use a fresh session or supported reload when discovery needs checking",
        "Use the selected capability's own guidance",
    ):
        assert term in text, term


def test_setup_readiness_keeps_side_effects_and_evidence_scoped() -> None:
    text = skill("skill-ops", "automata-setup")
    for term in (
        "Installation approval alone does not authorize test messages",
        "Reuse explicit permission already covering those effects",
        "Do not launch workers merely to make installation appear complete",
        "not just a send receipt",
        "untested or blocked rather than claiming readiness",
        "When reusable setup knowledge is useful",
        "Do not require a setup record for every capability",
        "or persist live handles as permanent identity",
        "repair only the affected setup within authority",
    ):
        assert term in text, term


def test_setup_covers_custom_source_and_selected_skill_installation() -> None:
    text = skill("skill-ops", "automata-setup")
    for term in (
        "skills from bundled or custom sources",
        "respect an explicit skills-only or other narrower request",
        "Confirm source (bundled by default), scope, and destination roots",
        "remove selected existing destinations, then copy; do not merge",
        "local paths and `file://` URLs",
        "the installer does not fetch remote repositories",
        "by its directory name; source grouping directories are not exposed",
        "repeatable or comma-separated `--skill` values",
        "--skill <skill-a>,<skill-b>",
        "Omit `--skill` only when all discovered skills are intended",
        "not a skill-content review or extra package-structure audit",
    ):
        assert term in text, term


def test_timer_record_deletion_requires_owner_authority() -> None:
    text = skill("operations", "automata-timer")
    assert "agreed retention/removal policy or explicit scoped approval" in text
    assert "Age alone does not establish that evidence is disposable" in text
    assert "Cancel obsolete pending or recurring jobs" in text
