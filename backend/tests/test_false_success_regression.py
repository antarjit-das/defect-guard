"""Regression tests for false-success document extraction bug.

Verifies:
- Test A: DocumentExtraction with fields=[] is not considered usable.
- Test B: Worker receiving extraction with zero usable fields marks EXTRACTION_FAILED with error.
- Test C: Textract failure (e.g. SubscriptionRequiredException) results in EXTRACTION_FAILED.
- Test D: Bedrock failure + empty fallback results in EXTRACTION_FAILED.
- Test E: Bedrock failure + usable fallback fields preserves successful EXTRACTED status.
- Test F: EXTRACTION_FAILED and unusable documents are excluded from Application Snapshot.
"""

import json
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

from backend.src.core.models import (
    DocumentItem,
    DocumentRole,
    DocumentStatus,
    DocumentExtraction,
    ExtractedField,
    Packet,
    PacketStatus,
    is_usable_extraction,
    is_usable_field,
)
from backend.src.core.snapshot import build_snapshot
from backend.src.handlers.extract_document import handler as handle_extract_document


# =====================================================================
# Test A — empty fields predicate
# =====================================================================

def test_a_empty_fields_not_successful():
    """A completed extraction with fields=[] must not be considered successful."""
    # 1. Empty field list
    extraction_empty = DocumentExtraction(fields=[])
    assert is_usable_extraction(extraction_empty) is False
    assert extraction_empty.is_usable() is False

    # 2. None extraction
    assert is_usable_extraction(None) is False

    # 3. Fields with only null or whitespace values
    extraction_nulls = DocumentExtraction(
        fields=[
            ExtractedField(fieldKey="student_name", rawValue=None, normalizedValue=None),
            ExtractedField(fieldKey="annual_income", rawValue="   ", normalizedValue=""),
        ]
    )
    assert is_usable_extraction(extraction_nulls) is False
    assert extraction_nulls.is_usable() is False

    # 4. Fields with at least one usable value
    extraction_valid = DocumentExtraction(
        fields=[
            ExtractedField(fieldKey="student_name", rawValue="ANTARJIT DAS", normalizedValue="antarjit das"),
        ]
    )
    assert is_usable_extraction(extraction_valid) is True
    assert extraction_valid.is_usable() is True


# =====================================================================
# Test B — empty extraction reaches worker
# =====================================================================

@patch("backend.src.handlers.extract_document.get_authoritative_metadata")
@patch("backend.src.handlers.extract_document.extract_document_sync")
@patch("backend.src.handlers.extract_document.invoke_bedrock_structured")
@patch("backend.src.handlers.extract_document.update_document_extraction")
@patch("backend.src.handlers.extract_document.get_full_packet")
@patch("backend.src.handlers.extract_document.update_packet_status")
def test_b_empty_extraction_reaches_worker(
    mock_up_pkt, mock_get_full, mock_up_doc, mock_bedrock, mock_textract, mock_s3_meta
):
    """Simulate Bedrock returning zero usable fields: status must become EXTRACTION_FAILED with error."""
    mock_s3_meta.return_value = {"contentLength": 100000, "contentType": "image/jpeg"}
    mock_textract.return_value = {
        "query_answers": {},
        "form_kvs": {},
        "raw_lines": ["Government of India", "Aadhaar Card"],
        "mean_confidence": 0.90,
        "page_count": 1,
    }

    # Bedrock returns schema-valid JSON, but with zero fields
    mock_bedrock.return_value = json.dumps({
        "roleConfirmed": True,
        "documentQuality": "GOOD",
        "fields": [],
        "notes": "Could not identify any fields",
    })

    event = {
        "packetId": "pkt-b",
        "documentId": "doc-b",
        "role": "AADHAAR",
        "objectKey": "packets/pkt-b/doc-b.jpg",
    }

    res = handle_extract_document(event)

    assert res["status"] == "FAILED"
    assert "error" in res
    assert res["error"] == "No usable fields could be extracted from document"

    # Verify update_document_extraction called with EXTRACTION_FAILED and error
    mock_up_doc.assert_called_once()
    call_kwargs = mock_up_doc.call_args[1]
    assert call_kwargs["status"] == DocumentStatus.EXTRACTION_FAILED
    assert call_kwargs["error"] == "No usable fields could be extracted from document"
    assert call_kwargs.get("extraction_dict") is None

    # Verify packet status was NOT updated to READY_TO_CHECK
    mock_up_pkt.assert_not_called()


