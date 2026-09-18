"""Pure Python normalizers for scholarship document data.

Implements normalization for names, dates, currency/income, IFSC codes,
and account numbers as specified in IMPLEMENTATION.md §8.5.
Zero external AWS/boto3 imports.
"""

import re
from datetime import datetime
from typing import Optional, List, Tuple

# Honorifics and relationship prefixes common in Indian official documents
HONORIFICS_PATTERN = re.compile(
    r"\b(shri|smt|mr|mrs|ms|kum|kumar|kumari|late|dr|prof|s/o|d/o|w/o|c/o|son\s+of|daughter\s+of|wife\s+of)\b\.?",
    re.IGNORECASE,
)

# Punctuation to strip from names (preserves internal hyphens)
NAME_PUNCTUATION_PATTERN = re.compile(r"[^\w\s\-]")


def normalize_name(raw_name: Optional[str]) -> Tuple[Optional[str], List[str]]:
    """Clean and normalize a personal or institution name.

    Returns:
        Tuple of (normalized_string, list_of_tokens).
        Example: "Shri ANTARJIT  DAS, S/o Late Prodip" -> ("antarjit das prodip", ["antarjit", "das", "prodip"])
    """
    if not raw_name or not raw_name.strip():
        return None, []

    # Strip unwanted honorifics
    cleaned = HONORIFICS_PATTERN.sub(" ", raw_name)

    # Strip punctuation except hyphens
    cleaned = NAME_PUNCTUATION_PATTERN.sub(" ", cleaned)

    # Collapse whitespace and convert to lowercase
    tokens = [token.lower() for token in cleaned.split() if token.strip()]
    if not tokens:
        return None, []

    normalized = " ".join(tokens)
    return normalized, tokens


def normalize_date(raw_date: Optional[str]) -> Optional[str]:
    """Parse common Indian and standard date formats into ISO YYYY-MM-DD.

    Supports:
        - DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
        - YYYY-MM-DD, YYYY/MM/DD
        - D MMM YYYY, DD MMMM YYYY (e.g., 12 Mar 2004, 12 March 2004)
        - 2-digit years with a 40-year pivot (e.g., 04 -> 2004, 98 -> 1998)
    """
    if not raw_date or not raw_date.strip():
        return None

    cleaned = raw_date.strip()
    # Normalize separators
    cleaned = re.sub(r"[\.,]", "/", cleaned)
    cleaned = re.sub(r"[-]", "/", cleaned)

    # Supported date parsing formats
    date_formats = [
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%d/%m/%y",
        "%d/%b/%Y",
        "%d/%B/%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%Y-%m-%d",
    ]

    for fmt in date_formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            # Two-digit year pivot check: if year is in far future, adjust to 1900s
            if dt.year > datetime.now().year + 1:
                dt = dt.replace(year=dt.year - 100)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def normalize_money(raw_money: Optional[str]) -> Optional[int]:
    """Normalize Indian currency amounts into integer rupees.

    Handles:
        - "₹4,50,000/-" -> 450000
        - "Rs. 2,60,000" -> 260000
        - "2.6 Lakh" or "4 Lakh" -> 260000, 400000
        - "4.5 Lakhs" -> 450000
    """
    if not raw_money or not str(raw_money).strip():
        return None

    cleaned = str(raw_money).strip()

    # Check for Lakh/Lakhs notation (e.g., "4.5 Lakh" or "4 Lakhs")
    lakh_match = re.search(r"([\d\.]+)\s*(?:lakh|lakhs|lac|lacs)", cleaned, re.IGNORECASE)
    if lakh_match:
        try:
            val = float(lakh_match.group(1))
            return int(val * 100_000)
        except ValueError:
            pass

    # Strip currency symbols, commas, and trailing "/-"
    cleaned = re.sub(r"[₹\$,]", "", cleaned)
    cleaned = re.sub(r"\b(rs|inr)\.?\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"/-\s*$", "", cleaned)
    cleaned = cleaned.strip()

    # Extract digits
    digits_match = re.search(r"(\d+)", cleaned)
    if digits_match:
        try:
            return int(digits_match.group(1))
        except ValueError:
            return None

    return None


def normalize_ifsc(raw_ifsc: Optional[str]) -> Optional[str]:
    """Normalize an IFSC code: uppercase, trim, remove whitespace and hyphens."""
    if not raw_ifsc or not raw_ifsc.strip():
        return None

    cleaned = re.sub(r"[\s\-]", "", raw_ifsc).upper()
    return cleaned if cleaned else None


def normalize_account_number(raw_account: Optional[str]) -> Optional[str]:
    """Normalize a bank account number: extract digits only."""
    if not raw_account or not raw_account.strip():
        return None

    digits = re.sub(r"\D", "", raw_account)
    return digits if digits else None


def normalize_aadhaar(raw_aadhaar: Optional[str]) -> Optional[str]:
    """Normalize an Aadhaar number: extract digits only."""
    if not raw_aadhaar or not raw_aadhaar.strip():
        return None

    digits = re.sub(r"\D", "", raw_aadhaar)
    return digits if digits else None
