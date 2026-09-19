"""DynamoDB single-table client for Defect Guard.

Strictly implements IMPLEMENTATION.md §5 single table design:
- Table: DefectGuard (PAY_PER_REQUEST, TTL on expiresAt = now + 86400).
- PK: PACKET#<packetId>
- SK: META | DOC#<documentId> | VERDICT#<isoTimestamp>
- Access Patterns:
    AP1: Read packet metadata -> GetItem(pk, "META")
    AP2: Read the whole packet -> Query(pk) (META + DOC#* + VERDICT#*)
    AP3: Create/replace a document -> PutItem(DOC#) + UpdateItem(old doc supersededBy)
    AP4: Store an extraction -> UpdateItem(pk, "DOC#<id>") setting extraction and status
    AP5: Append a verdict -> PutItem(VERDICT#) + UpdateItem(META)
- No GSI, zero Scan operations.
"""

import os
import time
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Any, Optional
import boto3
from boto3.dynamodb.conditions import Key
from botocore.config import Config

from backend.src.core.models import (
    Packet,
    PacketStatus,
    DocumentItem,
    DocumentStatus,
    Verdict,
)

logger = logging.getLogger(__name__)

DEFAULT_REGION = os.environ.get("AWS_REGION", "ap-south-1")
DEFAULT_TABLE = os.environ.get("DYNAMODB_TABLE", "DefectGuard")
TTL_SECONDS = 86400  # 24 hours retention


def get_dynamodb_resource(region_name: str = DEFAULT_REGION):
    """Factory to get DynamoDB high-level resource."""
    return boto3.resource(
        "dynamodb",
        region_name=region_name,
        config=Config(retries={"max_attempts": 3, "mode": "standard"}),
    )


def compute_ttl(seconds_from_now: int = TTL_SECONDS) -> int:
    """Return epoch seconds integer for expiresAt."""
    return int(time.time()) + seconds_from_now


