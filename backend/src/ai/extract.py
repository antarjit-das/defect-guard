"""Prompt assembly and payload formatting for Bedrock document extraction.

Prepares structured prompts combining Amazon Textract Query answers,
Form Key-Value pairs, and raw LINE text for typed extraction.
Zero external AWS/boto3 imports.
"""

from typing import Dict, List, Tuple, Optional
from backend.src.core.fields import ROLE_FIELDS, FIELD_LABELS


EXTRACTION_SYSTEM_PROMPT = (
    "You are a specialized document extraction engine for Indian government scholarship applications. "
    "You extract typed fields accurately from OCR text and form key-values. "
    "Rules:\n"
    "1. Only report what the extracted text explicitly supports.\n"
    "2. Never invent, extrapolate, or guess missing information.\n"
    "3. If a field is not present in the text, return rawValue as null.\n"
    "4. For each field, provide the exact verbatim evidence snippet from the document text.\n"
    "5. Confirm whether the document visually and textually matches its declared role.\n"
    "6. Assess document quality: POOR if heavily blurred, illegible, or cropped; otherwise GOOD."
)


def build_extraction_prompt(
    role: str,
    query_answers: Optional[Dict[str, str]] = None,
    form_kvs: Optional[Dict[str, str]] = None,
    raw_lines: Optional[List[str]] = None,
) -> Tuple[str, str]:
    """Assemble the system and user prompts for Bedrock document extraction.

    Returns:
        Tuple of (system_prompt: str, user_prompt: str).
    """
    expected_fields = ROLE_FIELDS.get(role, [])
    fields_description_lines = []
    for field_key in expected_fields:
        label = FIELD_LABELS.get(field_key, field_key.replace("_", " ").title())
        fields_description_lines.append(f"- '{field_key}': {label}")

    fields_desc = "\n".join(fields_description_lines)

    # Format Textract Query Results
    queries_section = "None"
    if query_answers:
        queries_section = "\n".join([f"- {k}: {v}" for k, v in query_answers.items()])

    # Format Key-Value Pairs
    kvs_section = "None"
    if form_kvs:
        kvs_section = "\n".join([f"- {k} => {v}" for k, v in form_kvs.items()][:25])

    # Format Raw OCR Lines (capped at 4,000 chars per §7)
    raw_text = "\n".join(raw_lines or [])
    if len(raw_text) > 4000:
        raw_text = raw_text[:4000] + "\n...[truncated]"

    user_prompt = f"""Document Role: {role}

Target Fields to Extract:
{fields_desc}

Textract Natural Language Query Answers:
{queries_section}

Detected Form Key-Value Pairs:
{kvs_section}

Raw Document OCR Text Lines:
{raw_text}

Instructions:
Extract each of the target fields listed above based strictly on the OCR text, queries, and key-values.
Confirm role match and assess document quality.
"""

    return EXTRACTION_SYSTEM_PROMPT, user_prompt.strip()
