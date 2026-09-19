"""Lambda handler for POST /packets/{packetId}/documents.

Registers an uploaded document slot and returns a presigned S3 PUT URL.
Re-registering an existing role supersedes the previous document.

Contract:
- Input: {"role": "...", "fileName": "...", "contentType": "...", "sizeBytes": ...}
- Output 201: {"documentId": "...", "uploadUrl": "https://...", "expiresInSeconds": 300, "objectKey": "..."}
- Rules:
    - contentType in {application/pdf, image/jpeg, image/png}
    - sizeBytes <= 5 242 880 (5 MB)
    - role must be in {AADHAAR, INCOME_CERTIFICATE, MARKSHEET, BANK_PROOF}
- Errors:
    - 400 UNSUPPORTED_TYPE
    - 400 FILE_TOO_LARGE
    - 400 UNKNOWN_ROLE
    - 404 PACKET_NOT_FOUND
"""

import uuid
import logging
from typing import Dict, Any

from backend.src.core.models import DocumentRole, DocumentItem, DocumentStatus
from backend.src.core.validators import (
    validate_upload_constraints,
    ALLOWED_MIME_TYPES,
    MAX_FILE_BYTES,
)
from backend.src.aws.ddb import get_packet_meta, get_full_packet, register_document
from backend.src.aws.s3_client import generate_presigned_upload_url
from backend.src.handlers.api_util import api_response, api_error, parse_request_body

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Handle POST /packets/{packetId}/documents."""
    try:
        path_params = event.get("pathParameters") or {}
        packet_id = path_params.get("packetId")
        if not packet_id:
            return api_error(404, "PACKET_NOT_FOUND", "Packet ID is required.")

        # Verify packet exists in DynamoDB
        meta = get_packet_meta(packet_id)
        if not meta:
            return api_error(404, "PACKET_NOT_FOUND", f"Packet '{packet_id}' not found.")

        body = parse_request_body(event)
        role_raw = body.get("role")
        file_name = body.get("fileName", "").strip()
        content_type = body.get("contentType", "").strip().lower()
        size_bytes = body.get("sizeBytes")

        # 1. Validate role
        try:
            role = DocumentRole(role_raw)
        except (ValueError, KeyError):
            return api_error(
                400,
                "UNKNOWN_ROLE",
                f"Role '{role_raw}' is not one of: AADHAAR, INCOME_CERTIFICATE, MARKSHEET, BANK_PROOF.",
            )

        # 2. Validate upload constraints (MIME and size)
        is_valid, err_msg, _ = validate_upload_constraints(content_type, size_bytes)
        if not is_valid:
            if content_type not in ALLOWED_MIME_TYPES:
                return api_error(400, "UNSUPPORTED_TYPE", err_msg or "Unsupported file format.")
            return api_error(400, "FILE_TOO_LARGE", err_msg or "File exceeds 5 MB limit.")

        # 4. Check if a document already exists for this role (for replacement/superseding)
        existing_packet = get_full_packet(packet_id)
        superseded_doc_id = None
        if existing_packet:
            for doc in existing_packet.documents:
                # Find current active document for this role
                if doc.role == role and doc.supersededBy is None:
                    superseded_doc_id = doc.documentId
                    break

        # 5. Generate documentId and Presigned S3 PUT URL
        document_id = str(uuid.uuid4())
        upload_data = generate_presigned_upload_url(
            packet_id=packet_id,
            document_id=document_id,
            file_name=file_name,
            content_type=content_type,
        )

        # 6. Save new DocumentItem in DynamoDB (AP3)
        doc_item = DocumentItem(
            documentId=document_id,
            role=role,
            fileName=file_name,
            contentType=content_type,
            sizeBytes=size_bytes,
            status=DocumentStatus.PENDING_UPLOAD,
            objectKey=upload_data["objectKey"],
        )
        register_document(packet_id, doc_item, superseded_doc_id=superseded_doc_id)

        return api_response(
            201,
            {
                "documentId": document_id,
                "uploadUrl": upload_data["uploadUrl"],
                "expiresInSeconds": upload_data["expiresInSeconds"],
                "objectKey": upload_data["objectKey"],
            },
        )

    except Exception as e:
        logger.exception("Error creating upload URL: %s", str(e))
        return api_error(500, "INTERNAL", "Failed to generate upload URL.")
