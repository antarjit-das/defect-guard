"""HTTP API Gateway helper utilities for Lambda handlers.

Standardizes JSON response formatting, CORS headers, and error shapes
conforming strictly to IMPLEMENTATION.md §6:
    {"error": {"code": "...", "message": "..."}}
"""

import json
from typing import Dict, Any, Optional

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


def api_response(status_code: int, body: Any) -> Dict[str, Any]:
    """Format an API Gateway HTTP payload."""
    serialized = json.dumps(body) if not isinstance(body, str) else body
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": serialized,
    }


def api_error(status_code: int, code: str, message: str) -> Dict[str, Any]:
    """Format standard API error response conforming to contract."""
    return api_response(
        status_code=status_code,
        body={"error": {"code": code, "message": message}},
    )


def parse_request_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """Safely parse JSON request body from API Gateway proxy event."""
    body = event.get("body")
    if not body:
        return {}
    if isinstance(body, dict):
        return body
    try:
        return json.loads(body)
    except Exception:
        return {}
