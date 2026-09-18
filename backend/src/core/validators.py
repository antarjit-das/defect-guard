"""Pure Python validators for Indian scholarship document data and uploads.

Includes:
- Verhoeff checksum algorithm for Aadhaar validation.
- RBI IFSC code regex validation.
- Upload MIME type and file size validation.
Zero external AWS/boto3 imports.
"""

import re
from typing import Optional, Tuple, Set

# --- Verhoeff Algorithm Tables ---
# Dihedral group D5 multiplication table
VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)

# Permutation table
VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)

# Inverse table
VERHOEFF_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)


def validate_verhoeff(number_str: Optional[str]) -> bool:
    """Validate a number string using the Verhoeff checksum algorithm.

    Used by UIDAI for 12-digit Indian Aadhaar numbers.
    The last digit is the Verhoeff checksum.
    """
    if not number_str or not isinstance(number_str, str):
        return False

    cleaned = re.sub(r"\D", "", number_str)
    if not cleaned:
        return False

    c = 0
    # Process digits in reverse order (from right to left)
    for i, char in enumerate(reversed(cleaned)):
        digit = int(char)
        c = VERHOEFF_D[c][VERHOEFF_P[i % 8][digit]]

    return c == 0


def generate_verhoeff(number_str: str) -> str:
    """Generate the Verhoeff check digit for a string of numbers.

    Appends the calculated check digit to produce a valid Verhoeff number.
    """
    cleaned = re.sub(r"\D", "", number_str)
    c = 0
    for i, char in enumerate(reversed(cleaned)):
        digit = int(char)
        c = VERHOEFF_D[c][VERHOEFF_P[(i + 1) % 8][digit]]

    return str(VERHOEFF_INV[c])


# --- IFSC Validation ---
# Indian Financial System Code: 4 letters, 0, 6 alphanumeric characters
IFSC_REGEX = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")


def validate_ifsc(ifsc_code: Optional[str]) -> bool:
    """Validate an Indian Financial System Code (IFSC) format according to RBI norms."""
    if not ifsc_code or not isinstance(ifsc_code, str):
        return False

    cleaned = ifsc_code.strip().upper()
    return bool(IFSC_REGEX.match(cleaned))


# --- Upload & File Constraints ---
ALLOWED_MIME_TYPES: Set[str] = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}

MAX_FILE_BYTES: int = 5 * 1024 * 1024  # 5 MB
PORTAL_SOFT_WARNING_BYTES: int = 200 * 1024  # 200 KB standard scholarship portal recommendation


def validate_upload_constraints(
    content_type: str,
    size_bytes: int,
) -> Tuple[bool, Optional[str], bool]:
    """Validate document upload constraints.

    Returns:
        Tuple of (is_valid, error_message, has_size_warning).
    """
    # MIME validation
    if content_type.lower() not in ALLOWED_MIME_TYPES:
        return (
            False,
            f"Unsupported file format '{content_type}'. Allowed formats: PDF, JPEG, PNG.",
            False,
        )

    # Size cap validation
    if size_bytes > MAX_FILE_BYTES:
        return (
            False,
            f"File size ({size_bytes} bytes) exceeds the 5 MB maximum allowed upload size.",
            False,
        )

    # Soft warning for files exceeding 200 KB (NSP recommendation)
    has_warning = size_bytes > PORTAL_SOFT_WARNING_BYTES
    return True, None, has_warning
