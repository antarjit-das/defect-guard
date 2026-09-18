"""Application Snapshot builder for Defect Guard.

Aggregates extracted document fields across all uploaded documents into a single
cross-document comparison table (Snapshot), establishes canonical values based
on document hierarchy precedence, and identifies cross-document disagreements.
Zero external AWS/boto3 imports.
"""

from typing import List, Dict, Optional, Any

from backend.src.core.fields import (
    ROLE_PRECEDENCE,
    FIELD_LABELS,
    ALL_FIELD_KEYS,
    FIELD_STUDENT_NAME,
    FIELD_FATHER_NAME,
    FIELD_PARENT_NAME,
    FIELD_ACCOUNT_HOLDER_NAME,
    FIELD_DOB,
    FIELD_INCOME_CERT_DATE,
    FIELD_ANNUAL_INCOME,
)
from backend.src.core.models import (
    DocumentItem,
    DocumentStatus,
    Snapshot,
    SnapshotRow,
)
from backend.src.core.normalize import (
    normalize_name,
    normalize_date,
    normalize_money,
)


def _check_disagreement(field_key: str, values_by_role: Dict[str, str]) -> bool:
    """Determine whether the values from different documents disagree.

    Uses normalized values (lowercase, stripped honorifics, ISO dates, integer money)
    to avoid false positives on formatting differences.
    """
    if len(values_by_role) <= 1:
        return False

    normalized_set = set()

    for val in values_by_role.values():
        if val is None or not str(val).strip():
            continue

        str_val = str(val).strip()

        # Name fields: normalize using normalize_name
        if field_key in {
            FIELD_STUDENT_NAME,
            FIELD_FATHER_NAME,
            FIELD_PARENT_NAME,
            FIELD_ACCOUNT_HOLDER_NAME,
        }:
            norm_name, _ = normalize_name(str_val)
            normalized_set.add(norm_name)

        # Date fields: normalize using normalize_date
        elif field_key in {FIELD_DOB, FIELD_INCOME_CERT_DATE}:
            norm_date = normalize_date(str_val)
            normalized_set.add(norm_date or str_val.lower())

        # Money fields: normalize using normalize_money
        elif field_key == FIELD_ANNUAL_INCOME:
            norm_money = normalize_money(str_val)
            normalized_set.add(norm_money or str_val.lower())

        # General string/code fields
        else:
            normalized_set.add(str_val.lower())

    # If more than one distinct normalized value exists, there is a disagreement
    return len(normalized_set) > 1


def build_snapshot(documents: List[DocumentItem]) -> Snapshot:
    """Build a Snapshot from a list of DocumentItems.

    Rules:
    1. Only active documents are considered (ignores superseded documents and failed extractions).
    2. Collects values by role for each field.
    3. Canonical value and source are resolved using ROLE_PRECEDENCE:
       AADHAAR > MARKSHEET > INCOME_CERTIFICATE > BANK_PROOF.
    4. Evaluates disagreement across roles using normalized values.
    5. Excludes fields that have no values reported in any document.
    """
    # Filter active, successfully extracted documents
    active_docs: List[DocumentItem] = [
        doc for doc in documents
        if doc.supersededBy is None
        and doc.status == DocumentStatus.EXTRACTED
        and doc.extraction is not None
    ]

    # Map: field_key -> { role_str: raw_value_str }
    field_role_values: Dict[str, Dict[str, str]] = {}

    for doc in active_docs:
        role_str = str(doc.role.value if hasattr(doc.role, "value") else doc.role)
        for field in doc.extraction.fields:
            if field.rawValue is not None and str(field.rawValue).strip():
                if field.fieldKey not in field_role_values:
                    field_role_values[field.fieldKey] = {}
                field_role_values[field.fieldKey][role_str] = str(field.rawValue).strip()

    rows: List[SnapshotRow] = []

    # Preserve canonical field ordering from ALL_FIELD_KEYS
    ordered_keys = [k for k in ALL_FIELD_KEYS if k in field_role_values]
    # Include any custom/unregistered keys at the end
    extra_keys = [k for k in field_role_values if k not in ALL_FIELD_KEYS]
    all_keys = ordered_keys + extra_keys

    for field_key in all_keys:
        role_values = field_role_values[field_key]
        if not role_values:
            continue

        label = FIELD_LABELS.get(field_key, field_key.replace("_", " ").title())

        # Determine canonical value per ROLE_PRECEDENCE
        canonical_val: Optional[str] = None
        canonical_src: Optional[str] = None

        for preferred_role in ROLE_PRECEDENCE:
            if preferred_role in role_values:
                canonical_val = role_values[preferred_role]
                canonical_src = preferred_role
                break

        # Fallback if preferred role not found
        if canonical_val is None and role_values:
            first_role = next(iter(role_values))
            canonical_val = role_values[first_role]
            canonical_src = first_role

        # Check for cross-document disagreement
        has_disagreement = _check_disagreement(field_key, role_values)

        rows.append(
            SnapshotRow(
                fieldKey=field_key,
                label=label,
                valuesByRole=role_values,
                canonicalValue=canonical_val,
                canonicalSource=canonical_src,
                hasDisagreement=has_disagreement,
            )
        )

    return Snapshot(rows=rows)
