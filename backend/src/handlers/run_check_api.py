"""Lambda handler for POST /packets/{packetId}/check.

Triggers the deterministic rules engine and AI adjudication pipeline.

Contract:
- Input: {}
- Output 202: {"checkRunId": "...", "status": "CHECKING"}
- Behaviour:
    1. Requires all four mandatory roles with status = EXTRACTED.
    2. Prevents re-run if packet status is currently CHECKING (409 ALREADY_RUNNING).
    3. Sets packet status = CHECKING.
    4. Invokes worker Lambda `fn_run_check` asynchronously (Event invocation type).
- Errors:
    - 404 PACKET_NOT_FOUND
    - 409 DOCUMENTS_NOT_READY (one or more mandatory documents are still processing)
    - 409 ALREADY_RUNNING
"""

import os
import uuid
import json
import logging
from typing import Dict, Any
import boto3

from backend.src.core.models import PacketStatus, DocumentStatus, is_usable_extraction
from backend.src.aws.ddb import get_full_packet, update_packet_status
from backend.src.handlers.api_util import api_response, api_error

logger = logging.getLogger(__name__)

RUN_CHECK_WORKER_FUNCTION = os.environ.get("RUN_CHECK_WORKER_FUNCTION", "DefectGuard-RunCheck")
REQUIRED_DOCUMENT_ROLES = {"AADHAAR", "INCOME_CERTIFICATE", "MARKSHEET", "BANK_PROOF"}


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Handle POST /packets/{packetId}/check."""
    try:
        path_params = event.get("pathParameters") or {}
        packet_id = path_params.get("packetId")

        if not packet_id:
            return api_error(404, "PACKET_NOT_FOUND", "Packet ID is required.")

        packet = get_full_packet(packet_id)
        if not packet:
            return api_error(404, "PACKET_NOT_FOUND", f"Packet '{packet_id}' not found.")

        # 1. Prevent overlapping runs
        if packet.status == PacketStatus.CHECKING:
            return api_error(
                409,
                "ALREADY_RUNNING",
                "A defect check is currently in progress for this packet.",
            )

        # 2. Require every mandatory role to finish extraction before a verdict.
        # This prevents a transient EXTRACTING replacement from being scored as
        # missing by the rule engine.
        extracted_roles = set()
        for doc in packet.documents:
            if doc.supersededBy is None and doc.status == DocumentStatus.EXTRACTED:
                if doc.extraction is not None and not is_usable_extraction(doc.extraction):
                    continue
                role = doc.role.value if hasattr(doc.role, "value") else str(doc.role)
                extracted_roles.add(role)

        missing_roles = sorted(REQUIRED_DOCUMENT_ROLES - extracted_roles)
        if missing_roles:
            return api_response(
                409,
                {
                    "error": {
                        "code": "DOCUMENTS_NOT_READY",
                        "message": (
                            "All mandatory documents must finish extraction before a check can run. "
                            f"Still processing or missing: {', '.join(missing_roles)}."
                        ),
                    },
                    "extractedRoles": sorted(extracted_roles),
                    "pendingRoles": missing_roles,
                },
            )

        # 3. Generate checkRunId and update status to CHECKING
        check_run_id = str(uuid.uuid4())
        update_packet_status(packet_id, PacketStatus.CHECKING)

        # 4. Trigger worker lambda asynchronously
        try:
            lambda_client = boto3.client("lambda")
            payload = {
                "packetId": packet_id,
                "checkRunId": check_run_id,
            }
            lambda_client.invoke(
                FunctionName=RUN_CHECK_WORKER_FUNCTION,
                InvocationType="Event",
                Payload=json.dumps(payload),
            )
        except Exception as inv_err:
            logger.warning("Could not invoke run_check worker Lambda (%s). Continuing.", str(inv_err))

        return api_response(
            202,
            {
                "checkRunId": check_run_id,
                "status": PacketStatus.CHECKING.value,
            },
        )

    except Exception as e:
        logger.exception("Error initiating check run: %s", str(e))
        return api_error(500, "INTERNAL", "Failed to start defect check.")
