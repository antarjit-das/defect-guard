"""Deterministic scheme rule engine for Defect Guard.

Evaluates Application Snapshot and document metadata against NIJUT_BABU_2026.yaml.
Emits typed Finding objects with stable IDs and tags candidates for AI adjudication.
Zero external AWS/boto3 imports.
"""

'''i need to understand the code here better bruh, the caveat is just that im too shit in Python OOPS so far'''

from pathlib import Path
from typing import List, Optional, Dict, Any
import yaml

from backend.src.core.models import (
    Snapshot,
    DocumentItem,
    Finding,
    Severity,
    FindingCategory,
    DocumentReference,
    DocumentRole,
    DocumentStatus,
    DocumentQuality,
)
from backend.src.core.normalize import (
    normalize_name,
    normalize_money,
)
from backend.src.core.fields import (
    FIELD_STUDENT_NAME,
    FIELD_FATHER_NAME,
    FIELD_PARENT_NAME,
    FIELD_ACCOUNT_HOLDER_NAME,
    FIELD_INSTITUTION_NAME,
    FIELD_GENDER,
    FIELD_ANNUAL_INCOME,
    FIELD_INCOME_CERT_AUTHORITY,
    ROLE_AADHAAR,
    ROLE_INCOME_CERTIFICATE,
    ROLE_MARKSHEET,
    ROLE_BANK_PROOF,
)

DEFAULT_RULESET_PATH = Path(__file__).resolve().parent / "NIJUT_BABU_2026.yaml"


