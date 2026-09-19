"""Asynchronous worker Lambda: fn_extract_document.

Triggered asynchronously after document upload.
Workflow:
1. Calls S3 head_object to fetch authoritative ContentLength and ContentType.
2. Calls Textract analyze_document (QUERIES + FORMS) synchronously.
3. Builds Bedrock extraction prompt with Textract results, form key-values, and raw OCR lines.
4. Invokes Bedrock with DocumentExtraction JSON Schema.
5. If Bedrock succeeds: parses typed fields.
   If Bedrock unavailable / throttled: falls back to deterministic Textract query answers.
6. Runs pure-Python normalizers:
   - Names: normalize_name
   - Dates: normalize_date
   - Money: normalize_money
   - IFSC: normalize_ifsc
   - Account: normalize_account_number + mask_account_number
   - Aadhaar: normalize_aadhaar + mask_aadhaar + Verhoeff validation
7. Updates DynamoDB DOC# item setting extraction payload and status = EXTRACTED (or EXTRACTION_FAILED).
8. Checks if all active documents in packet are now EXTRACTED. If so, transitions packet status to READY_TO_CHECK.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple

from ..core.models import (
    DocumentStatus,
    PacketStatus,
    DocumentQuality,
    DocumentExtraction,
    ExtractedField,
    is_usable_extraction,
    is_usable_field,
)
from ..core.fields import (
    ROLE_FIELDS,
    FIELD_STUDENT_NAME,
    FIELD_FATHER_NAME,
    FIELD_PARENT_NAME,
    FIELD_ACCOUNT_HOLDER_NAME,
    FIELD_DOB,
    FIELD_INCOME_CERT_DATE,
    FIELD_ANNUAL_INCOME,
    FIELD_IFSC,
    FIELD_BANK_ACCOUNT_NUMBER,
    FIELD_AADHAAR_LAST4,
    TEXTRACT_QUERIES,
)
from ..core.normalize import (
    normalize_name,
    normalize_date,
    normalize_money,
    normalize_ifsc,
    normalize_account_number,
    normalize_aadhaar,
)
from ..core.masking import mask_aadhaar, mask_account_number
from ..core.validators import validate_verhoeff
from ..aws.s3_client import get_authoritative_metadata, DEFAULT_BUCKET
from ..aws.textract_client import extract_document_sync
from ..aws.bedrock_client import invoke_bedrock_structured
from ..aws.ddb import (
    get_full_packet,
    update_document_extraction,
    update_packet_status,
)
from ..ai.schemas import get_extraction_output_config
from ..ai.extract import build_extraction_prompt

logger = logging.getLogger(__name__)


def _safe_error_message(service: str, exc: Exception) -> str:
    """Generate a concise, safe error string without secrets, credentials, or payloads."""
    exc_type = type(exc).__name__
    if hasattr(exc, "response") and isinstance(getattr(exc, "response", None), dict):
        err_info = exc.response.get("Error", {})
        code = err_info.get("Code", exc_type)
        msg = err_info.get("Message", str(exc))
        clean_msg = str(msg).strip().replace("\n", " ")[:120]
        return f"{service} {code}: {clean_msg}"
    clean_msg = str(exc).strip().replace("\n", " ")[:120]
    return f"{service} {exc_type}: {clean_msg}"


def normalize_extracted_value(field_key: str, raw_val: Optional[str]) -> Tuple[Optional[str], Optional[Any], bool]:
    """Apply domain normalization and PII masking to an extracted field.

    Returns:
        Tuple of (stored_raw_value, normalized_value, needs_confirmation).
    """
    if not raw_val or not str(raw_val).strip():
        return None, None, False

    clean_raw = str(raw_val).strip()
    needs_conf = False

    # 1. Name fields
    if field_key in {FIELD_STUDENT_NAME, FIELD_FATHER_NAME, FIELD_PARENT_NAME, FIELD_ACCOUNT_HOLDER_NAME}:
        norm, _ = normalize_name(clean_raw)
        return clean_raw, norm, False

    # 2. Date fields
    if field_key in {FIELD_DOB, FIELD_INCOME_CERT_DATE}:
        norm = normalize_date(clean_raw)
        return clean_raw, norm, (norm is None)

    # 3. Money / Annual Income
    if field_key == FIELD_ANNUAL_INCOME:
        norm = normalize_money(clean_raw)
        return clean_raw, norm, (norm is None)

    # 4. IFSC code
    if field_key == FIELD_IFSC:
        norm = normalize_ifsc(clean_raw)
        return clean_raw, norm, False

    # 5. Bank Account Number (mask PII!)
    if field_key == FIELD_BANK_ACCOUNT_NUMBER:
        masked, last4 = mask_account_number(clean_raw)
        norm = normalize_account_number(clean_raw)
        # We store masked version to comply with privacy rules
        return masked or clean_raw, last4, False

    # 6. Aadhaar Number (mask PII + Verhoeff validation)
    if field_key in {FIELD_AADHAAR_LAST4, "aadhaar_number"}:
        masked, last4 = mask_aadhaar(clean_raw)
        norm_digits = normalize_aadhaar(clean_raw)
        is_verhoeff_valid = validate_verhoeff(norm_digits) if norm_digits and len(norm_digits) == 12 else True
        return masked or clean_raw, last4, (not is_verhoeff_valid)

    # Default: string cleanup
    return clean_raw, clean_raw.lower(), False


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Handle async document extraction."""
    packet_id = event.get("packetId")
    document_id = event.get("documentId")
    role = event.get("role")
    object_key = event.get("objectKey")

    if not packet_id or not document_id or not role:
        logger.error("Missing required extraction payload: %s", event)
        return {"status": "FAILED", "error": "Missing packetId, documentId, or role"}

    try:
        logger.info("Starting extraction for packet=%s, doc=%s, role=%s", packet_id, document_id, role)

        # 1. Fetch authoritative S3 metadata (never trust client)
        bucket = event.get("bucketName", DEFAULT_BUCKET)
        content_length: Optional[int] = None
        try:
            auth_meta = get_authoritative_metadata(object_key, bucket_name=bucket)
            content_length = auth_meta.get("contentLength")
            logger.info("Authoritative S3 metadata: %s bytes, type=%s", content_length, auth_meta.get("contentType"))
        except Exception as s3_err:
            logger.warning("Could not read S3 head_object: %s. Continuing with registered storage metadata.", str(s3_err))

        # 2. Textract extraction
        textract_res = None
        textract_error: Optional[str] = None
        try:
            textract_res = extract_document_sync(
                bucket_name=bucket,
                object_key=object_key,
                role=role,
            )
        except Exception as tex_err:
            textract_error = _safe_error_message("Textract", tex_err)
            logger.error("Textract service invocation failed for packet=%s, doc=%s, role=%s: %s", packet_id, document_id, role, textract_error)

        # Distinguish:
        # Case A: Textract service failure (e.g. SubscriptionRequiredException, AccessDeniedException)
        if textract_error:
            error_msg = f"Textract service failure: {textract_error}"
            logger.warning("Document %s (packet %s) failed due to Textract service error: %s", document_id, packet_id, error_msg)
            update_document_extraction(
                packet_id=packet_id,
                document_id=document_id,
                extraction_dict=None,
                status=DocumentStatus.EXTRACTION_FAILED,
                error=error_msg,
                size_bytes=content_length,
            )
            return {"status": "FAILED", "documentId": document_id, "error": error_msg}

        query_answers = textract_res.get("query_answers", {}) if textract_res else {}
        form_kvs = textract_res.get("form_kvs", {}) if textract_res else {}
        raw_lines = textract_res.get("raw_lines", []) if textract_res else []
        mean_conf = textract_res.get("mean_confidence", 0.0) if textract_res else 0.0

        # Case B: Textract succeeds but detects no text, queries, or form fields
        if not (query_answers or form_kvs or raw_lines):
            error_msg = "Textract completed but detected no readable text or form fields"
            logger.warning("Document %s (packet %s) produced empty Textract OCR: %s", document_id, packet_id, error_msg)
            update_document_extraction(
                packet_id=packet_id,
                document_id=document_id,
                extraction_dict=None,
                status=DocumentStatus.EXTRACTION_FAILED,
                error=error_msg,
                size_bytes=content_length,
            )
            return {"status": "FAILED", "documentId": document_id, "error": error_msg}

        # 3. Bedrock extraction invocation
        extracted_fields_list: List[ExtractedField] = []
        role_confirmed = False
        doc_quality = DocumentQuality.GOOD if mean_conf >= 0.70 else DocumentQuality.POOR
        notes = None
        bedrock_error: Optional[str] = None

        ai_response_text = None
        try:
            sys_prompt, user_prompt = build_extraction_prompt(
                role=role,
                query_answers=query_answers,
                form_kvs=form_kvs,
                raw_lines=raw_lines,
            )
            out_config = get_extraction_output_config()
            ai_response_text = invoke_bedrock_structured(
                system_prompt=sys_prompt,
                user_prompt=user_prompt,
                output_config=out_config,
                max_tokens=2000,
            )
        except Exception as bed_err:
            bedrock_error = _safe_error_message("Bedrock", bed_err)
            logger.warning("Bedrock invocation failed: %s. Engaging deterministic Textract fallback.", bedrock_error)

        # 4. Parse Bedrock response OR use Textract Query Fallback
        if ai_response_text:
            try:
                parsed_ai = json.loads(ai_response_text)
                ai_fields = parsed_ai.get("fields", [])
                for f in ai_fields:
                    f_key = f.get("fieldKey", "")
                    raw_val = f.get("rawValue")
                    conf = float(f.get("confidence", 1.0))
                    ev = f.get("evidence")

                    stored_raw, norm_val, needs_conf = normalize_extracted_value(f_key, raw_val)
                    extracted_fields_list.append(
                        ExtractedField(
                            fieldKey=f_key,
                            rawValue=stored_raw,
                            normalizedValue=norm_val,
                            confidence=conf,
                            evidence=ev,
                            source="BEDROCK_CLAUDE_SONNET",
                            needsConfirmation=needs_conf,
                        )
                    )
                role_confirmed = bool(parsed_ai.get("roleConfirmed", False))
                doc_quality_val = parsed_ai.get("documentQuality", "GOOD")
                doc_quality = DocumentQuality(doc_quality_val)
                notes = parsed_ai.get("notes")
            except Exception as parse_err:
                bedrock_error = f"Bedrock JSON parse error: {type(parse_err).__name__}"
                logger.warning("Failed parsing Bedrock extraction JSON: %s. Using Textract query fallback.", str(parse_err))
                ai_response_text = None

        # Fallback: if AI response was None or failed or produced zero usable fields,
        # populate from Textract query answers
        if not any(is_usable_field(f) for f in extracted_fields_list):
            logger.info("Populating extraction fields from deterministic Textract queries.")
            fallback_fields: List[ExtractedField] = []
            role_queries = TEXTRACT_QUERIES.get(role, [])
            for q in role_queries:
                q_text = q["Text"]
                f_key = q.get("Alias", "")
                raw_val = query_answers.get(q_text)

                if f_key and raw_val:
                    stored_raw, norm_val, needs_conf = normalize_extracted_value(f_key, raw_val)
                    fallback_fields.append(
                        ExtractedField(
                            fieldKey=f_key,
                            rawValue=stored_raw,
                            normalizedValue=norm_val,
                            confidence=mean_conf,
                            evidence=f"Textract Query: '{q_text}'",
                            source="TEXTRACT_QUERY",
                            needsConfirmation=needs_conf,
                        )
                    )
            if any(is_usable_field(f) for f in fallback_fields):
                extracted_fields_list = fallback_fields
                role_confirmed = True
                doc_quality = DocumentQuality.GOOD if mean_conf >= 0.70 else DocumentQuality.POOR
            else:
                extracted_fields_list = []

        # 5. Build DocumentExtraction payload
        extraction = DocumentExtraction(
            roleConfirmed=role_confirmed,
            documentQuality=doc_quality,
            fields=extracted_fields_list,
            notes=notes,
        )

        # 6. Validate extraction usability
        if not is_usable_extraction(extraction):
            if textract_error:
                error_msg = f"No usable fields could be extracted from document ({textract_error})"
            elif bedrock_error:
                error_msg = f"No usable fields could be extracted from document ({bedrock_error})"
            else:
                error_msg = "No usable fields could be extracted from document"

            logger.warning(
                "Document %s (packet %s) extraction failed: %s",
                document_id, packet_id, error_msg
            )
            update_document_extraction(
                packet_id=packet_id,
                document_id=document_id,
                extraction_dict=None,
                status=DocumentStatus.EXTRACTION_FAILED,
                error=error_msg,
                size_bytes=content_length,
            )
            return {"status": "FAILED", "documentId": document_id, "error": error_msg}

        # 7. Update DynamoDB DOC# item (AP4) with valid extraction
        update_document_extraction(
            packet_id=packet_id,
            document_id=document_id,
            extraction_dict=extraction.model_dump(),
            status=DocumentStatus.EXTRACTED,
            size_bytes=content_length,
        )

        # 8. Check if packet is now ready to check
        packet = get_full_packet(packet_id)
        if packet:
            active_extracted_count = 0
            for doc in packet.documents:
                if doc.supersededBy is None and doc.status == DocumentStatus.EXTRACTED:
                    active_extracted_count += 1

            # If >= 3 documents are extracted and packet is in EXTRACTING status, update to READY_TO_CHECK
            if active_extracted_count >= 3 and packet.status in (PacketStatus.EXTRACTING, PacketStatus.DRAFT):
                update_packet_status(packet_id, PacketStatus.READY_TO_CHECK)
                logger.info("Packet %s has %d active extracted docs. Status -> READY_TO_CHECK.", packet_id, active_extracted_count)

        return {"status": "SUCCESS", "documentId": document_id}

    except Exception as e:
        logger.exception("Fatal error in extraction worker: %s", str(e))
        safe_fatal_msg = _safe_error_message("Worker", e)
        update_document_extraction(
            packet_id=packet_id,
            document_id=document_id,
            extraction_dict=None,
            status=DocumentStatus.EXTRACTION_FAILED,
            error=safe_fatal_msg,
        )
        return {"status": "FAILED", "documentId": document_id, "error": safe_fatal_msg}
