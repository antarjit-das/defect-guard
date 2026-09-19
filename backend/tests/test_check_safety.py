"""Regression tests for /check safety and snapshot protection.

Guarantees:
- EXTRACTION_FAILED documents are excluded from usable extraction snapshots.
- Documents with empty or unusable extractions do not count toward extraction prerequisites.
- An empty or failed packet cannot silently produce a successful-looking 100-score verdict.
- run_check requires at least 3 usable extracted documents before creating a verdict.
- POST /check API requires all mandatory roles to be successfully extracted with usable fields.
"""

import json
from unittest.mock import patch, MagicMock

from backend.src.core.models import (
    Packet,
    PacketStatus,
    DocumentItem,
    DocumentRole,
    DocumentStatus,
    DocumentExtraction,
    ExtractedField,
    DocumentQuality,
    AIStatus,
)
from backend.src.core.snapshot import build_snapshot
from backend.src.handlers.run_check import handler as handle_run_check
from backend.src.handlers.run_check_api import handler as handle_run_check_api


def test_snapshot_excludes_failed_and_unusable_documents():
    """Verify that EXTRACTION_FAILED documents and unusable extractions are excluded from snapshot."""
    doc_failed = DocumentItem(
        documentId="doc-failed",
        role=DocumentRole.AADHAAR,
        fileName="aadhaar.jpg",
        contentType="image/jpeg",
        sizeBytes=100000,
        status=DocumentStatus.EXTRACTION_FAILED,
        error="Textract service failure: SubscriptionRequiredException",
        extraction=None,
    )
    doc_empty_fields = DocumentItem(
        documentId="doc-empty",
        role=DocumentRole.MARKSHEET,
        fileName="marksheet.pdf",
        contentType="application/pdf",
        sizeBytes=100000,
        status=DocumentStatus.EXTRACTED,
        extraction=DocumentExtraction(
            fields=[],
            roleConfirmed=False,
            documentQuality=DocumentQuality.POOR,
        ),
    )
    doc_valid = DocumentItem(
        documentId="doc-valid",
        role=DocumentRole.INCOME_CERTIFICATE,
        fileName="income.pdf",
        contentType="application/pdf",
        sizeBytes=100000,
        status=DocumentStatus.EXTRACTED,
        extraction=DocumentExtraction(
            fields=[
                ExtractedField(fieldKey="annual_income", rawValue="₹2,40,000/-"),
            ],
            roleConfirmed=True,
            documentQuality=DocumentQuality.GOOD,
        ),
    )

    # 1. Snapshot with failed + empty + valid: only valid document appears
    snapshot = build_snapshot([doc_failed, doc_empty_fields, doc_valid])
    assert len(snapshot.rows) == 1
    assert snapshot.rows[0].fieldKey == "annual_income"
    assert snapshot.rows[0].canonicalValue == "₹2,40,000/-"

    # 2. All-failed packet produces completely empty snapshot
    empty_snapshot = build_snapshot([doc_failed, doc_empty_fields])
    assert len(empty_snapshot.rows) == 0


@patch("backend.src.handlers.run_check.get_full_packet")
@patch("backend.src.handlers.run_check.save_verdict")
@patch("backend.src.handlers.run_check.update_packet_status")
def test_run_check_worker_rejects_empty_or_failed_packet(
    mock_update_status, mock_save_verdict, mock_get_full
):
    """Verify run_check worker rejects packet when all documents failed extraction.

    Guarantees that a 100 score is NEVER produced on an empty or failed packet.
    """
    failed_docs = [
        DocumentItem(
            documentId=f"d-{role.value}",
            role=role,
            fileName=f"{role.value}.pdf",
            contentType="application/pdf",
            sizeBytes=50000,
            status=DocumentStatus.EXTRACTION_FAILED,
            error="Service error",
            extraction=None,
        )
        for role in [DocumentRole.AADHAAR, DocumentRole.INCOME_CERTIFICATE, DocumentRole.MARKSHEET, DocumentRole.BANK_PROOF]
    ]

    mock_get_full.return_value = Packet(
        packetId="pkt-failed-all",
        status=PacketStatus.CHECKING,
        createdAt="2026-09-19T00:00:00Z",
        updatedAt="2026-09-19T00:00:00Z",
        documents=failed_docs,
    )

    event = {"packetId": "pkt-failed-all", "checkRunId": "chk-fail-test"}
    result = handle_run_check(event)

    assert result["status"] == "FAILED"
    assert "at least 3 usable extracted documents are required" in result["error"]
    # Critical guarantee: save_verdict MUST NOT be called!
    mock_save_verdict.assert_not_called()


@patch("backend.src.handlers.run_check.get_full_packet")
@patch("backend.src.handlers.run_check.save_verdict")
@patch("backend.src.handlers.run_check.update_packet_status")
def test_run_check_worker_rejects_insufficient_documents(
    mock_update_status, mock_save_verdict, mock_get_full
):
    """Verify run_check worker enforces the minimum 3 usable extracted documents requirement."""
    docs = [
        DocumentItem(
            documentId="d1",
            role=DocumentRole.AADHAAR,
            fileName="aadhaar.jpg",
            contentType="image/jpeg",
            sizeBytes=50000,
            status=DocumentStatus.EXTRACTED,
            extraction=DocumentExtraction(
                fields=[ExtractedField(fieldKey="student_name", rawValue="ANTARJIT DAS")]
            ),
        ),
        DocumentItem(
            documentId="d2",
            role=DocumentRole.MARKSHEET,
            fileName="marksheet.pdf",
            contentType="application/pdf",
            sizeBytes=50000,
            status=DocumentStatus.EXTRACTED,
            extraction=DocumentExtraction(
                fields=[ExtractedField(fieldKey="student_name", rawValue="ANTARJIT DAS")]
            ),
        ),
        DocumentItem(
            documentId="d3",
            role=DocumentRole.INCOME_CERTIFICATE,
            fileName="income.pdf",
            contentType="application/pdf",
            sizeBytes=50000,
            status=DocumentStatus.EXTRACTION_FAILED,
            extraction=None,
        ),
    ]

    mock_get_full.return_value = Packet(
        packetId="pkt-two-docs",
        status=PacketStatus.CHECKING,
        createdAt="2026-09-19T00:00:00Z",
        updatedAt="2026-09-19T00:00:00Z",
        documents=docs,
    )

    event = {"packetId": "pkt-two-docs", "checkRunId": "chk-insufficient"}
    result = handle_run_check(event)

    assert result["status"] == "FAILED"
    assert "at least 3 usable extracted documents are required" in result["error"]
    assert "found 2" in result["error"]
    mock_save_verdict.assert_not_called()


