"""Unit tests for the 5 API Gateway Lambda handlers.

Validates contract conformance, status codes, input validations, and error payloads.
"""

import json
from unittest.mock import patch, MagicMock

from backend.src.core.models import (
    Packet,
    PacketStatus,
    DocumentItem,
    DocumentRole,
    DocumentStatus,
)
from backend.src.handlers.create_packet import handler as handle_create_packet
from backend.src.handlers.create_upload_url import handler as handle_create_upload_url
from backend.src.handlers.mark_uploaded import handler as handle_mark_uploaded
from backend.src.handlers.run_check_api import handler as handle_run_check
from backend.src.handlers.get_packet import handler as handle_get_packet


# =====================================================================
# Test 1: POST /packets
# =====================================================================

@patch("backend.src.handlers.create_packet.create_packet_meta")
def test_handler_create_packet_success(mock_create_meta):
    """POST /packets returns 201 with packetId, status=DRAFT."""
    mock_create_meta.return_value = {
        "packetId": "pkt-uuid-1",
        "schemeId": "NIJUT_BABU_2026",
        "status": "DRAFT",
        "createdAt": "2026-09-19T00:00:00Z",
    }

    event = {"httpMethod": "POST", "body": "{}"}
    resp = handle_create_packet(event)

    assert resp["statusCode"] == 201
    body = json.loads(resp["body"])
    assert body["packetId"] == "pkt-uuid-1"
    assert body["schemeId"] == "NIJUT_BABU_2026"
    assert body["status"] == "DRAFT"


# =====================================================================
# Test 2: POST /packets/{id}/documents
# =====================================================================

@patch("backend.src.handlers.create_upload_url.get_packet_meta")
@patch("backend.src.handlers.create_upload_url.get_full_packet")
@patch("backend.src.handlers.create_upload_url.generate_presigned_upload_url")
@patch("backend.src.handlers.create_upload_url.register_document")
def test_handler_create_upload_url_success(mock_reg, mock_gen_url, mock_get_full, mock_get_meta):
    """POST /packets/{id}/documents returns 201 with presigned URL."""
    mock_get_meta.return_value = {"packetId": "pkt-1"}
    mock_get_full.return_value = Packet(
        packetId="pkt-1",
        status=PacketStatus.DRAFT,
        createdAt="2026-09-19T00:00:00Z",
        updatedAt="2026-09-19T00:00:00Z",
        documents=[],
    )
    mock_gen_url.return_value = {
        "uploadUrl": "https://s3.mock/upload",
        "objectKey": "packets/pkt-1/doc-1.pdf",
        "expiresInSeconds": 300,
    }

    event = {
        "httpMethod": "POST",
        "pathParameters": {"packetId": "pkt-1"},
        "body": json.dumps({
            "role": "AADHAAR",
            "fileName": "my_aadhaar.pdf",
            "contentType": "application/pdf",
            "sizeBytes": 150000,
        }),
    }
    resp = handle_create_upload_url(event)
    assert resp["statusCode"] == 201
    body = json.loads(resp["body"])
    assert "documentId" in body
    assert body["uploadUrl"] == "https://s3.mock/upload"
    assert body["objectKey"] == "packets/pkt-1/doc-1.pdf"


@patch("backend.src.handlers.create_upload_url.get_packet_meta")
def test_handler_create_upload_url_invalid_type(mock_get_meta):
    """POST /packets/{id}/documents rejects unsupported content types (e.g. text/plain)."""
    mock_get_meta.return_value = {"packetId": "pkt-1"}
    event = {
        "httpMethod": "POST",
        "pathParameters": {"packetId": "pkt-1"},
        "body": json.dumps({
            "role": "AADHAAR",
            "fileName": "notes.txt",
            "contentType": "text/plain",
            "sizeBytes": 1000,
        }),
    }
    resp = handle_create_upload_url(event)
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert body["error"]["code"] == "UNSUPPORTED_TYPE"


@patch("backend.src.handlers.create_upload_url.get_packet_meta")
def test_handler_create_upload_url_too_large(mock_get_meta):
    """POST /packets/{id}/documents rejects files larger than 5 MB."""
    mock_get_meta.return_value = {"packetId": "pkt-1"}
    event = {
        "httpMethod": "POST",
        "pathParameters": {"packetId": "pkt-1"},
        "body": json.dumps({
            "role": "MARKSHEET",
            "fileName": "big_marksheet.pdf",
            "contentType": "application/pdf",
            "sizeBytes": 6 * 1024 * 1024,  # 6 MB
        }),
    }
    resp = handle_create_upload_url(event)
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert body["error"]["code"] == "FILE_TOO_LARGE"


# =====================================================================
# Test 3: POST /packets/{id}/documents/{docId}/uploaded
# =====================================================================

