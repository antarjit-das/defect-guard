"""Unit tests for core normalizers and masking functions.

Validates name cleaning, date parsing, currency conversion, and PII masking.
"""

from backend.src.core.normalize import (
    normalize_name,
    normalize_date,
    normalize_money,
    normalize_ifsc,
    normalize_account_number,
    normalize_aadhaar,
)
from backend.src.core.masking import (
    mask_aadhaar,
    mask_account_number,
)


def test_normalize_name():
    """Test personal name normalization and tokenization across various Indian honorifics."""
    # Simple capitalization & whitespace
    norm, tokens = normalize_name("  ANTARJIT   DAS  ")
    assert norm == "antarjit das"
    assert tokens == ["antarjit", "das"]

    # Honorific Shri / Late
    norm, tokens = normalize_name("Shri ANTARJIT DAS")
    assert norm == "antarjit das"
    assert "shri" not in tokens

    # S/o (Son of) and punctuation
    norm, tokens = normalize_name("Rahul Das, S/o Late Prodip Das")
    assert norm == "rahul das prodip das"
    assert "s/o" not in tokens
    assert "late" not in tokens

    # Female honorifics
    norm, tokens = normalize_name("Smt. Ananya Devi")
    assert norm == "ananya devi"

    norm, tokens = normalize_name("Ms. Priyanka Barman")
    assert norm == "priyanka barman"

    # Empty / None
    assert normalize_name(None) == (None, [])
    assert normalize_name("   ") == (None, [])


def test_normalize_date():
    """Test date parsing across various Indian date formats into ISO YYYY-MM-DD."""
    assert normalize_date("12/03/2004") == "2004-03-12"
    assert normalize_date("12-03-2004") == "2004-03-12"
    assert normalize_date("12.03.2004") == "2004-03-12"
    assert normalize_date("2004-03-12") == "2004-03-12"
    assert normalize_date("12 Mar 2004") == "2004-03-12"
    assert normalize_date("12 March 2004") == "2004-03-12"
    assert normalize_date("12/03/04") == "2004-03-12"

    # Invalid dates
    assert normalize_date("not-a-date") is None
    assert normalize_date(None) is None


def test_normalize_money():
    """Test currency normalization from strings, symbols, and Lakh notations to integer rupees."""
    assert normalize_money("₹4,50,000/-") == 450000
    assert normalize_money("Rs. 2,60,000") == 260000
    assert normalize_money("2.6 Lakh") == 260000
    assert normalize_money("4 Lakhs") == 400000
    assert normalize_money("4.5 Lacs") == 450000
    assert normalize_money("350000") == 350000
    assert normalize_money("Rs. 1,00,000/-") == 100000

    # Invalid / empty
    assert normalize_money(None) is None
    assert normalize_money("unknown") is None


def test_normalize_ifsc():
    """Test IFSC code cleanup."""
    assert normalize_ifsc(" sbin0001234 ") == "SBIN0001234"
    assert normalize_ifsc("SBIN-0001234") == "SBIN0001234"
    assert normalize_ifsc(None) is None


def test_normalize_account_and_aadhaar():
    """Test account number and Aadhaar digit extraction."""
    assert normalize_account_number("1234-5678-9012") == "123456789012"
    assert normalize_aadhaar("9876 5432 1234") == "987654321234"
    assert normalize_account_number(None) is None


def test_masking():
    """Test PII masking for Aadhaar and bank account numbers."""
    masked_aadhaar, last4_aadhaar = mask_aadhaar("9876 5432 1234")
    assert masked_aadhaar == "XXXXXXXX1234"
    assert last4_aadhaar == "1234"

    masked_acc, last4_acc = mask_account_number("123456789012")
    assert masked_acc == "XXXXXXXX9012"
    assert last4_acc == "9012"

    # Short numbers
    assert mask_aadhaar(None) == (None, None)
    assert mask_account_number("123") == ("123", "123")
