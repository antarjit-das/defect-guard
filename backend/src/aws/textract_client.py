"""Amazon Textract thin client for Defect Guard.

Calls analyze_document with role-specific natural language queries and form features.
Parses query answers, form key-value pairs, and raw text lines with confidences.
"""

import os
from typing import Dict, List, Any, Optional
import boto3
from botocore.config import Config

from ..core.fields import TEXTRACT_QUERIES

DEFAULT_REGION = os.environ.get("AWS_REGION", "ap-south-1")
DEFAULT_BUCKET = os.environ.get("UPLOADS_BUCKET", "defect-guard-uploads")


def get_textract_client(region_name: str = DEFAULT_REGION):
    """Factory to get Textract client with retry config."""
    return boto3.client(
        "textract",
        region_name=region_name,
        config=Config(retries={"max_attempts": 3, "mode": "standard"}),
    )


def extract_document_sync(
    bucket_name: str,
    object_key: str,
    role: str,
    client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Execute Textract analyze_document synchronously using QUERIES + FORMS.

    Args:
        bucket_name: S3 bucket containing document.
        object_key: S3 object key.
        role: Document role (AADHAAR, MARKSHEET, INCOME_CERTIFICATE, BANK_PROOF).
        client: Optional boto3 client override.

    Returns:
        Dict containing:
            - 'query_answers': Dict[query_text, answer_text]
            - 'form_kvs': Dict[key_text, value_text]
            - 'raw_lines': List[str]
            - 'mean_confidence': float
            - 'page_count': int
    """
    textract = client or get_textract_client()

    # Get queries defined for this role
    queries = TEXTRACT_QUERIES.get(role, [])
    queries_payload = []
    for q in queries:
        queries_payload.append({"Text": q["Text"], "Alias": q.get("Alias", "")})

    # Prepare analyze_document params
    params = {
        "Document": {
            "S3Object": {
                "Bucket": bucket_name,
                "Name": object_key,
            }
        },
        "FeatureTypes": ["QUERIES", "FORMS"],
    }
    if len(queries_payload) > 0:
        params["QueriesConfig"] = {"Queries": queries_payload}

    response = textract.analyze_document(**params)
    return parse_textract_blocks(response)


def parse_textract_blocks(response: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Textract response blocks into queries, key-values, and lines."""
    blocks = response.get("Blocks", [])
    blocks_by_id = {}
    for b in blocks:
        blocks_by_id[b["Id"]] = b

    query_answers: Dict[str, str] = {}
    query_result_ids = {}

    # 1. Map QUERY blocks to their QUERY_RESULT
    for b in blocks:
        if b.get("BlockType") == "QUERY":
            query_text = b.get("Query", {}).get("Text", "")
            relationships = b.get("Relationships", [])
            for rel in relationships:
                if rel.get("Type") == "ANSWER":
                    for ans_id in rel.get("Ids", []):
                        query_result_ids[ans_id] = query_text

    # 2. Extract QUERY_RESULT text
    for b in blocks:
        if b.get("BlockType") == "QUERY_RESULT":
            ans_id = b.get("Id")
            if ans_id in query_result_ids:
                q_text = query_result_ids[ans_id]
                query_answers[q_text] = b.get("Text", "")

    # 3. Extract Form Key-Value pairs
    key_map = {}
    value_map = {}
    for b in blocks:
        if b.get("BlockType") == "KEY_VALUE_SET":
            entity_types = b.get("EntityTypes", [])
            if "KEY" in entity_types:
                key_map[b["Id"]] = b
            elif "VALUE" in entity_types:
                value_map[b["Id"]] = b

    def get_child_text(block: Dict[str, Any]) -> str:
        text_parts = []
        for rel in block.get("Relationships", []):
            if rel.get("Type") == "CHILD":
                for child_id in rel.get("Ids", []):
                    child = blocks_by_id.get(child_id)
                    if child and child.get("BlockType") == "WORD":
                        text_parts.append(child.get("Text", ""))
        return " ".join(text_parts).strip()

    form_kvs: Dict[str, str] = {}
    for key_id, key_block in key_map.items():
        k_text = get_child_text(key_block)
        v_text = ""
        for rel in key_block.get("Relationships", []):
            if rel.get("Type") == "VALUE":
                for val_id in rel.get("Ids", []):
                    val_block = value_map.get(val_id)
                    if val_block:
                        v_text = get_child_text(val_block)
        if k_text:
            form_kvs[k_text] = v_text

    # 4. Extract Lines & Confidence
    raw_lines: List[str] = []
    line_confidences: List[float] = []
    page_count = 1

    for b in blocks:
        if b.get("BlockType") == "PAGE":
            page_count = max(page_count, b.get("Page", 1))
        elif b.get("BlockType") == "LINE":
            text = b.get("Text", "").strip()
            if text:
                raw_lines.append(text)
            if "Confidence" in b:
                line_confidences.append(float(b["Confidence"]))

    mean_conf = 1.0
    if len(line_confidences) > 0:
        total_conf = 0.0
        for c in line_confidences:
            total_conf += c
        mean_conf = total_conf / len(line_confidences) / 100.0  # normalize to 0..1

    return {
        "query_answers": query_answers,
        "form_kvs": form_kvs,
        "raw_lines": raw_lines,
        "mean_confidence": mean_conf,
        "page_count": page_count,
    }