def floats_to_decimals(obj: Any) -> Any:
    """Convert float values to Decimal for DynamoDB serialization."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: floats_to_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [floats_to_decimals(x) for x in obj]
    return obj


def decimals_to_floats(obj: Any) -> Any:
    """Convert DynamoDB Decimals back to float/int for Pydantic."""
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    if isinstance(obj, dict):
        return {k: decimals_to_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [decimals_to_floats(x) for x in obj]
    return obj


# =====================================================================
# Access Pattern AP1: Read Packet Metadata
# =====================================================================

def get_packet_meta(
    packet_id: str,
    table_name: Optional[str] = None,
    resource: Optional[Any] = None,
) -> Optional[Dict[str, Any]]:
    """AP1: Read packet metadata item via GetItem(pk='PACKET#<id>', sk='META')."""
    ddb = resource or get_dynamodb_resource()
    table = ddb.Table(table_name or DEFAULT_TABLE)

    pk = f"PACKET#{packet_id}"
    resp = table.get_item(Key={"pk": pk, "sk": "META"})
    item = resp.get("Item")
    if not item:
        return None
    return decimals_to_floats(item)


# =====================================================================
# Access Pattern AP2: Read Whole Packet for UI Envelope
# =====================================================================

def get_full_packet(
    packet_id: str,
    table_name: Optional[str] = None,
    resource: Optional[Any] = None,
) -> Optional[Packet]:
    """AP2: Read whole packet using single Query(pk='PACKET#<id>').

    Assembles META + all DOC# items + latest VERDICT# item into a typed Packet.
    """
    ddb = resource or get_dynamodb_resource()
    table = ddb.Table(table_name or DEFAULT_TABLE)

    pk = f"PACKET#{packet_id}"
    resp = table.query(KeyConditionExpression=Key("pk").eq(pk))
    items = resp.get("Items", [])
    if len(items) == 0:
        return None

    meta_item: Optional[Dict[str, Any]] = None
    doc_items: List[Dict[str, Any]] = []
    verdict_items: List[Dict[str, Any]] = []

    for it in items:
        clean_it = decimals_to_floats(it)
        sk = clean_it.get("sk", "")
        if sk == "META":
            meta_item = clean_it
        elif sk.startswith("DOC#"):
            doc_items.append(clean_it)
        elif sk.startswith("VERDICT#"):
            verdict_items.append(clean_it)

    if not meta_item:
        return None

    # Sort verdicts by createdAt or sk desc to get the newest
    latest_verdict: Optional[Verdict] = None
    if len(verdict_items) > 0:
        # Sort descending by sk (which has ISO timestamp)
        sorted_verdicts = sorted(verdict_items, key=lambda x: x.get("sk", ""), reverse=True)
        newest_raw = sorted_verdicts[0]
        # Remove DynamoDB keys before validating with Pydantic
        newest_raw_clean = dict(newest_raw)
        newest_raw_clean.pop("pk", None)
        newest_raw_clean.pop("sk", None)
        latest_verdict = Verdict.model_validate(newest_raw_clean)

    # Assemble DocumentItem objects
    parsed_docs: List[DocumentItem] = []
    for d in doc_items:
        d_clean = dict(d)
        d_clean.pop("pk", None)
        d_clean.pop("sk", None)
        parsed_docs.append(DocumentItem.model_validate(d_clean))

    packet_payload = {
        "packetId": meta_item["packetId"],
        "schemeId": meta_item.get("schemeId", "NIJUT_BABU_2026"),
        "status": meta_item.get("status", PacketStatus.DRAFT),
        "createdAt": meta_item["createdAt"],
        "updatedAt": meta_item.get("updatedAt", meta_item["createdAt"]),
        "documents": parsed_docs,
        "verdict": latest_verdict,
        "previousScore": meta_item.get("previousScore"),
        "expiresAt": meta_item.get("expiresAt"),
    }

    return Packet.model_validate(packet_payload)


# =====================================================================
# Packet Creation
# =====================================================================

def create_packet_meta(
    packet_id: str,
    scheme_id: str = "NIJUT_BABU_2026",
    table_name: Optional[str] = None,
    resource: Optional[Any] = None,
) -> Dict[str, Any]:
    """Create initial META item for a new scholarship packet."""
    ddb = resource or get_dynamodb_resource()
    table = ddb.Table(table_name or DEFAULT_TABLE)

    now_iso = datetime.now(timezone.utc).isoformat()
    ttl = compute_ttl()

    item = {
        "pk": f"PACKET#{packet_id}",
        "sk": "META",
        "packetId": packet_id,
        "schemeId": scheme_id,
        "status": PacketStatus.DRAFT.value,
        "createdAt": now_iso,
        "updatedAt": now_iso,
        "expiresAt": ttl,
    }

    table.put_item(Item=floats_to_decimals(item))
    return item


# =====================================================================
# Access Pattern AP3: Register/Replace Document
# =====================================================================

def register_document(
    packet_id: str,
    doc_item: DocumentItem,
    superseded_doc_id: Optional[str] = None,
    table_name: Optional[str] = None,
    resource: Optional[Any] = None,
) -> None:
    """AP3: PutItem for new DOC#, plus optional UpdateItem on old document setting supersededBy."""
    ddb = resource or get_dynamodb_resource()
    table = ddb.Table(table_name or DEFAULT_TABLE)

    pk = f"PACKET#{packet_id}"
    sk = f"DOC#{doc_item.documentId}"
    ttl = compute_ttl()

    raw_dict = doc_item.model_dump()
    raw_dict["pk"] = pk
    raw_dict["sk"] = sk
    raw_dict["expiresAt"] = ttl

    # Convert Enums to strings
    if hasattr(raw_dict.get("role"), "value"):
        raw_dict["role"] = raw_dict["role"].value
    if hasattr(raw_dict.get("status"), "value"):
        raw_dict["status"] = raw_dict["status"].value

    table.put_item(Item=floats_to_decimals(raw_dict))

    # Mark old document as superseded if specified
    if superseded_doc_id:
        table.update_item(
            Key={"pk": pk, "sk": f"DOC#{superseded_doc_id}"},
            UpdateExpression="SET supersededBy = :sid",
            ExpressionAttributeValues={":sid": doc_item.documentId},
        )

    # Touch packet updatedAt
    now_iso = datetime.now(timezone.utc).isoformat()
    table.update_item(
        Key={"pk": pk, "sk": "META"},
        UpdateExpression="SET updatedAt = :u",
        ExpressionAttributeValues={":u": now_iso},
    )


