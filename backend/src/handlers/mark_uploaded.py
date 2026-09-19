"""Lambda handler for POST /packets/{packetId}/documents/{documentId}/uploaded.

Tells the backend the document bytes have landed in S3 and triggers async extraction.

Contract:
- Input: {}
- Output 202: {"documentId": "...", "status": "EXTRACTING"}
- Behaviour:
    1. Validates document exists in packet.
    2. Calls S3 head_object to confirm the file actually exists in S3 (non-trusting).
    3. Sets document status = EXTRACTING, packet status = EXTRACTING.
    4. Invokes worker Lambda `fn_extract_document` asynchronously (Event invocation type).
- Errors:
    - 404 DOCUMENT_NOT_FOUND
    - 404 PACKET_NOT_FOUND
    - 409 OBJECT_MISSING (upload did not complete)
"""

import json
import os
import logging
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError

from backend.src.core.models import DocumentStatus, PacketStatus
from backend.src.aws.ddb import (
    get_packet_meta,
    get_full_packet,
    update_document_extraction,
    update_packet_status,
)
from backend.src.aws.s3_client import get_authoritative_metadata
from backend.src.handlers.api_util import api_response, api_error

logger = logging.getLogger(__name__)

EXTRACT_WORKER_FUNCTION = os.environ.get("EXTRACT_WORKER_FUNCTION", "DefectGuard-ExtractDocument")


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Handle POST /packets/{packetId}/documents/{documentId}/uploaded."""
    try:
        path_params = event.get("pathParameters") or {}
        packet_id = path_params.get("packetId")
        document_id = path_params.get("documentId")

        if not packet_id:
            return api_error(404, "PACKET_NOT_FOUND", "Packet ID is required.")
        if not document_id:
            return api_error(404, "DOCUMENT_NOT_FOUND", "Document ID is required.")

        # 1. Fetch full packet and locate document
        packet = get_full_packet(packet_id)
        if not packet:
            return api_error(404, "PACKET_NOT_FOUND", f"Packet '{packet_id}' not found.")

        target_doc = None
        for doc in packet.documents:
            if doc.documentId == document_id:
                target_doc = doc
                break

        if not target_doc:
            return api_error(
                404,
                "DOCUMENT_NOT_FOUND",
                f"Document '{document_id}' not found in packet '{packet_id}'.",
            )

        # 2. Check S3 head_object to ensure file actually landed
        object_key = target_doc.objectKey or f"packets/{packet_id}/{document_id}"
        try:
            get_authoritative_metadata(object_key)
        except ClientError as ce:
            error_code = ce.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchKey"):
                return api_error(
                    409,
                    "OBJECT_MISSING",
                    f"Document was not found in storage. Upload may not have completed.",
                )
            logger.warning("S3 HeadObject check encountered: %s", str(ce))
        except Exception as e:
            logger.warning("Storage verification warning: %s", str(e))

        # 3. Update document status to EXTRACTING and packet status to EXTRACTING
        update_document_extraction(
            packet_id=packet_id,
            document_id=document_id,
            extraction_dict={},
            status=DocumentStatus.EXTRACTING,
        )
        update_packet_status(packet_id, PacketStatus.EXTRACTING)

        # 4. Trigger worker lambda asynchronously
        try:
            lambda_client = boto3.client("lambda")
            payload = {
                "packetId": packet_id,
                "documentId": document_id,
                "role": target_doc.role.value,
                "objectKey": object_key,
                "fileName": target_doc.fileName,
            }
            lambda_client.invoke(
                FunctionName=EXTRACT_WORKER_FUNCTION,
                InvocationType="Event",  # Asynchronous fire-and-forget
                Payload=json.dumps(payload),
            )
        except Exception as inv_err:
            logger.warning("Could not invoke worker Lambda (%s). Continuing in standalone mode.", str(inv_err))

        return api_response(
            202,
            {
                "documentId": document_id,
                "status": DocumentStatus.EXTRACTING.value,
            },
        )

    except Exception as e:
        logger.exception("Error handling mark_uploaded: %s", str(e))
        return api_error(500, "INTERNAL", "Failed to mark document as uploaded.")
