"""Unit tests for the deterministic scheme rule engine.

Tests evaluation against NIJUT_BABU_2026.yaml including planted demo defects,
document replacement clearing defects, and specific MMNBA scheme rules.
"""

from backend.src.core.models import (
    DocumentItem,
    DocumentRole,
    DocumentStatus,
    DocumentExtraction,
    ExtractedField,
    Severity,
)
from backend.src.core.snapshot import build_snapshot
from backend.src.core.rules.engine import RuleEngine


def _create_demo_documents():
    """Build the 4 standard synthetic demo documents with the 3 planted defects."""
    doc_aadhaar = DocumentItem(
        documentId="doc-aadhaar-1",
        role=DocumentRole.AADHAAR,
        fileName="aadhaar.jpg",
        contentType="image/jpeg",
        sizeBytes=150_000,
        status=DocumentStatus.EXTRACTED,
        extraction=DocumentExtraction(
            fields=[
                ExtractedField(fieldKey="student_name", rawValue="ANTARJIT DAS"),
                ExtractedField(fieldKey="dob", rawValue="2004-03-12"),
                ExtractedField(fieldKey="gender", rawValue="Male"),
                ExtractedField(fieldKey="aadhaar_last4", rawValue="4821"),
            ]
        ),
    )

    doc_income = DocumentItem(
        documentId="doc-income-1",
        role=DocumentRole.INCOME_CERTIFICATE,
        fileName="income.pdf",
        contentType="application/pdf",
        sizeBytes=180_000,
        status=DocumentStatus.EXTRACTED,
        extraction=DocumentExtraction(
            fields=[
                ExtractedField(fieldKey="parent_name", rawValue="PRODIP DAS"),
                # Planted Defect: ₹4,50,000 exceeds ₹4,00,000 ceiling
                ExtractedField(fieldKey="annual_income", rawValue="₹4,50,000/-"),
                ExtractedField(fieldKey="income_cert_authority", rawValue="Circle Officer, Dispur"),
            ]
        ),
    )

    doc_marksheet = DocumentItem(
        documentId="doc-marksheet-1",
        role=DocumentRole.MARKSHEET,
        fileName="marksheet.pdf",
        contentType="application/pdf",
        sizeBytes=190_000,
        status=DocumentStatus.EXTRACTED,
        extraction=DocumentExtraction(
            fields=[
                # Planted Defect: Spelling differs from Aadhaar
                ExtractedField(fieldKey="student_name", rawValue="ANTARJEET DASS"),
                ExtractedField(fieldKey="father_name", rawValue="PRODIP DAS"),
                ExtractedField(fieldKey="institution_name", rawValue="Cotton University"),
            ]
        ),
    )

    doc_bank = DocumentItem(
        documentId="doc-bank-1",
        role=DocumentRole.BANK_PROOF,
        fileName="passbook.jpg",
        contentType="image/jpeg",
        sizeBytes=160_000,
        status=DocumentStatus.EXTRACTED,
        extraction=DocumentExtraction(
            fields=[
                ExtractedField(fieldKey="account_holder_name", rawValue="ANTARJIT DAS"),
                ExtractedField(fieldKey="bank_account_number", rawValue="9821"),
                ExtractedField(fieldKey="ifsc", rawValue="SBIN0001234"),
            ]
        ),
    )

    return [doc_aadhaar, doc_income, doc_marksheet, doc_bank]


def test_demo_packet_rule_evaluation():
    """Verify that the 3 planted defects fire on the demo documents."""
    docs = _create_demo_documents()
    snapshot = build_snapshot(docs)

    engine = RuleEngine()
    findings = engine.evaluate(snapshot, docs)

    rule_ids = [f.ruleId for f in findings]

    # Must contain R-01 (Name mismatch), R-07 (Income ceiling), R-04 (Institution verification)
    assert "R-01" in rule_ids
    assert "R-07" in rule_ids
    assert "R-04" in rule_ids

    # R-01 check
    r01 = next(f for f in findings if f.ruleId == "R-01")
    assert r01.severity == Severity.RED
    assert r01.needsAdjudication is True
    assert len(r01.documents) == 2

    # R-07 check
    r07 = next(f for f in findings if f.ruleId == "R-07")
    assert r07.severity == Severity.RED
    assert "450,000" in r07.reason
    assert "400,000" in r07.reason

    # R-04 check
    r04 = next(f for f in findings if f.ruleId == "R-04")
    assert r04.severity == Severity.RED
    assert "250,000" in r04.reason