@patch("backend.src.handlers.extract_document.get_authoritative_metadata")
@patch("backend.src.handlers.extract_document.extract_document_sync")
@patch("backend.src.handlers.extract_document.invoke_bedrock_structured")
@patch("backend.src.handlers.extract_document.update_document_extraction")
@patch("backend.src.handlers.extract_document.update_packet_status")
def test_b2_textract_empty_ocr_distinguished(
    mock_up_pkt, mock_up_doc, mock_bedrock, mock_textract, mock_s3_meta
):
    """Textract completes cleanly but produces no OCR lines or queries: fails without calling Bedrock."""
    mock_s3_meta.return_value = {"contentLength": 50000, "contentType": "image/jpeg"}
    mock_textract.return_value = {
        "query_answers": {},
        "form_kvs": {},
        "raw_lines": [],
        "mean_confidence": 0.0,
        "page_count": 1,
    }

    event = {
        "packetId": "pkt-b2",
        "documentId": "doc-b2",
        "role": "AADHAAR",
        "objectKey": "packets/pkt-b2/doc-b2.jpg",
    }

    res = handle_extract_document(event)

    assert res["status"] == "FAILED"
    assert "Textract completed but detected no readable text" in res["error"]

    mock_up_doc.assert_called_once()
    call_kwargs = mock_up_doc.call_args[1]
    assert call_kwargs["status"] == DocumentStatus.EXTRACTION_FAILED
    assert "Textract completed but detected no readable text" in call_kwargs["error"]

    # Bedrock must not be invoked on empty OCR
    mock_bedrock.assert_not_called()
    mock_up_pkt.assert_not_called()


# =====================================================================
# Test C — Textract failure
# =====================================================================

@patch("backend.src.handlers.extract_document.get_authoritative_metadata")
@patch("backend.src.handlers.extract_document.extract_document_sync")
@patch("backend.src.handlers.extract_document.invoke_bedrock_structured")
@patch("backend.src.handlers.extract_document.update_document_extraction")
@patch("backend.src.handlers.extract_document.update_packet_status")
def test_c_textract_failure_becomes_extraction_failed(
    mock_up_pkt, mock_up_doc, mock_bedrock, mock_textract, mock_s3_meta
):
    """Simulate Textract client raising an exception: status must become EXTRACTION_FAILED."""
    mock_s3_meta.return_value = {"contentLength": 80000, "contentType": "application/pdf"}

    # Simulate SubscriptionRequiredException from AWS Textract
    tex_error = ClientError(
        {
            "Error": {
                "Code": "SubscriptionRequiredException",
                "Message": "The AWS Access Key Id needs a subscription for the service",
            }
        },
        "AnalyzeDocument",
    )
    mock_textract.side_effect = tex_error
    mock_bedrock.return_value = None

    event = {
        "packetId": "pkt-c",
        "documentId": "doc-c",
        "role": "MARKSHEET",
        "objectKey": "packets/pkt-c/doc-c.pdf",
    }

    res = handle_extract_document(event)

    assert res["status"] == "FAILED"
    assert "error" in res

    # Must NOT become EXTRACTED
    mock_up_doc.assert_called_once()
    call_kwargs = mock_up_doc.call_args[1]
    assert call_kwargs["status"] == DocumentStatus.EXTRACTION_FAILED
    assert call_kwargs["status"] != DocumentStatus.EXTRACTED
    assert "SubscriptionRequiredException" in call_kwargs["error"]
    assert "Textract service failure" in call_kwargs["error"]
    assert call_kwargs.get("extraction_dict") is None

    # Bedrock must not be invoked when Textract failed
    mock_bedrock.assert_not_called()
    mock_up_pkt.assert_not_called()


# =====================================================================
# Test D — Bedrock failure + empty fallback
# =====================================================================

@patch("backend.src.handlers.extract_document.get_authoritative_metadata")
@patch("backend.src.handlers.extract_document.extract_document_sync")
@patch("backend.src.handlers.extract_document.invoke_bedrock_structured")
@patch("backend.src.handlers.extract_document.update_document_extraction")
@patch("backend.src.handlers.extract_document.update_packet_status")
def test_d_bedrock_failure_empty_fallback(
    mock_up_pkt, mock_up_doc, mock_bedrock, mock_textract, mock_s3_meta
):
    """Textract succeeds, Bedrock fails, fallback produces zero fields -> EXTRACTION_FAILED."""
    mock_s3_meta.return_value = {"contentLength": 95000, "contentType": "image/jpeg"}
    mock_textract.return_value = {
        "query_answers": {},  # Textract found no answers for role queries
        "form_kvs": {},
        "raw_lines": ["Some random unparseable stamp"],
        "mean_confidence": 0.80,
        "page_count": 1,
    }

    # Bedrock invocation raises exception
    mock_bedrock.side_effect = Exception("ValidationException: Bedrock model invocation failed")

    event = {
        "packetId": "pkt-d",
        "documentId": "doc-d",
        "role": "BANK_PROOF",
        "objectKey": "packets/pkt-d/doc-d.jpg",
    }

    res = handle_extract_document(event)

    assert res["status"] == "FAILED"
    mock_up_doc.assert_called_once()
    call_kwargs = mock_up_doc.call_args[1]
    assert call_kwargs["status"] == DocumentStatus.EXTRACTION_FAILED
    assert "No usable fields" in call_kwargs["error"]
    assert call_kwargs.get("extraction_dict") is None

    mock_up_pkt.assert_not_called()