@patch("backend.src.handlers.run_check_api.get_full_packet")
def test_run_check_api_rejects_when_mandatory_doc_extraction_failed(mock_get_full):
    """POST /check returns 409 DOCUMENTS_NOT_READY if a mandatory document failed extraction."""
    docs = [
        DocumentItem(
            documentId="d1", role=DocumentRole.AADHAAR, fileName="a.jpg", contentType="image/jpeg",
            sizeBytes=50000, status=DocumentStatus.EXTRACTED,
            extraction=DocumentExtraction(fields=[ExtractedField(fieldKey="student_name", rawValue="ANTARJIT DAS")]),
        ),
        DocumentItem(
            documentId="d2", role=DocumentRole.MARKSHEET, fileName="m.pdf", contentType="application/pdf",
            sizeBytes=50000, status=DocumentStatus.EXTRACTED,
            extraction=DocumentExtraction(fields=[ExtractedField(fieldKey="student_name", rawValue="ANTARJIT DAS")]),
        ),
        DocumentItem(
            documentId="d3", role=DocumentRole.BANK_PROOF, fileName="b.pdf", contentType="application/pdf",
            sizeBytes=50000, status=DocumentStatus.EXTRACTED,
            extraction=DocumentExtraction(fields=[ExtractedField(fieldKey="account_holder_name", rawValue="ANTARJIT DAS")]),
        ),
        # INCOME_CERTIFICATE failed extraction!
        DocumentItem(
            documentId="d4", role=DocumentRole.INCOME_CERTIFICATE, fileName="inc.pdf", contentType="application/pdf",
            sizeBytes=50000, status=DocumentStatus.EXTRACTION_FAILED,
            error="Textract failed",
            extraction=None,
        ),
    ]

    mock_get_full.return_value = Packet(
        packetId="pkt-api-fail",
        status=PacketStatus.DRAFT,
        createdAt="2026-09-19T00:00:00Z",
        updatedAt="2026-09-19T00:00:00Z",
        documents=docs,
    )

    event = {"pathParameters": {"packetId": "pkt-api-fail"}}
    resp = handle_run_check_api(event)

    assert resp["statusCode"] == 409
    body = json.loads(resp["body"])
    assert body["error"]["code"] == "DOCUMENTS_NOT_READY"
    assert "INCOME_CERTIFICATE" in body["pendingRoles"]


@patch("backend.src.handlers.run_check_api.get_full_packet")
def test_run_check_api_rejects_empty_extractions(mock_get_full):
    """POST /check returns 409 DOCUMENTS_NOT_READY if a document is marked EXTRACTED but has 0 usable fields."""
    docs = [
        DocumentItem(
            documentId="d1", role=DocumentRole.AADHAAR, fileName="a.jpg", contentType="image/jpeg",
            sizeBytes=50000, status=DocumentStatus.EXTRACTED,
            extraction=DocumentExtraction(fields=[ExtractedField(fieldKey="student_name", rawValue="ANTARJIT DAS")]),
        ),
        DocumentItem(
            documentId="d2", role=DocumentRole.MARKSHEET, fileName="m.pdf", contentType="application/pdf",
            sizeBytes=50000, status=DocumentStatus.EXTRACTED,
            extraction=DocumentExtraction(fields=[ExtractedField(fieldKey="student_name", rawValue="ANTARJIT DAS")]),
        ),
        DocumentItem(
            documentId="d3", role=DocumentRole.BANK_PROOF, fileName="b.pdf", contentType="application/pdf",
            sizeBytes=50000, status=DocumentStatus.EXTRACTED,
            extraction=DocumentExtraction(fields=[ExtractedField(fieldKey="account_holder_name", rawValue="ANTARJIT DAS")]),
        ),
        # INCOME_CERTIFICATE is EXTRACTED, but fields are empty (unusable)
        DocumentItem(
            documentId="d4", role=DocumentRole.INCOME_CERTIFICATE, fileName="inc.pdf", contentType="application/pdf",
            sizeBytes=50000, status=DocumentStatus.EXTRACTED,
            extraction=DocumentExtraction(fields=[]),
        ),
    ]

    mock_get_full.return_value = Packet(
        packetId="pkt-unusable-fields",
        status=PacketStatus.DRAFT,
        createdAt="2026-09-19T00:00:00Z",
        updatedAt="2026-09-19T00:00:00Z",
        documents=docs,
    )

    event = {"pathParameters": {"packetId": "pkt-unusable-fields"}}
    resp = handle_run_check_api(event)

    assert resp["statusCode"] == 409
    body = json.loads(resp["body"])
    assert body["error"]["code"] == "DOCUMENTS_NOT_READY"
    assert "INCOME_CERTIFICATE" in body["pendingRoles"]