@patch("backend.src.handlers.mark_uploaded.get_full_packet")
@patch("backend.src.handlers.mark_uploaded.get_authoritative_metadata")
@patch("backend.src.handlers.mark_uploaded.update_document_extraction")
@patch("backend.src.handlers.mark_uploaded.update_packet_status")
@patch("backend.src.handlers.mark_uploaded.boto3.client")
def test_handler_mark_uploaded_success(mock_boto, mock_up_status, mock_up_ext, mock_s3_meta, mock_get_full):
    """POST /uploaded returns 202 status=EXTRACTING and triggers async worker."""
    mock_get_full.return_value = Packet(
        packetId="pkt-1",
        status=PacketStatus.DRAFT,
        createdAt="2026-09-19T00:00:00Z",
        updatedAt="2026-09-19T00:00:00Z",
        documents=[
            DocumentItem(
                documentId="doc-1",
                role=DocumentRole.AADHAAR,
                fileName="aadhaar.pdf",
                contentType="application/pdf",
                sizeBytes=100000,
                objectKey="packets/pkt-1/doc-1.pdf",
            )
        ],
    )
    mock_s3_meta.return_value = {"contentLength": 100000, "contentType": "application/pdf"}

    event = {
        "httpMethod": "POST",
        "pathParameters": {"packetId": "pkt-1", "documentId": "doc-1"},
        "body": "{}",
    }
    resp = handle_mark_uploaded(event)
    assert resp["statusCode"] == 202
    body = json.loads(resp["body"])
    assert body["documentId"] == "doc-1"
    assert body["status"] == "EXTRACTING"


# =====================================================================
# Test 4: POST /packets/{id}/check
# =====================================================================

@patch("backend.src.handlers.run_check_api.get_full_packet")
@patch("backend.src.handlers.run_check_api.update_packet_status")
@patch("backend.src.handlers.run_check_api.boto3.client")
def test_handler_run_check_not_enough_docs(mock_boto, mock_up_status, mock_get_full):
    """POST /check returns 409 NOT_ENOUGH_DOCUMENTS if < 3 extracted documents exist."""
    mock_get_full.return_value = Packet(
        packetId="pkt-1",
        status=PacketStatus.DRAFT,
        createdAt="2026-09-19T00:00:00Z",
        updatedAt="2026-09-19T00:00:00Z",
        documents=[
            DocumentItem(
                documentId="doc-1",
                role=DocumentRole.AADHAAR,
                fileName="aadhaar.pdf",
                contentType="application/pdf",
                sizeBytes=100000,
                status=DocumentStatus.EXTRACTED,
            )
        ],
    )

    event = {
        "httpMethod": "POST",
        "pathParameters": {"packetId": "pkt-1"},
        "body": "{}",
    }
    resp = handle_run_check(event)
    assert resp["statusCode"] == 409
    body = json.loads(resp["body"])
    assert body["error"]["code"] == "NOT_ENOUGH_DOCUMENTS"
    assert body["extracted"] == 1
    assert body["required"] == 3


@patch("backend.src.handlers.run_check_api.get_full_packet")
@patch("backend.src.handlers.run_check_api.update_packet_status")
@patch("backend.src.handlers.run_check_api.boto3.client")
def test_handler_run_check_success(mock_boto, mock_up_status, mock_get_full):
    """POST /check returns 202 status=CHECKING when >= 3 docs are extracted."""
    docs = []
    for r in [DocumentRole.AADHAAR, DocumentRole.MARKSHEET, DocumentRole.BANK_PROOF]:
        docs.append(
            DocumentItem(
                documentId=f"doc-{r.value}",
                role=r,
                fileName=f"{r.value}.pdf",
                contentType="application/pdf",
                sizeBytes=100000,
                status=DocumentStatus.EXTRACTED,
            )
        )

    mock_get_full.return_value = Packet(
        packetId="pkt-1",
        status=PacketStatus.READY_TO_CHECK,
        createdAt="2026-09-19T00:00:00Z",
        updatedAt="2026-09-19T00:00:00Z",
        documents=docs,
    )

    event = {
        "httpMethod": "POST",
        "pathParameters": {"packetId": "pkt-1"},
        "body": "{}",
    }
    resp = handle_run_check(event)
    assert resp["statusCode"] == 202
    body = json.loads(resp["body"])
    assert "checkRunId" in body
    assert body["status"] == "CHECKING"


# =====================================================================
# Test 5: GET /packets/{id}
# =====================================================================

@patch("backend.src.handlers.get_packet.get_full_packet")
def test_handler_get_packet_success(mock_get_full):
    """GET /packets/{id} returns 200 with full packet payload."""
    mock_get_full.return_value = Packet(
        packetId="pkt-1",
        status=PacketStatus.CHECKED,
        createdAt="2026-09-19T00:00:00Z",
        updatedAt="2026-09-19T00:00:00Z",
        documents=[],
    )

    event = {
        "httpMethod": "GET",
        "pathParameters": {"packetId": "pkt-1"},
    }
    resp = handle_get_packet(event)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["packetId"] == "pkt-1"
    assert body["status"] == "CHECKED"


@patch("backend.src.handlers.get_packet.get_full_packet")
def test_handler_get_packet_not_found(mock_get_full):
    """GET /packets/{id} returns 404 if packet does not exist."""
    mock_get_full.return_value = None

    event = {
        "httpMethod": "GET",
        "pathParameters": {"packetId": "pkt-nonexistent"},
    }
    resp = handle_get_packet(event)
    assert resp["statusCode"] == 404
    body = json.loads(resp["body"])
    assert body["error"]["code"] == "PACKET_NOT_FOUND"