# =====================================================================
# Test E — fallback with usable fields
# =====================================================================

@patch("backend.src.handlers.extract_document.get_authoritative_metadata")
@patch("backend.src.handlers.extract_document.extract_document_sync")
@patch("backend.src.handlers.extract_document.invoke_bedrock_structured")
@patch("backend.src.handlers.extract_document.update_document_extraction")
@patch("backend.src.handlers.extract_document.get_full_packet")
def test_e_fallback_with_usable_fields(
    mock_get_full, mock_up_doc, mock_bedrock, mock_textract, mock_s3_meta
):
    """Textract succeeds, Bedrock fails, but fallback produces usable fields -> EXTRACTED."""
    mock_s3_meta.return_value = {"contentLength": 110000, "contentType": "image/jpeg"}
    mock_textract.return_value = {
        "query_answers": {
            "What is the name?": "ANTARJIT DAS",
            "What is the date of birth?": "12/03/2004",
        },
        "form_kvs": {},
        "raw_lines": ["Government of India", "ANTARJIT DAS", "12/03/2004"],
        "mean_confidence": 0.95,
        "page_count": 1,
    }

    # Bedrock fails
    mock_bedrock.side_effect = Exception("Bedrock throttled")
    mock_get_full.return_value = None

    event = {
        "packetId": "pkt-e",
        "documentId": "doc-e",
        "role": "AADHAAR",
        "objectKey": "packets/pkt-e/doc-e.jpg",
    }

    res = handle_extract_document(event)

    assert res["status"] == "SUCCESS"
    assert res["documentId"] == "doc-e"

    # Must preserve EXTRACTED status with the fallback fields
    mock_up_doc.assert_called_once()
    call_kwargs = mock_up_doc.call_args[1]
    assert call_kwargs["status"] == DocumentStatus.EXTRACTED

    ext_dict = call_kwargs["extraction_dict"]
    assert ext_dict is not None
    assert ext_dict["roleConfirmed"] is True
    assert len(ext_dict["fields"]) >= 2

    name_field = next(f for f in ext_dict["fields"] if f["fieldKey"] == "student_name")
    assert name_field["rawValue"] == "ANTARJIT DAS"
    assert name_field["normalizedValue"] == "antarjit das"


# =====================================================================
# Test F — failed documents excluded from snapshot
# =====================================================================

def test_f_failed_documents_excluded_from_snapshot():
    """Documents with EXTRACTION_FAILED or unusable extraction do not contribute to snapshot."""
    doc_extracted = DocumentItem(
        documentId="doc-valid",
        role=DocumentRole.AADHAAR,
        fileName="aadhaar.jpg",
        contentType="image/jpeg",
        sizeBytes=100000,
        status=DocumentStatus.EXTRACTED,
        extraction=DocumentExtraction(
            roleConfirmed=True,
            documentQuality=DocumentExtraction().documentQuality,
            fields=[
                ExtractedField(fieldKey="student_name", rawValue="ANTARJIT DAS", normalizedValue="antarjit das"),
            ],
        ),
    )

    doc_failed = DocumentItem(
        documentId="doc-fail",
        role=DocumentRole.MARKSHEET,
        fileName="marksheet.pdf",
        contentType="application/pdf",
        sizeBytes=120000,
        status=DocumentStatus.EXTRACTION_FAILED,
        extraction=None,
        error="No usable fields could be extracted from document (Textract SubscriptionRequiredException)",
    )

    doc_empty_extracted = DocumentItem(
        documentId="doc-empty",
        role=DocumentRole.BANK_PROOF,
        fileName="bank.pdf",
        contentType="application/pdf",
        sizeBytes=110000,
        status=DocumentStatus.EXTRACTED,
        extraction=DocumentExtraction(fields=[]),  # Empty fields edge case
    )

    snapshot = build_snapshot([doc_extracted, doc_failed, doc_empty_extracted])

    # Only 1 row should be in snapshot from the single valid document
    assert len(snapshot.rows) == 1
    row = snapshot.rows[0]
    assert row.fieldKey == "student_name"
    assert row.canonicalValue == "ANTARJIT DAS"
    assert "MARKSHEET" not in row.valuesByRole
    assert "BANK_PROOF" not in row.valuesByRole
    assert row.valuesByRole == {"AADHAAR": "ANTARJIT DAS"}