class RuleEngine:
    """Evaluates scholarship packets against YAML-defined scheme rules."""

    def __init__(self, ruleset_path: Optional[Path] = None):
        self.ruleset_path = ruleset_path or DEFAULT_RULESET_PATH   # ruleset_path has been added as extra var, cuz in future we may do tests on how this engine would behave with another ruleset or with a corrupt yaml. so we dont need to continuously overwrite the default_ruleset_path everytime
        with open(self.ruleset_path, "r", encoding="utf-8") as f:
            self.ruleset = yaml.safe_load(f)

        self.scheme_meta: Dict[str, Any] = self.ruleset.get("scheme", {})
        self.rules_by_id: Dict[str, Dict[str, Any]] = {
            r["id"]: r for r in self.ruleset.get("rules", [])
        }

    def evaluate(
        self,
        snapshot: Snapshot,
        documents: List[DocumentItem],
    ) -> List[Finding]:
        """Run all deterministic rules over the snapshot and document collection.

        Returns:
            List of Finding objects sorted by findingId.
        """
        findings: List[Finding] = []
        counter = 1

        # Map snapshot rows by field key for fast lookup
        rows_by_field = {row.fieldKey: row for row in snapshot.rows}

        # Filter active extracted documents
        active_docs = [
            doc for doc in documents
            if doc.supersededBy is None and doc.status == DocumentStatus.EXTRACTED
        ]

        # Helper to create finding from YAML rule definition
        def add_finding(
            rule_id: str,
            doc_refs: List[DocumentReference],
            custom_reason: Optional[str] = None,
            custom_fix: Optional[str] = None,
            confidence: float = 0.95,
        ):
            nonlocal counter
            rule = self.rules_by_id[rule_id]
            severity = Severity(rule["severity"])
            category = FindingCategory(rule["category"])

            findings.append(
                Finding(
                    findingId=f"f{counter}",
                    ruleId=rule_id,
                    title=rule["title"],
                    severity=severity,
                    category=category,
                    documents=doc_refs,
                    reason=custom_reason or rule["defaultReason"],
                    fixInstruction=custom_fix or rule["defaultFix"],
                    confidence=confidence,
                    source=rule["source"],
                    needsAdjudication=rule.get("needsAdjudication", False),
                )
            )
            counter += 1

        # --- Rule R-05: Missing mandatory supporting document (RED) ---
        mandatory_roles = self.scheme_meta.get(
            "mandatoryRoles",
            [ROLE_AADHAAR, ROLE_INCOME_CERTIFICATE, ROLE_MARKSHEET, ROLE_BANK_PROOF],
        )
        # Collect all document types that the student actually uploaded
        uploaded_roles = set()
        for doc in active_docs:
            role_name = doc.role.value if hasattr(doc.role, "value") else str(doc.role)
            uploaded_roles.add(role_name)

        # Check which mandatory documents are missing
        missing_roles = []
        for role in mandatory_roles:
            if role not in uploaded_roles:
                missing_roles.append(role)

        if len(missing_roles) > 0:
            add_finding(
                "R-05",
                [],
                custom_reason=f"Missing mandatory document(s): {', '.join(missing_roles)}.",
                confidence=1.0,
            )

        # --- Rule R-01: Student name mismatch across documents (RED) ---
        if FIELD_STUDENT_NAME in rows_by_field:
            row = rows_by_field[FIELD_STUDENT_NAME]
            if row.hasDisagreement:
                doc_refs = [
                    DocumentReference(role=DocumentRole(role_str), value=val)
                    for role_str, val in row.valuesByRole.items()
                ]
                add_finding("R-01", doc_refs, confidence=0.96)

        # --- Rule R-02: Father's or guardian's name mismatch (RED) ---
        father_row = rows_by_field.get(FIELD_FATHER_NAME)
        parent_row = rows_by_field.get(FIELD_PARENT_NAME)

        father_mismatch = False
        doc_refs_r02: List[DocumentReference] = []

        if father_row and father_row.hasDisagreement:
            father_mismatch = True
            doc_refs_r02.extend(
                [DocumentReference(role=DocumentRole(r), value=v) for r, v in father_row.valuesByRole.items()]
            )
        elif father_row and parent_row and father_row.canonicalValue and parent_row.canonicalValue:
            norm_father, _ = normalize_name(father_row.canonicalValue)
            norm_parent, _ = normalize_name(parent_row.canonicalValue)
            if norm_father != norm_parent:
                father_mismatch = True
                doc_refs_r02 = [
                    DocumentReference(role=DocumentRole(father_row.canonicalSource or ROLE_MARKSHEET), value=father_row.canonicalValue),
                    DocumentReference(role=DocumentRole(parent_row.canonicalSource or ROLE_INCOME_CERTIFICATE), value=parent_row.canonicalValue),
                ]

        if father_mismatch:
            add_finding("R-02", doc_refs_r02, confidence=0.94)

        # --- Rule R-03: Bank account holder name mismatch (RED) ---
        acct_row = rows_by_field.get(FIELD_ACCOUNT_HOLDER_NAME)
        student_row = rows_by_field.get(FIELD_STUDENT_NAME)
        if acct_row and student_row and acct_row.canonicalValue and student_row.canonicalValue:
            norm_acct, _ = normalize_name(acct_row.canonicalValue)
            norm_student, _ = normalize_name(student_row.canonicalValue)
            if norm_acct != norm_student:
                doc_refs_r03 = [
                    DocumentReference(role=DocumentRole.BANK_PROOF, value=acct_row.canonicalValue),
                    DocumentReference(role=DocumentRole(student_row.canonicalSource or ROLE_AADHAAR), value=student_row.canonicalValue),
                ]
                add_finding("R-03", doc_refs_r03, confidence=0.95)

        # --- Rule R-06: Gender is not Male (RED) ---
        gender_row = rows_by_field.get(FIELD_GENDER)
        if gender_row and gender_row.canonicalValue:
            val = gender_row.canonicalValue.strip().lower()
            if val not in {"male", "m"}:
                add_finding(
                    "R-06",
                    [DocumentReference(role=DocumentRole.AADHAAR, value=gender_row.canonicalValue)],
                    confidence=0.99,
                )

        # --- Rule R-07: Declared annual income exceeds ceiling (RED) ---
        income_row = rows_by_field.get(FIELD_ANNUAL_INCOME)
        income_ceiling = self.scheme_meta.get("incomeCeiling", 400_000)
        if income_row and income_row.canonicalValue:
            income_num = normalize_money(income_row.canonicalValue)
            if income_num is not None and income_num > income_ceiling:
                add_finding(
                    "R-07",
                    [DocumentReference(role=DocumentRole.INCOME_CERTIFICATE, value=income_row.canonicalValue)],
                    custom_reason=(
                        f"The income certificate declares an annual family income of ₹{income_num:,}, "
                        f"which exceeds the mandatory scheme ceiling of ₹{income_ceiling:,}."
                    ),
                    confidence=0.99,
                )

        # --- Rule R-04: Institution enrollment requires verification (AMBER) ---
        inst_row = rows_by_field.get(FIELD_INSTITUTION_NAME)
        if inst_row and inst_row.canonicalValue:
            add_finding(
                "R-04",
                [DocumentReference(role=DocumentRole(inst_row.canonicalSource or ROLE_MARKSHEET), value=inst_row.canonicalValue)],
                confidence=0.85,
            )

        # --- Rule R-08: Income certificate issuing authority requires verification (AMBER) ---
        auth_row = rows_by_field.get(FIELD_INCOME_CERT_AUTHORITY)
        if auth_row and auth_row.canonicalValue:
            auth_val = auth_row.canonicalValue.lower()
            # If authority does not clearly indicate Revenue Circle Officer
            if "circle officer" not in auth_val and "revenue" not in auth_val:
                add_finding(
                    "R-08",
                    [DocumentReference(role=DocumentRole.INCOME_CERTIFICATE, value=auth_row.canonicalValue)],
                    confidence=0.80,
                )

        # --- Document Quality & Technical Upload Rules (R-09, R-10, R-11) ---
        for doc in active_docs:
            role_enum = doc.role if isinstance(doc.role, DocumentRole) else DocumentRole(doc.role)

            # R-09: Unreadable / Poor Quality Scan (AMBER)
            if doc.extraction and doc.extraction.documentQuality == DocumentQuality.POOR:
                add_finding(
                    "R-09",
                    [DocumentReference(role=role_enum, value=doc.fileName)],
                    custom_reason=f"The uploaded file for {role_enum.value} ({doc.fileName}) is of poor visual quality or low scan resolution.",
                    confidence=0.90,
                )

            # R-10: Slot Mismatch (AMBER)
            if doc.extraction and doc.extraction.roleConfirmed is False:
                add_finding(
                    "R-10",
                    [DocumentReference(role=role_enum, value=doc.fileName)],
                    custom_reason=f"The uploaded file in {role_enum.value} does not appear to match that document type.",
                    confidence=0.88,
                )

            # R-11: File Size Exceeds Soft Cap (AMBER)
            if doc.sizeBytes > 200 * 1024:  # > 200 KB soft warning
                size_kb = doc.sizeBytes // 1024
                add_finding(
                    "R-11",
                    [DocumentReference(role=role_enum, value=f"{size_kb} KB")],
                    custom_reason=f"Document {doc.fileName} is {size_kb} KB, which exceeds the scholarship portal recommendation (200 KB).",
                    custom_fix="Consider compressing the scan under 200 KB to prevent rejection at final portal submission.",
                    confidence=0.85,
                )

        return findings