def test_document_replacement_clears_defect():
    """Verify that replacing the income certificate with compliant income clears R-04 and R-07."""
    docs = _create_demo_documents()

    # Supersede doc-income-1 with a compliant income certificate
    docs[1].supersededBy = "doc-income-new"

    doc_income_compliant = DocumentItem(
        documentId="doc-income-new",
        role=DocumentRole.INCOME_CERTIFICATE,
        fileName="income_compliant.pdf",
        contentType="application/pdf",
        sizeBytes=170_000,
        status=DocumentStatus.EXTRACTED,
        extraction=DocumentExtraction(
            fields=[
                ExtractedField(fieldKey="parent_name", rawValue="PRODIP DAS"),
                # Compliant income under ₹2.50 Lakh and ₹4.00 Lakh
                ExtractedField(fieldKey="annual_income", rawValue="₹2,40,000/-"),
                ExtractedField(fieldKey="income_cert_authority", rawValue="Circle Officer, Dispur"),
            ]
        ),
    )
    docs.append(doc_income_compliant)

    snapshot = build_snapshot(docs)
    engine = RuleEngine()
    findings = engine.evaluate(snapshot, docs)

    rule_ids = [f.ruleId for f in findings]
    # R-07 and R-04 are cleared!
    assert "R-07" not in rule_ids
    assert "R-04" not in rule_ids
    # R-01 (name mismatch) still remains
    assert "R-01" in rule_ids


def test_r04_income_ceiling_boundaries():
    """Verify deterministic R-04 behavior across boundary values and formats:
    - exactly ₹250,000 (no trigger)
    - below ₹250,000 (no trigger)
    - above ₹250,000 (trigger RED)
    - formatted currency strings
    - missing annual income (no trigger)
    """
    engine = RuleEngine()

    def evaluate_income(val):
        doc = DocumentItem(
            documentId="doc-inc",
            role=DocumentRole.INCOME_CERTIFICATE,
            fileName="inc.pdf",
            contentType="application/pdf",
            sizeBytes=100000,
            status=DocumentStatus.EXTRACTED,
            extraction=DocumentExtraction(
                fields=[ExtractedField(fieldKey="annual_income", rawValue=val)] if val is not None else []
            ),
        )
        snap = build_snapshot([doc])
        res = engine.evaluate(snap, [doc])
        return [f for f in res if f.ruleId == "R-04"]

    # 1. Exactly 250,000 -> must NOT trigger
    assert len(evaluate_income("250000")) == 0
    assert len(evaluate_income("₹250,000")) == 0
    assert len(evaluate_income("250,000")) == 0
    assert len(evaluate_income("₹ 250000")) == 0
    assert len(evaluate_income("2.5 Lakh")) == 0

    # 2. Below 250,000 -> must NOT trigger
    assert len(evaluate_income("249999")) == 0
    assert len(evaluate_income("₹2,40,000/-")) == 0
    assert len(evaluate_income("150000")) == 0

    # 3. Above 250,000 -> MUST trigger with Severity.RED
    r04_250001 = evaluate_income("250001")
    assert len(r04_250001) == 1
    assert r04_250001[0].severity == Severity.RED
    assert "250,000" in r04_250001[0].reason

    r04_formatted = evaluate_income("₹2,50,001/-")
    assert len(r04_formatted) == 1
    assert r04_formatted[0].severity == Severity.RED

    r04_450k = evaluate_income("₹4,50,000/-")
    assert len(r04_450k) == 1
    assert r04_450k[0].severity == Severity.RED

    # 4. Missing annual income -> must NOT trigger
    assert len(evaluate_income(None)) == 0
    assert len(evaluate_income("")) == 0


def test_rule_gender_check():
    """Verify that a female gender record fires R-06 (Male only scheme)."""
    docs = _create_demo_documents()
    # Change gender to Female
    docs[0].extraction.fields[2].rawValue = "Female"

    snapshot = build_snapshot(docs)
    engine = RuleEngine()
    findings = engine.evaluate(snapshot, docs)

    rule_ids = [f.ruleId for f in findings]
    assert "R-06" in rule_ids
    r06 = next(f for f in findings if f.ruleId == "R-06")
    assert r06.severity == Severity.RED


