"""Lambda handler for POST /packets.

Starts a new scholarship check packet in DRAFT status.
Contract:
- Input: {}
- Output 201: {"packetId": "...", "schemeId": "NIJUT_BABU_2026", "status": "DRAFT", "createdAt": "..."}
- Errors: 500 INTERNAL
"""

import uuid
import logging
from typing import Dict, Any

from backend.src.aws.ddb import create_packet_meta
from backend.src.handlers.api_util import api_response, api_error

logger = logging.getLogger(__name__)


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Handle POST /packets."""
    try:
        packet_id = str(uuid.uuid4())
        meta = create_packet_meta(packet_id=packet_id, scheme_id="NIJUT_BABU_2026")

        response_body = {
            "packetId": meta["packetId"],
            "schemeId": meta["schemeId"],
            "status": meta["status"],
            "createdAt": meta["createdAt"],
        }
        return api_response(201, response_body)

    except Exception as e:
        logger.exception("Failed to create packet: %s", str(e))
        return api_error(500, "INTERNAL", "Failed to create scholarship packet.")
