"""Unit tests for asynchronous worker Lambdas (fn_extract_document, fn_run_check).

Validates:
- fn_extract_document: Textract + Bedrock structured extraction, PII masking, normalizers, and READY_TO_CHECK transition.
- fn_run_check: Snapshot assembly, RuleEngine, Bedrock adjudication with 6 guardrails, template fallback, scoring, and CHECKED transition.
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
    Finding,
    Severity,
    FindingCategory,
    AIStatus,
)
from backend.src.handlers.extract_document import handler as handle_extract_document
from backend.src.handlers.run_check import handler as handle_run_check


# =====================================================================
# Test 1: extract_document with Bedrock Success
# =====================================================================

@patch("backend.src.handlers.extract_document.get_authoritative_metadata")
@patch("backend.src.handlers.extract_document.extract_document_sync")
@patch("backend.src.handlers.extract_document.invoke_bedrock_structured")
@patch("backend.src.handlers.extract_document.update_document_extraction")
@patch("backend.src.handlers.extract_document.get_full_packet")
@patch("backend.src.handlers.extract_document.update_packet_status")
def test_extract_document_worker_success(
    mock_up_pkt, mock_get_full, mock_up_doc, mock_bedrock, mock_textract, mock_s3_meta
):
    """fn_extract_document extracts fields, masks Aadhaar, updates DynamoDB, and transitions packet."""
    mock_s3_meta.return_value = {"contentLength": 150000, "contentType": "image/jpeg"}
    mock_textract.return_value = {
        "query_answers": {"What is the name?": "ANTARJIT DAS"},
        "form_kvs": {},
        "raw_lines": ["Government of India", "Name: ANTARJIT DAS"],
        "mean_confidence": 0.98,
        "page_count": 1,
    }

    # Simulate Bedrock returning valid DocumentExtraction JSON
    mock_bedrock.return_value = json.dumps({
        "roleConfirmed": True,
        "documentQuality": "GOOD",
        "fields": [
            {
                "fieldKey": "student_name",
                "rawValue": "Shri ANTARJIT DAS",
                "confidence": 0.98,
                "evidence": "Name: ANTARJIT DAS",
            },
            {
                "fieldKey": "aadhaar_last4",
                "rawValue": "9876 5432 1234",  # Must be masked by worker!
                "confidence": 0.99,
                "evidence": "1234",
            },
        ],
        "notes": "Clear scan",
    })

    # Simulate 3 extracted documents so packet transitions to READY_TO_CHECK
    docs = [
        DocumentItem(documentId="d1", role=DocumentRole.AADHAAR, fileName="a.jpg", contentType="image/jpeg", sizeBytes=1000, status=DocumentStatus.EXTRACTED),
        DocumentItem(documentId="d2", role=DocumentRole.MARKSHEET, fileName="m.pdf", contentType="application/pdf", sizeBytes=1000, status=DocumentStatus.EXTRACTED),
        DocumentItem(documentId="d3", role=DocumentRole.BANK_PROOF, fileName="b.pdf", contentType="application/pdf", sizeBytes=1000, status=DocumentStatus.EXTRACTED),
    ]
    mock_get_full.return_value = Packet(
        packetId="pkt-1",
        status=PacketStatus.EXTRACTING,
        createdAt="2026-09-19T00:00:00Z",
        updatedAt="2026-09-19T00:00:00Z",
        documents=docs,
    )

    event = {
        "packetId": "pkt-1",
        "documentId": "d1",
        "role": "AADHAAR",
        "objectKey": "packets/pkt-1/d1.jpg",
    }

    res = handle_extract_document(event)
    assert res["status"] == "SUCCESS"
    assert res["documentId"] == "d1"

    # Verify update_document_extraction was called with masked Aadhaar (XXXXXXXX1234)
    mock_up_doc.assert_called_once()
    call_args = mock_up_doc.call_args[1]
    ext_dict = call_args["extraction_dict"]
    assert ext_dict["roleConfirmed"] is True

    # Check that Aadhaar was masked
    aadhaar_field = next(f for f in ext_dict["fields"] if f["fieldKey"] == "aadhaar_last4")
    assert aadhaar_field["rawValue"] == "XXXXXXXX1234"

    # Verify packet status transitioned to READY_TO_CHECK
    mock_up_pkt.assert_called_once_with("pkt-1", PacketStatus.READY_TO_CHECK)


# =====================================================================
# Test 2: extract_document with Fallback to Textract Queries
# =====================================================================

@patch("backend.src.handlers.extract_document.get_authoritative_metadata")
@patch("backend.src.handlers.extract_document.extract_document_sync")
@patch("backend.src.handlers.extract_document.invoke_bedrock_structured")
@patch("backend.src.handlers.extract_document.update_document_extraction")
@patch("backend.src.handlers.extract_document.get_full_packet")
def test_extract_document_worker_textract_fallback(
    mock_get_full, mock_up_doc, mock_bedrock, mock_textract, mock_s3_meta
):
    """When Bedrock fails/unreachable, worker falls back to deterministic Textract queries."""
    mock_s3_meta.return_value = {"contentLength": 120000, "contentType": "application/pdf"}
    mock_textract.return_value = {
        "query_answers": {
            "Whose income is certified?": "PRODIP DAS",
            "What is the annual income?": "4,50,000",
        },
        "form_kvs": {},
        "raw_lines": ["Income Certificate", "PRODIP DAS", "Rs. 4,50,000"],
        "mean_confidence": 0.95,
        "page_count": 1,
    }

    # Bedrock returns None (e.g. unverified account or throttling)
    mock_bedrock.return_value = None
    mock_get_full.return_value = None

    event = {
        "packetId": "pkt-1",
        "documentId": "d2",
        "role": "INCOME_CERTIFICATE",
        "objectKey": "packets/pkt-1/d2.pdf",
    }

    res = handle_extract_document(event)
    assert res["status"] == "SUCCESS"

    # Verify fields were populated from Textract
    call_args = mock_up_doc.call_args[1]
    ext_dict = call_args["extraction_dict"]
    fields = ext_dict["fields"]
    assert len(fields) >= 2
    income_field = next(f for f in fields if f["fieldKey"] == "annual_income")
    assert income_field["normalizedValue"] == 450000


# =====================================================================
# Test 3: run_check worker with Full Pipeline and Bedrock Adjudication
# =====================================================================

@patch("backend.src.handlers.run_check.get_full_packet")
@patch("backend.src.handlers.run_check.invoke_bedrock_structured")
@patch("backend.src.handlers.run_check.save_verdict")
def test_run_check_worker_success(mock_save_verdict, mock_bedrock, mock_get_full):
    """fn_run_check executes rules, Bedrock adjudication with guardrails, scores, and persists verdict."""
    # Setup 4 documents with the demo defect (Name mismatch: ANTARJIT DAS vs ANTARJEET DASS)
    docs = [
        DocumentItem(
            documentId="d1", role=DocumentRole.AADHAAR, fileName="aadhaar.jpg", contentType="image/jpeg", sizeBytes=1000,
            status=DocumentStatus.EXTRACTED,
            extraction=DocumentExtraction(
                fields=[
                    ExtractedField(fieldKey="student_name", rawValue="ANTARJIT DAS", normalizedValue="antarjit das"),
                    ExtractedField(fieldKey="gender", rawValue="MALE", normalizedValue="male"),
                ]
            ),
        ),
        DocumentItem(
            documentId="d2", role=DocumentRole.MARKSHEET, fileName="marksheet.pdf", contentType="application/pdf", sizeBytes=1000,
            status=DocumentStatus.EXTRACTED,
            extraction=DocumentExtraction(
                fields=[
                    ExtractedField(fieldKey="student_name", rawValue="ANTARJEET DASS", normalizedValue="antarjeet dass"),
                    ExtractedField(fieldKey="institution_name", rawValue="Cotton University", normalizedValue="cotton university"),
                ]
            ),
        ),
        DocumentItem(
            documentId="d3", role=DocumentRole.INCOME_CERTIFICATE, fileName="income.pdf", contentType="application/pdf", sizeBytes=1000,
            status=DocumentStatus.EXTRACTED,
            extraction=DocumentExtraction(
                fields=[
                    ExtractedField(fieldKey="annual_income", rawValue="2,50,000", normalizedValue=250000),
                    ExtractedField(fieldKey="income_cert_authority", rawValue="Circle Officer", normalizedValue="circle officer"),
                ]
            ),
        ),
        DocumentItem(
            documentId="d4", role=DocumentRole.BANK_PROOF, fileName="bank.pdf", contentType="application/pdf", sizeBytes=1000,
            status=DocumentStatus.EXTRACTED,
            extraction=DocumentExtraction(
                fields=[
                    ExtractedField(fieldKey="account_holder_name", rawValue="ANTARJIT DAS", normalizedValue="antarjit das"),
                ]
            ),
        ),
    ]

    mock_get_full.return_value = Packet(
        packetId="pkt-demo",
        status=PacketStatus.CHECKING,
        createdAt="2026-09-19T00:00:00Z",
        updatedAt="2026-09-19T00:00:00Z",
        documents=docs,
    )

    # Bedrock adjudicates the name mismatch as benign transliteration (isRealConflict=False)
    mock_bedrock.return_value = json.dumps({
        "results": [
            {
                "findingId": "f1",
                "isRealConflict": False,  # Downgrades RED -> AMBER!
                "confidence": 0.90,
                "reason": "Common transliteration variant of 'ANTARJIT DAS' vs 'ANTARJEET DASS'.",
                "fixInstruction": "Verify name spelling with college nodal officer.",
                "rankHint": 1,
            }
        ]
    })

    event = {"packetId": "pkt-demo", "checkRunId": "chk-123"}
    res = handle_run_check(event)

    assert res["status"] == "SUCCESS"
    assert res["packetId"] == "pkt-demo"
    assert res["checkRunId"] == "chk-123"

    # Verify save_verdict was called
    mock_save_verdict.assert_called_once()
    verdict: Verdict = mock_save_verdict.call_args[0][1]

    # Rule R-01 downgraded to AMBER (10 pts) + R-04 institution (10 pts) = 100 - 20 = 80 (RISKY)
    assert verdict.score == 80
    assert verdict.band.value == "RISKY"
    assert "10x2 amber = 80" in verdict.scoreArithmetic
    assert verdict.aiStatus == AIStatus.OK


# =====================================================================
# Test 4: run_check worker with Template Fallback
# =====================================================================

@patch("backend.src.handlers.run_check.get_full_packet")
@patch("backend.src.handlers.run_check.invoke_bedrock_structured")
@patch("backend.src.handlers.run_check.save_verdict")
def test_run_check_worker_template_fallback(mock_save_verdict, mock_bedrock, mock_get_full):
    """When Bedrock fails, run_check populates YAML template text with aiStatus=FALLBACK_TEMPLATE."""
    docs = [
        DocumentItem(
            documentId="d1", role=DocumentRole.AADHAAR, fileName="aadhaar.jpg", contentType="image/jpeg", sizeBytes=1000,
            status=DocumentStatus.EXTRACTED,
            extraction=DocumentExtraction(
                fields=[
                    ExtractedField(fieldKey="student_name", rawValue="ANTARJIT DAS", normalizedValue="antarjit das"),
                ]
            ),
        ),
        DocumentItem(
            documentId="d2", role=DocumentRole.MARKSHEET, fileName="marksheet.pdf", contentType="application/pdf", sizeBytes=1000,
            status=DocumentStatus.EXTRACTED,
            extraction=DocumentExtraction(
                fields=[
                    ExtractedField(fieldKey="student_name", rawValue="RAHUL DAS", normalizedValue="rahul das"),
                ]
            ),
        ),
        DocumentItem(
            documentId="d3", role=DocumentRole.INCOME_CERTIFICATE, fileName="income.pdf", contentType="application/pdf", sizeBytes=1000,
            status=DocumentStatus.EXTRACTED,
            extraction=DocumentExtraction(fields=[]),
        ),
    ]

    mock_get_full.return_value = Packet(
        packetId="pkt-fb",
        status=PacketStatus.CHECKING,
        createdAt="2026-09-19T00:00:00Z",
        updatedAt="2026-09-19T00:00:00Z",
        documents=docs,
    )

    # Bedrock fails completely
    mock_bedrock.return_value = None

    event = {"packetId": "pkt-fb", "checkRunId": "chk-fb"}
    res = handle_run_check(event)

    assert res["status"] == "SUCCESS"
    verdict: Verdict = mock_save_verdict.call_args[0][1]
    assert verdict.aiStatus == AIStatus.FALLBACK_TEMPLATE
    # Template reason was used on R-01 finding
    r01_finding = next(f for f in verdict.findings if f.ruleId == "R-01")
    assert "Your name is spelled differently" in r01_finding.reason
