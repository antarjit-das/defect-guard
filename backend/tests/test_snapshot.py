"""Unit tests for Application Snapshot builder.

Verifies canonical precedence, disagreement detection, and superseded document filtering.
"""

from backend.src.core.models import (
    DocumentItem,
    DocumentRole,
    DocumentStatus,
    DocumentExtraction,
    ExtractedField,
)
from backend.src.core.snapshot import build_snapshot


def test_snapshot_canonical_precedence():
    """Test that canonical values follow AADHAAR > MARKSHEET > INCOME_CERTIFICATE > BANK_PROOF."""
    doc_aadhaar = DocumentItem(
        documentId="doc-1",
        role=DocumentRole.AADHAAR,
        fileName="aadhaar.jpg",
        contentType="image/jpeg",
        sizeBytes=100000,
        status=DocumentStatus.EXTRACTED,
        extraction=DocumentExtraction(
            fields=[
                ExtractedField(fieldKey="student_name", rawValue="ANTARJIT DAS"),
                ExtractedField(fieldKey="dob", rawValue="2004-03-12"),
            ]
        ),
    )

    doc_marksheet = DocumentItem(
        documentId="doc-2",
        role=DocumentRole.MARKSHEET,
        fileName="marksheet.pdf",
        contentType="application/pdf",
        sizeBytes=120000,
        status=DocumentStatus.EXTRACTED,
        extraction=DocumentExtraction(
            fields=[
                ExtractedField(fieldKey="student_name", rawValue="ANTARJEET DASS"),
                ExtractedField(fieldKey="father_name", rawValue="PRODIP DAS"),
            ]
        ),
    )

    snapshot = build_snapshot([doc_aadhaar, doc_marksheet])

    name_row = next(r for r in snapshot.rows if r.fieldKey == "student_name")
    assert name_row.canonicalValue == "ANTARJIT DAS"
    assert name_row.canonicalSource == "AADHAAR"
    assert name_row.hasDisagreement is True

    # Marksheet is canonical for father_name since Aadhaar has no father_name field
    father_row = next(r for r in snapshot.rows if r.fieldKey == "father_name")
    assert father_row.canonicalValue == "PRODIP DAS"
    assert father_row.canonicalSource == "MARKSHEET"
    assert father_row.hasDisagreement is False


def test_snapshot_disagreement_with_normalization():
    """Test that formatting/honorific differences are NOT falsely flagged as disagreements."""
    doc_marksheet = DocumentItem(
        documentId="doc-2",
        role=DocumentRole.MARKSHEET,
        fileName="marksheet.pdf",
        contentType="application/pdf",
        sizeBytes=120000,
        status=DocumentStatus.EXTRACTED,
        extraction=DocumentExtraction(
            fields=[
                ExtractedField(fieldKey="father_name", rawValue="PRODIP DAS"),
            ]
        ),
    )

    doc_income = DocumentItem(
        documentId="doc-3",
        role=DocumentRole.INCOME_CERTIFICATE,
        fileName="income.pdf",
        contentType="application/pdf",
        sizeBytes=110000,
        status=DocumentStatus.EXTRACTED,
        extraction=DocumentExtraction(
            fields=[
                # Notice "Shri" prefix and extra spaces
                ExtractedField(fieldKey="father_name", rawValue="Shri  PRODIP   DAS"),
            ]
        ),
    )

    snapshot = build_snapshot([doc_marksheet, doc_income])
    father_row = next(r for r in snapshot.rows if r.fieldKey == "father_name")

    # Normalization strips Shri and collapses spaces, so they agree!
    assert father_row.hasDisagreement is False
    assert father_row.canonicalValue == "PRODIP DAS"


def test_snapshot_money_comparison():
    """Test that currency formatting differences are recognized as matching."""
    doc_1 = DocumentItem(
        documentId="doc-1",
        role=DocumentRole.INCOME_CERTIFICATE,
        fileName="income.pdf",
        contentType="application/pdf",
        sizeBytes=110000,
        status=DocumentStatus.EXTRACTED,
        extraction=DocumentExtraction(
            fields=[
                ExtractedField(fieldKey="annual_income", rawValue="₹4,50,000/-"),
            ]
        ),
    )
    doc_2 = DocumentItem(
        documentId="doc-2",
        role=DocumentRole.MARKSHEET,
        fileName="form.pdf",
        contentType="application/pdf",
        sizeBytes=110000,
        status=DocumentStatus.EXTRACTED,
        extraction=DocumentExtraction(
            fields=[
                ExtractedField(fieldKey="annual_income", rawValue="4.5 Lakh"),
            ]
        ),
    )

    snapshot = build_snapshot([doc_1, doc_2])
    income_row = next(r for r in snapshot.rows if r.fieldKey == "annual_income")
    assert income_row.hasDisagreement is False


def test_snapshot_superseded_and_failed_exclusion():
    """Test that superseded documents and unextracted documents are ignored."""
    doc_old = DocumentItem(
        documentId="doc-old",
        role=DocumentRole.INCOME_CERTIFICATE,
        fileName="old_income.pdf",
        contentType="application/pdf",
        sizeBytes=100000,
        status=DocumentStatus.EXTRACTED,
        supersededBy="doc-new",  # Marked as superseded!
        extraction=DocumentExtraction(
            fields=[ExtractedField(fieldKey="annual_income", rawValue="900000")]
        ),
    )

    doc_new = DocumentItem(
        documentId="doc-new",
        role=DocumentRole.INCOME_CERTIFICATE,
        fileName="new_income.pdf",
        contentType="application/pdf",
        sizeBytes=100000,
        status=DocumentStatus.EXTRACTED,
        supersededBy=None,
        extraction=DocumentExtraction(
            fields=[ExtractedField(fieldKey="annual_income", rawValue="350000")]
        ),
    )

    doc_pending = DocumentItem(
        documentId="doc-pending",
        role=DocumentRole.MARKSHEET,
        fileName="pending.pdf",
        contentType="application/pdf",
        sizeBytes=100000,
        status=DocumentStatus.PENDING_UPLOAD,
        extraction=None,
    )

    snapshot = build_snapshot([doc_old, doc_new, doc_pending])
    assert len(snapshot.rows) == 1
    income_row = snapshot.rows[0]
    assert income_row.canonicalValue == "350000"
    assert "900000" not in income_row.valuesByRole.values()