# =====================================================================
# Access Pattern AP4: Store Extraction
# =====================================================================

def update_document_extraction(
    packet_id: str,
    document_id: str,
    extraction_dict: Dict[str, Any],
    status: DocumentStatus = DocumentStatus.EXTRACTED,
    error: Optional[str] = None,
    table_name: Optional[str] = None,
    resource: Optional[Any] = None,
) -> None:
    """AP4: Update DOC# item setting extraction and status."""
    ddb = resource or get_dynamodb_resource()
    table = ddb.Table(table_name or DEFAULT_TABLE)

    pk = f"PACKET#{packet_id}"
    sk = f"DOC#{document_id}"

    status_val = status.value if hasattr(status, "value") else str(status)

    update_expr = "SET #st = :st, extraction = :ex"
    expr_names = {"#st": "status"}
    expr_values = {
        ":st": status_val,
        ":ex": floats_to_decimals(extraction_dict),
    }

    if error:
        update_expr += ", #err = :err"
        expr_names["#err"] = "error"
        expr_values[":err"] = error

    table.update_item(
        Key={"pk": pk, "sk": sk},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )


# =====================================================================
# Access Pattern AP5: Append Verdict
# =====================================================================

def save_verdict(
    packet_id: str,
    verdict: Verdict,
    table_name: Optional[str] = None,
    resource: Optional[Any] = None,
) -> None:
    """AP5: PutItem on VERDICT#<ts> and UpdateItem on META setting latestVerdictSk, status=CHECKED."""
    ddb = resource or get_dynamodb_resource()
    table = ddb.Table(table_name or DEFAULT_TABLE)

    pk = f"PACKET#{packet_id}"
    verdict_sk = f"VERDICT#{verdict.createdAt}"
    ttl = compute_ttl()

    verdict_dict = verdict.model_dump()
    verdict_dict["pk"] = pk
    verdict_dict["sk"] = verdict_sk
    verdict_dict["expiresAt"] = ttl

    # Write VERDICT# item
    table.put_item(Item=floats_to_decimals(verdict_dict))

    # Fetch prior score from META before updating
    prior_meta = get_packet_meta(packet_id, table_name=table_name, resource=resource)
    prev_score = None
    if prior_meta and "latestVerdictScore" in prior_meta:
        prev_score = prior_meta["latestVerdictScore"]

    # Update META with pointer, previousScore, and status
    now_iso = datetime.now(timezone.utc).isoformat()
    update_expr = "SET #st = :st, latestVerdictSk = :lsk, latestVerdictScore = :scr, updatedAt = :u"
    expr_names = {"#st": "status"}
    expr_values = {
        ":st": PacketStatus.CHECKED.value,
        ":lsk": verdict_sk,
        ":scr": verdict.score,
        ":u": now_iso,
    }
    if prev_score is not None:
        update_expr += ", previousScore = :ps"
        expr_values[":ps"] = prev_score

    table.update_item(
        Key={"pk": pk, "sk": "META"},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )


def update_packet_status(
    packet_id: str,
    status: PacketStatus,
    table_name: Optional[str] = None,
    resource: Optional[Any] = None,
) -> None:
    """Update packet status in META."""
    ddb = resource or get_dynamodb_resource()
    table = ddb.Table(table_name or DEFAULT_TABLE)

    pk = f"PACKET#{packet_id}"
    now_iso = datetime.now(timezone.utc).isoformat()
    status_val = status.value if hasattr(status, "value") else str(status)

    table.update_item(
        Key={"pk": pk, "sk": "META"},
        UpdateExpression="SET #st = :st, updatedAt = :u",
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={":st": status_val, ":u": now_iso},
    )
