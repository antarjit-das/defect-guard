"""Readiness scoring and arithmetic engine for Defect Guard.

Strictly deterministic pure-Python scoring engine.
Implements the formula and rating bands from IMPLEMENTATION.md §8.8.
Zero external AWS/boto3 imports. LLM never calculates or alters the score.
"""

from typing import List, Tuple

from .models import Finding, Severity, VerdictBand


def compute_readiness_score(findings: List[Finding]) -> Tuple[int, VerdictBand, str]:
    """Calculate the Application Document Readiness score and arithmetic breakdown.

    Formula:
        score = max(0, 100 - (25 * num_red) - (10 * num_amber))

    Rating Bands:
        - READY: score >= 85
        - RISKY: 60 <= score < 85
        - NOT_READY: score < 60

    Returns:
        Tuple of (score: int, band: VerdictBand, scoreArithmetic: str).
        Example: (40, VerdictBand.NOT_READY, "100 - 25x2 red - 10x1 amber = 40")
    """
    num_red = 0
    num_amber = 0

    for f in findings:
        if f.severity == Severity.RED:
            num_red += 1
        elif f.severity == Severity.AMBER:
            num_amber += 1


    deductions = (25 * num_red) + (10 * num_amber)
    raw_score = 100 - deductions
    score = max(0, raw_score)

    # Determine readiness band
    if score >= 85:
        band = VerdictBand.READY
    elif score >= 60:
        band = VerdictBand.RISKY
    else:
        band = VerdictBand.NOT_READY

    # Build human-readable arithmetic string
    parts = []
    if num_red > 0:
        parts.append(f"25x{num_red} red")
    if num_amber > 0:
        parts.append(f"10x{num_amber} amber")

    if parts:
        score_arithmetic = f"100 - {' - '.join(parts)} = {score}"
    else:
        score_arithmetic = "100 = 100"

    return score, band, score_arithmetic