def test_rule_missing_document():
    """Verify that omitting a mandatory role fires R-05."""
    docs = _create_demo_documents()
    # Remove Bank Proof
    docs_without_bank = [d for d in docs if d.role != DocumentRole.BANK_PROOF]

    snapshot = build_snapshot(docs_without_bank)
    engine = RuleEngine()
    findings = engine.evaluate(snapshot, docs_without_bank)

    rule_ids = [f.ruleId for f in findings]
    assert "R-05" in rule_ids
    r05 = next(f for f in findings if f.ruleId == "R-05")
    assert r05.severity == Severity.RED
    assert "BANK_PROOF" in r05.reason


def test_rule_processing_document_is_not_missing():
    """R-05 reflects upload presence, not asynchronous extraction timing."""
    docs = _create_demo_documents()
    income_doc = next(doc for doc in docs if doc.role == DocumentRole.INCOME_CERTIFICATE)
    income_doc.status = DocumentStatus.EXTRACTING
    income_doc.extraction = None

    findings = RuleEngine().evaluate(build_snapshot(docs), docs)
    assert "R-05" not in [finding.ruleId for finding in findings]


def test_rule_bank_account_holder_mismatch():
    """Verify that a bank account in someone else's name fires R-03."""
    docs = _create_demo_documents()
    # Change account holder name to someone else
    docs[3].extraction.fields[0].rawValue = "RAMESH KUMAR"

    snapshot = build_snapshot(docs)
    engine = RuleEngine()
    findings = engine.evaluate(snapshot, docs)

    rule_ids = [f.ruleId for f in findings]
    assert "R-03" in rule_ids
    r03 = next(f for f in findings if f.ruleId == "R-03")
    assert r03.severity == Severity.RED
    assert r03.needsAdjudication is True


def test_r11_size_semantics_and_boundaries():
    """Verify R-11 scheme size compliance semantics and distinct upload gate limits:
    - 150 KB (below 200 KB): upload valid, no warning, R-11 does NOT trigger
    - exactly 200 KB (204,800 bytes): upload valid, no warning, R-11 does NOT trigger
    - 204,801 bytes: upload valid, soft warning flagged, R-11 MUST trigger (AMBER)
    - 350 KB: upload valid, soft warning flagged, R-11 MUST trigger (AMBER)
    - 6 MB (> 5 MB API cap): rejected at upload layer (400 FILE_TOO_LARGE)
    """
    from backend.src.core.validators import validate_upload_constraints

    engine = RuleEngine()

    def evaluate_doc_size(size_bytes: int):
        doc = DocumentItem(
            documentId="doc-size-test",
            role=DocumentRole.MARKSHEET,
            fileName="marksheet.pdf",
            contentType="application/pdf",
            sizeBytes=size_bytes,
            status=DocumentStatus.EXTRACTED,
            extraction=DocumentExtraction(fields=[]),
        )
        snap = build_snapshot([doc])
        res = engine.evaluate(snap, [doc])
        return [f for f in res if f.ruleId == "R-11"]

    # 1. Below boundary: 150,000 bytes
    is_valid, err, has_warn = validate_upload_constraints("application/pdf", 150_000)
    assert is_valid is True
    assert err is None
    assert has_warn is False
    assert len(evaluate_doc_size(150_000)) == 0

    # 2. Exactly at 200 KB boundary: 204,800 bytes
    is_valid, err, has_warn = validate_upload_constraints("application/pdf", 204_800)
    assert is_valid is True
    assert err is None
    assert has_warn is False
    assert len(evaluate_doc_size(204_800)) == 0

    # 3. 1 byte above 200 KB boundary: 204,801 bytes
    is_valid, err, has_warn = validate_upload_constraints("application/pdf", 204_801)
    assert is_valid is True
    assert err is None
    assert has_warn is True  # Upload accepted but with soft recommendation warning
    r11_204801 = evaluate_doc_size(204_801)
    assert len(r11_204801) == 1
    assert r11_204801[0].severity == Severity.AMBER
    assert "200 KB" in r11_204801[0].reason

    # 4. Clearly above 200 KB but under 5 MB: 350,000 bytes
    is_valid, err, has_warn = validate_upload_constraints("application/pdf", 350_000)
    assert is_valid is True
    assert err is None
    assert has_warn is True
    r11_350k = evaluate_doc_size(350_000)
    assert len(r11_350k) == 1
    assert r11_350k[0].severity == Severity.AMBER
    assert "341 KB" in r11_350k[0].reason

    # 5. Above 5 MB API upload limit: 6 MB
    is_valid, err, has_warn = validate_upload_constraints("application/pdf", 6 * 1024 * 1024)
    assert is_valid is False
    assert "5 MB" in err
    # Demonstrates that >5MB files are rejected at the upload gate before ever reaching rules engine
