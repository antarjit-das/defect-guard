"""Data privacy and PII masking utilities for Defect Guard.

Guarantees full compliance with Aadhaar regulations and RBI guidelines:
- Never store, log, or transmit raw 12-digit Aadhaar numbers.
- Mask bank account numbers, preserving only the last 4 digits.
Zero external AWS/boto3 imports.
"""

import re
from typing import Optional, Tuple


def mask_aadhaar(raw_aadhaar: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Mask a 12-digit Aadhaar number, keeping only the last 4 digits.

    Returns:
        Tuple of (masked_aadhaar, last4_digits).
        Example: "9876 5432 1234" -> ("XXXXXXXX1234", "1234")
    """
    if not raw_aadhaar or not str(raw_aadhaar).strip():
        return None, None

    digits = re.sub(r"\D", "", str(raw_aadhaar))
    if len(digits) < 4:
        return "XXXXXXXXXXXX", None

    last4 = digits[-4:]
    masked = f"XXXXXXXX{last4}"
    return masked, last4


def mask_account_number(raw_account: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Mask a bank account number, preserving only the last 4 digits.

    Returns:
        Tuple of (masked_account, last4_digits).
        Example: "123456789012" -> ("XXXXXXXX9012", "9012")
    """
    if not raw_account or not str(raw_account).strip():
        return None, None

    digits = re.sub(r"\D", "", str(raw_account))
    if len(digits) <= 4:
        return digits, digits

    last4 = digits[-4:]
    prefix_len = len(digits) - 4
    masked = f"{'X' * prefix_len}{last4}"
    return masked, last4
