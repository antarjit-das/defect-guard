"""Lambda handler for GET /packets/{packetId}.

The single read endpoint polled by the frontend every 2 seconds.
Returns the complete Packet payload:
- packetId, schemeId, status, createdAt, updatedAt
- documents: List[DocumentItem] with extraction payloads
- verdict: Verdict (snapshot + findings + score + band + arithmetic)
- previousScore

Contract:
- Output 200: full Packet envelope
- Errors: 404 PACKET_NOT_FOUND
"""

import logging
from typing import Dict, Any

from ..aws.ddb import get_full_packet
from .api_util import api_response, api_error

logger = logging.getLogger(__name__)


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Handle GET /packets/{packetId}."""
    try:
        path_params = event.get("pathParameters") or {}
        packet_id = path_params.get("packetId")

        if not packet_id:
            return api_error(404, "PACKET_NOT_FOUND", "Packet ID is required.")

        packet = get_full_packet(packet_id)
        if not packet:
            return api_error(404, "PACKET_NOT_FOUND", f"Packet '{packet_id}' not found.")

        # Serialize packet Pydantic model directly to dict
        return api_response(200, packet.model_dump())

    except Exception as e:
        logger.exception("Error fetching packet: %s", str(e))
        return api_error(500, "INTERNAL", "Failed to retrieve scholarship packet.")
