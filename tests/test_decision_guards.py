"""Decision-state guards for security-sensitive roadmap work."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    """Read a governance document from the repository root."""
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_r2_adr_is_returned_for_revision() -> None:
    """AssetRegistry must not rely on the rejected batch-authorization design."""
    adr = _read("docs/adr-v052-r2-multi-target-redesign.md")

    assert "Proposed - Changes Required" in adr
    assert "AssetRegistry: BLOCKED" in adr


def test_unsafe_roadmap_work_is_blocked() -> None:
    """The active progress document must expose all three security blocks."""
    progress = _read(".guardrails/PROGRESS.md")

    assert "Nuclei synchronization: BLOCKED" in progress
    assert "v0.0.56 WSGI: BLOCKED" in progress
    assert "AssetRegistry: BLOCKED" in progress


def test_version_roadmap_repeats_security_blocks() -> None:
    """The planning view must not disagree with the active progress document."""
    roadmap = _read(".guardrails/VERSION_ROADMAP.md")

    assert "Nuclei synchronization: BLOCKED" in roadmap
    assert "v0.0.56 WSGI: BLOCKED" in roadmap
    assert "AssetRegistry: BLOCKED" in roadmap


def test_decision_log_does_not_mark_all_v052_adrs_accepted() -> None:
    """The central index must record the R2 decision as returned for revision."""
    decision_log = _read("docs/DECISION_LOG.md")

    assert "R2 multi-target: Proposed - Changes Required" in decision_log
    assert "WSGI: BLOCKED" in decision_log
