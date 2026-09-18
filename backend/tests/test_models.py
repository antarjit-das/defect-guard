"""Unit tests for Pydantic v2 data models and shared field definitions.

Verifies strict conformance to IMPLEMENTATION.md §5 and §9 contracts.
"""

import pytest
from pydantic import ValidationError

from backend.src.core.fields import (
    ALL_ROLES,
    ROLE_PRECEDENCE,
    ALL_FIELD_KEYS,
    FIELD_STUDENT_NAME,
    FIELD_ANNUAL_INCOME,
    ROLE_AADHAAR,
    ROLE_INCOME_CERTIFICATE,
    ROLE_MARKSHEET,
    ROLE_BANK_PROOF,
    ROLE_FIELDS,
    TEXTRACT_QUERIES,
)
from backend.src.core.models import (
    DocumentRole,
    PacketStatus,
    DocumentStatus,
    Severity,
    FindingCategory,
    VerdictBand,
    AIStatus,
    ExtractedField,
    DocumentExtraction,
    DocumentItem,
    SnapshotRow,
    Snapshot,
    Finding,
    DocumentReference,
    Verdict,
    Packet,
    CreateUploadUrlRequest,
    CreateUploadUrlResponse,
    CreatePacketResponse,
    RunCheckResponse,
    ApiErrorResponse,
)


def test_field_constants():
    """Verify that all 21 canonical field keys and 4 roles exist in constants."""
    assert len(ALL_ROLES) == 4
    assert len(ALL_FIELD_KEYS) == 21
    assert FIELD_STUDENT_NAME in ALL_FIELD_KEYS
    assert FIELD_ANNUAL_INCOME in ALL_FIELD_KEYS
    assert ROLE_PRECEDENCE[0] == ROLE_AADHAAR

    # Verify each role has defined extracted fields and Textract queries
    for role in ALL_ROLES:
        assert role in ROLE_FIELDS
        assert len(ROLE_FIELDS[role]) > 0
        assert role in TEXTRACT_QUERIES
        assert len(TEXTRACT_QUERIES[role]) > 0


def test_extracted_field_validation():
    """Test ExtractedField validation and boundary enforcement."""
    field = ExtractedField(
        fieldKey=FIELD_STUDENT_NAME,
        rawValue="ANTARJIT DAS",
        normalizedValue="antarjit das",
        confidence=0.98,
        evidence="Name: ANTARJIT DAS",
    )
    assert field.fieldKey == "student_name"
    assert field.confidence == 0.98

    # Confidence must be between 0.0 and 1.0
    with pytest.raises(ValidationError):
        ExtractedField(fieldKey="test", confidence=1.5)

    with pytest.raises(ValidationError):
        ExtractedField(fieldKey="test", confidence=-0.1)


def test_finding_and_verdict_models():
    """Test Finding and Verdict construction and constraints."""
    finding = Finding(
        findingId="f1",
        ruleId="R-01",
        title="Student name differs across documents",
        severity=Severity.RED,
        category=FindingCategory.IDENTITY,
        documents=[
            DocumentReference(role=DocumentRole.AADHAAR, value="ANTARJIT DAS"),
            DocumentReference(role=DocumentRole.MARKSHEET, value="ANTARJEET DASS"),
        ],
        reason="Name spelling differs on marksheet.",
        fixInstruction="Ensure records use consistent spelling.",
        confidence=0.95,
        source="MMNBA 2026 Guidelines",
    )
    assert finding.findingId == "f1"
    assert finding.severity == Severity.RED

    snapshot = Snapshot(
        rows=[
            SnapshotRow(
                fieldKey=FIELD_STUDENT_NAME,
                label="Student Name",
                valuesByRole={
                    ROLE_AADHAAR: "ANTARJIT DAS",
                    ROLE_MARKSHEET: "ANTARJEET DASS",
                },
                canonicalValue="ANTARJIT DAS",
                canonicalSource=ROLE_AADHAAR,
                hasDisagreement=True,
            )
        ]
    )

    verdict = Verdict(
        checkRunId="check-123",
        snapshot=snapshot,
        findings=[finding],
        score=75,
        band=VerdictBand.RISKY,
        scoreArithmetic="100 - 25x1 red = 75",
        ruleSetVersion="NIJUT_BABU_2026@1",
        aiStatus=AIStatus.OK,
        createdAt="2026-09-18T10:00:00Z",
    )
    assert verdict.score == 75
    assert verdict.band == VerdictBand.RISKY

    # Score constraint: 0 <= score <= 100
    with pytest.raises(ValidationError):
        Verdict(
            checkRunId="c1",
            snapshot=snapshot,
            findings=[],
            score=105,
            band=VerdictBand.READY,
            scoreArithmetic="",
            createdAt="2026-09-18T10:00:00Z",
        )


