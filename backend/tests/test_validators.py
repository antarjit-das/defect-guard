"""Unit tests for Verhoeff algorithm, IFSC validation, and upload constraints.

Validates mathematical and regulatory checksums and constraints.
"""

from backend.src.core.validators import (
    validate_verhoeff,
    generate_verhoeff,
    validate_ifsc,
    validate_upload_constraints,
)


def test_verhoeff_algorithm():
    """Test the Verhoeff checksum algorithm for Aadhaar numbers."""
    base_number = "98765432101"
    check_digit = generate_verhoeff(base_number)
    valid_aadhaar = base_number + check_digit

    # Valid check digit passes
    assert validate_verhoeff(valid_aadhaar) is True

    # Single digit error (alter check digit)
    wrong_check_digit = str((int(check_digit) + 1) % 10)
    invalid_aadhaar = base_number + wrong_check_digit
    assert validate_verhoeff(invalid_aadhaar) is False

    # Transposition error (swap two adjacent digits)
    transposed = base_number[:-2] + base_number[-1] + base_number[-2] + check_digit
    assert validate_verhoeff(transposed) is False

    # Edge cases
    assert validate_verhoeff(None) is False
    assert validate_verhoeff("") is False
    assert validate_verhoeff("abc") is False


def test_ifsc_validator():
    """Test RBI IFSC code validation according to format ^[A-Z]{4}0[A-Z0-9]{6}$."""
    # Valid IFSC codes
    assert validate_ifsc("SBIN0001234") is True
    assert validate_ifsc("HDFC0000123") is True
    assert validate_ifsc("BARB0DISPUR") is True
    assert validate_ifsc("sbin0001234") is True  # Case insensitive

    # Invalid IFSC codes
    assert validate_ifsc("SBIN1001234") is False  # 5th char must be '0'
    assert validate_ifsc("SBI0001234") is False   # Too short (10 chars)
    assert validate_ifsc("SBIN00012345") is False # Too long (12 chars)
    assert validate_ifsc("12340001234") is False  # First 4 must be letters
    assert validate_ifsc(None) is False
    assert validate_ifsc("") is False


def test_upload_constraints():
    """Test file size and MIME type upload validation."""
    # Valid small PDF
    valid, err, warning = validate_upload_constraints("application/pdf", 150_000)
    assert valid is True
    assert err is None
    assert warning is False

    # Valid larger JPEG (exceeds 200 KB soft recommendation, but under 5 MB)
    valid, err, warning = validate_upload_constraints("image/jpeg", 350_000)
    assert valid is True
    assert err is None
    assert warning is True

    # Invalid MIME type
    valid, err, _ = validate_upload_constraints("application/zip", 100_000)
    assert valid is False
    assert "Unsupported file format" in err

    # Oversized file (> 5 MB)
    valid, err, _ = validate_upload_constraints("application/pdf", 6 * 1024 * 1024)
    assert valid is False
    assert "exceeds the 5 MB" in err
