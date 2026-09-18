"""Tests validating that frontend mock fixtures strictly adhere to backend Pydantic models.

Enforces Contract C6: Both frontend and backend share identical, valid fixtures.
"""

import json
from pathlib import Path

from backend.src.core.models import (
    Packet,
    PacketStatus,
    DocumentStatus,
    DocumentRole,
    Severity,
    VerdictBand,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "fixtures"


def test_packet_checked_fixture():
    """Verify that packet_checked.json passes full Pydantic model validation."""
    fixture_path = FIXTURES_DIR / "packet_checked.json"
    assert fixture_path.exists(), f"Fixture not found at {fixture_path}"

    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    packet = Packet.model_validate(data)

    # Top-level checks
    assert packet.packetId == "pkt-demo-2026-0918"
    assert packet.status == PacketStatus.CHECKED
    assert packet.schemeId == "NIJUT_BABU_2026"
    assert len(packet.documents) == 4

    # Document-level checks
    doc_roles = [doc.role for doc in packet.documents]
    assert DocumentRole.AADHAAR in doc_roles
    assert DocumentRole.INCOME_CERTIFICATE in doc_roles
    assert DocumentRole.MARKSHEET in doc_roles
    assert DocumentRole.BANK_PROOF in doc_roles

    for doc in packet.documents:
        assert doc.status == DocumentStatus.EXTRACTED
        assert doc.extraction is not None
        assert doc.extraction.roleConfirmed is True
        assert len(doc.extraction.fields) > 0

    # Verdict & Snapshot checks
    verdict = packet.verdict
    assert verdict is not None
    assert verdict.score == 40
    assert verdict.band == VerdictBand.NOT_READY
    assert verdict.scoreArithmetic == "100 - 25x2 red - 10x1 amber = 40"

    # Snapshot rows
    student_name_row = next(r for r in verdict.snapshot.rows if r.fieldKey == "student_name")
    assert student_name_row.hasDisagreement is True
    assert student_name_row.valuesByRole["AADHAAR"] == "ANTARJIT DAS"
    assert student_name_row.valuesByRole["MARKSHEET"] == "ANTARJEET DASS"

    # Findings checks (3 planted demo defects)
    assert len(verdict.findings) == 3
    severities = [f.severity for f in verdict.findings]
    assert severities.count(Severity.RED) == 2
    assert severities.count(Severity.AMBER) == 1


def test_packet_extracting_fixture():
    """Verify that packet_extracting.json passes full Pydantic model validation."""
    fixture_path = FIXTURES_DIR / "packet_extracting.json"
    assert fixture_path.exists(), f"Fixture not found at {fixture_path}"

    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    packet = Packet.model_validate(data)

    assert packet.packetId == "pkt-demo-2026-0918"
    assert packet.status == PacketStatus.EXTRACTING
    assert packet.verdict is None
    assert len(packet.documents) == 4

    # Documents are in progress
    statuses = [doc.status for doc in packet.documents]
    assert DocumentStatus.EXTRACTING in statuses
    assert DocumentStatus.UPLOADED in statuses