def test_full_packet_envelope_roundtrip():
    """Test full Packet JSON serialization and deserialization (matching IMPLEMENTATION.md §6.5)."""
    raw_packet_data = {
        "packetId": "pkt-uuid-1",
        "schemeId": "NIJUT_BABU_2026",
        "status": "CHECKED",
        "createdAt": "2026-09-18T10:00:00Z",
        "updatedAt": "2026-09-18T10:05:00Z",
        "documents": [
            {
                "documentId": "doc-uuid-1",
                "role": "AADHAAR",
                "fileName": "aadhaar.jpg",
                "contentType": "image/jpeg",
                "sizeBytes": 152340,
                "pageCount": 1,
                "status": "EXTRACTED",
                "extraction": {
                    "roleConfirmed": True,
                    "documentQuality": "GOOD",
                    "fields": [
                        {
                            "fieldKey": "student_name",
                            "rawValue": "ANTARJIT DAS",
                            "normalizedValue": "antarjit das",
                            "confidence": 0.97,
                            "evidence": "Name / नाम ANTARJIT DAS",
                            "source": "TEXTRACT_QUERY",
                            "needsConfirmation": False,
                        }
                    ],
                },
            }
        ],
        "verdict": {
            "checkRunId": "run-uuid-1",
            "snapshot": {
                "rows": [
                    {
                        "fieldKey": "student_name",
                        "label": "Student Name",
                        "valuesByRole": {
                            "AADHAAR": "ANTARJIT DAS",
                            "MARKSHEET": "ANTARJEET DASS",
                        },
                        "canonicalValue": "ANTARJIT DAS",
                        "canonicalSource": "AADHAAR",
                        "hasDisagreement": True,
                    }
                ]
            },
            "findings": [
                {
                    "findingId": "f1",
                    "ruleId": "R-01",
                    "title": "Student name differs across documents",
                    "severity": "RED",
                    "category": "IDENTITY",
                    "documents": [
                        {"role": "AADHAAR", "value": "ANTARJIT DAS"},
                        {"role": "MARKSHEET", "value": "ANTARJEET DASS"},
                    ],
                    "reason": "Name differs between Aadhaar and marksheet.",
                    "fixInstruction": "Ensure records use consistent spelling.",
                    "confidence": 0.92,
                    "source": "MMNBA Guideline",
                }
            ],
            "score": 40,
            "band": "NOT_READY",
            "scoreArithmetic": "100 - 25x2 red - 10x1 amber = 40",
            "ruleSetVersion": "NIJUT_BABU_2026@1",
            "modelId": "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
            "aiStatus": "OK",
            "createdAt": "2026-09-18T10:05:00Z",
        },
        "previousScore": None,
    }

    packet = Packet.model_validate(raw_packet_data)
    assert packet.packetId == "pkt-uuid-1"
    assert packet.status == PacketStatus.CHECKED
    assert len(packet.documents) == 1
    assert packet.documents[0].role == DocumentRole.AADHAAR
    assert packet.verdict is not None
    assert packet.verdict.score == 40
    assert packet.verdict.band == VerdictBand.NOT_READY

    # Serialize back to dictionary
    serialized = packet.model_dump(mode="json")
    assert serialized["packetId"] == "pkt-uuid-1"
    assert serialized["status"] == "CHECKED"
    assert serialized["verdict"]["score"] == 40


def test_api_models():
    """Test API request and response models."""
    req = CreateUploadUrlRequest(
        role=DocumentRole.INCOME_CERTIFICATE,
        fileName="income.pdf",
        contentType="application/pdf",
        sizeBytes=184320,
    )
    assert req.role == DocumentRole.INCOME_CERTIFICATE

    res = CreateUploadUrlResponse(
        documentId="doc-123",
        uploadUrl="https://s3.amazonaws.com/presigned",
        expiresInSeconds=300,
        objectKey="packets/p1/doc-123.pdf",
    )
    assert res.expiresInSeconds == 300

    err = ApiErrorResponse.model_validate(
        {"error": {"code": "FILE_TOO_LARGE", "message": "File exceeds 5MB limit"}}
    )
    assert err.error.code == "FILE_TOO_LARGE"
