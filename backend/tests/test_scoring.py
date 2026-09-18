"""Unit tests for the readiness scoring and arithmetic engine.

Verifies deterministic arithmetic, rating bands, and boundary cases.
"""

from backend.src.core.models import Finding, Severity, FindingCategory, VerdictBand
from backend.src.core.scoring import compute_readiness_score


def _make_dummy_finding(severity: Severity, finding_id: str = "f1") -> Finding:
    """Helper to create dummy findings for scoring tests."""
    return Finding(
        findingId=finding_id,
        ruleId="R-TEST",
        title="Test finding",
        severity=severity,
        category=FindingCategory.ELIGIBILITY,
        documents=[],
        reason="Test reason",
        fixInstruction="Test fix",
        confidence=1.0,
        source="Test Source",
    )


def test_perfect_score():
    """Test that zero findings yields 100 points, READY band, and '100 = 100'."""
    score, band, arithmetic = compute_readiness_score([])
    assert score == 100
    assert band == VerdictBand.READY
    assert arithmetic == "100 = 100"


def test_demo_packet_scoring():
    """Test exact scoring for the 3 demo packet defects: 2 RED, 1 AMBER -> 40 points."""
    findings = [
        _make_dummy_finding(Severity.RED, "f1"),
        _make_dummy_finding(Severity.RED, "f2"),
        _make_dummy_finding(Severity.AMBER, "f3"),
    ]
    score, band, arithmetic = compute_readiness_score(findings)
    assert score == 40
    assert band == VerdictBand.NOT_READY
    assert arithmetic == "100 - 25x2 red - 10x1 amber = 40"


def test_recheck_score_transition():
    """Test score transition when 1 RED finding is resolved by replacement: 1 RED, 1 AMBER -> 65 points."""
    findings = [
        _make_dummy_finding(Severity.RED, "f1"),
        _make_dummy_finding(Severity.AMBER, "f3"),
    ]
    score, band, arithmetic = compute_readiness_score(findings)
    assert score == 65
    assert band == VerdictBand.RISKY
    assert arithmetic == "100 - 25x1 red - 10x1 amber = 65"


def test_scoring_boundaries():
    """Test rating band boundaries: >= 85 is READY, 60-84 is RISKY, < 60 is NOT_READY."""
    # 1 AMBER -> 90 points (READY)
    score, band, _ = compute_readiness_score([_make_dummy_finding(Severity.AMBER)])
    assert score == 90
    assert band == VerdictBand.READY

    # 4 AMBER -> exactly 60 points (RISKY boundary)
    findings_60 = [_make_dummy_finding(Severity.AMBER, f"f{i}") for i in range(4)]
    score, band, _ = compute_readiness_score(findings_60)
    assert score == 60
    assert band == VerdictBand.RISKY

    # 1 RED + 2 AMBER -> 55 points (< 60, NOT_READY)
    findings_55 = [
        _make_dummy_finding(Severity.RED, "f1"),
        _make_dummy_finding(Severity.AMBER, "f2"),
        _make_dummy_finding(Severity.AMBER, "f3"),
    ]
    score, band, _ = compute_readiness_score(findings_55)
    assert score == 55
    assert band == VerdictBand.NOT_READY


def test_score_floor_at_zero():
    """Test that score is capped at zero and cannot go negative."""
    # 5 RED -> 100 - 125 = -25 -> must cap at 0
    findings_excessive = [_make_dummy_finding(Severity.RED, f"f{i}") for i in range(5)]
    score, band, arithmetic = compute_readiness_score(findings_excessive)
    assert score == 0
    assert band == VerdictBand.NOT_READY
    assert arithmetic == "100 - 25x5 red = 0"


def test_info_findings_no_deduction():
    """Test that INFO findings do not subtract any points."""
    findings = [
        _make_dummy_finding(Severity.INFO, "f1"),
        _make_dummy_finding(Severity.INFO, "f2"),
    ]
    score, band, arithmetic = compute_readiness_score(findings)
    assert score == 100
    assert band == VerdictBand.READY
    assert arithmetic == "100 = 100"
