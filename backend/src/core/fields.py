"""Canonical field keys, document roles, and Textract query configurations.

This module acts as the single shared dictionary between:
1. Document OCR extraction queries.
2. AI extraction prompts.
3. Snapshot table rows.
4. Deterministic scheme validation rules.
"""

from typing import Final, List, Dict

# --- Document Roles ---
ROLE_AADHAAR: Final[str] = "AADHAAR"
ROLE_INCOME_CERTIFICATE: Final[str] = "INCOME_CERTIFICATE"
ROLE_MARKSHEET: Final[str] = "MARKSHEET"
ROLE_BANK_PROOF: Final[str] = "BANK_PROOF"

ALL_ROLES: Final[List[str]] = [
    ROLE_AADHAAR,
    ROLE_INCOME_CERTIFICATE,
    ROLE_MARKSHEET,
    ROLE_BANK_PROOF,
]

# Canonical precedence when picking the authoritative value for the snapshot
ROLE_PRECEDENCE: Final[List[str]] = [
    ROLE_AADHAAR,
    ROLE_MARKSHEET,
    ROLE_INCOME_CERTIFICATE,
    ROLE_BANK_PROOF,
]

# --- 21 Canonical Scheme Field Keys ---
FIELD_STUDENT_NAME: Final[str] = "student_name"
FIELD_FATHER_NAME: Final[str] = "father_name"
FIELD_PARENT_NAME: Final[str] = "parent_name"
FIELD_DOB: Final[str] = "dob"
FIELD_GENDER: Final[str] = "gender"
FIELD_AADHAAR_LAST4: Final[str] = "aadhaar_last4"
FIELD_ANNUAL_INCOME: Final[str] = "annual_income"
FIELD_INCOME_CERT_DATE: Final[str] = "income_cert_date"
FIELD_INCOME_CERT_AUTHORITY: Final[str] = "income_cert_authority"
FIELD_INCOME_CERT_NO: Final[str] = "income_cert_no"
FIELD_INSTITUTION_NAME: Final[str] = "institution_name"
FIELD_ADMISSION_YEAR: Final[str] = "admission_year"
FIELD_FEE_WAIVER_STATUS: Final[str] = "fee_waiver_status"
FIELD_BANK_ACCOUNT_NUMBER: Final[str] = "bank_account_number"
FIELD_IFSC: Final[str] = "ifsc"
FIELD_ACCOUNT_HOLDER_NAME: Final[str] = "account_holder_name"
FIELD_BANK_BRANCH: Final[str] = "bank_branch"
FIELD_ROLL_NO: Final[str] = "roll_no"
FIELD_BOARD_OR_UNIVERSITY: Final[str] = "board_or_university"
FIELD_PASSING_YEAR: Final[str] = "passing_year"
FIELD_PREVIOUS_PERCENTAGE: Final[str] = "previous_percentage"

ALL_FIELD_KEYS: Final[List[str]] = [
    FIELD_STUDENT_NAME,
    FIELD_FATHER_NAME,
    FIELD_PARENT_NAME,
    FIELD_DOB,
    FIELD_GENDER,
    FIELD_AADHAAR_LAST4,
    FIELD_ANNUAL_INCOME,
    FIELD_INCOME_CERT_DATE,
    FIELD_INCOME_CERT_AUTHORITY,
    FIELD_INCOME_CERT_NO,
    FIELD_INSTITUTION_NAME,
    FIELD_ADMISSION_YEAR,
    FIELD_FEE_WAIVER_STATUS,
    FIELD_BANK_ACCOUNT_NUMBER,
    FIELD_IFSC,
    FIELD_ACCOUNT_HOLDER_NAME,
    FIELD_BANK_BRANCH,
    FIELD_ROLL_NO,
    FIELD_BOARD_OR_UNIVERSITY,
    FIELD_PASSING_YEAR,
    FIELD_PREVIOUS_PERCENTAGE,
]

# User-facing labels for the snapshot rows
FIELD_LABELS: Final[Dict[str, str]] = {
    FIELD_STUDENT_NAME: "Student Name",
    FIELD_FATHER_NAME: "Father's Name",
    FIELD_PARENT_NAME: "Parent/Guardian Name",
    FIELD_DOB: "Date of Birth",
    FIELD_GENDER: "Gender",
    FIELD_AADHAAR_LAST4: "Aadhaar (Last 4 Digits)",
    FIELD_ANNUAL_INCOME: "Annual Family Income",
    FIELD_INCOME_CERT_DATE: "Income Certificate Issue Date",
    FIELD_INCOME_CERT_AUTHORITY: "Issuing Authority",
    FIELD_INCOME_CERT_NO: "Certificate Number",
    FIELD_INSTITUTION_NAME: "Institution / College Name",
    FIELD_ADMISSION_YEAR: "Year of Admission",
    FIELD_FEE_WAIVER_STATUS: "Fee Waiver Scheme Admission",
    FIELD_BANK_ACCOUNT_NUMBER: "Bank Account Number",
    FIELD_IFSC: "IFSC Code",
    FIELD_ACCOUNT_HOLDER_NAME: "Account Holder Name",
    FIELD_BANK_BRANCH: "Bank & Branch Name",
    FIELD_ROLL_NO: "Roll / Registration Number",
    FIELD_BOARD_OR_UNIVERSITY: "Board / University",
    FIELD_PASSING_YEAR: "Year of Passing",
    FIELD_PREVIOUS_PERCENTAGE: "Marks Percentage / CGPA",
}

# Role-specific fields extracted from each document
ROLE_FIELDS: Final[Dict[str, List[str]]] = {
    ROLE_AADHAAR: [
        FIELD_STUDENT_NAME,
        FIELD_DOB,
        FIELD_GENDER,
        FIELD_AADHAAR_LAST4,
    ],
    ROLE_INCOME_CERTIFICATE: [
        FIELD_PARENT_NAME,
        FIELD_ANNUAL_INCOME,
        FIELD_INCOME_CERT_DATE,
        FIELD_INCOME_CERT_AUTHORITY,
        FIELD_INCOME_CERT_NO,
    ],
    ROLE_MARKSHEET: [
        FIELD_STUDENT_NAME,
        FIELD_FATHER_NAME,
        FIELD_ROLL_NO,
        FIELD_BOARD_OR_UNIVERSITY,
        FIELD_INSTITUTION_NAME,
        FIELD_PASSING_YEAR,
        FIELD_PREVIOUS_PERCENTAGE,
    ],
    ROLE_BANK_PROOF: [
        FIELD_ACCOUNT_HOLDER_NAME,
        FIELD_BANK_ACCOUNT_NUMBER,
        FIELD_IFSC,
        FIELD_BANK_BRANCH,
    ],
}

# Amazon Textract Natural Language Queries per document role
# Kept strictly under 15 queries per call (averaging 4 to 6 queries)
TEXTRACT_QUERIES: Final[Dict[str, List[Dict[str, str]]]] = {
    ROLE_AADHAAR: [
        {"Text": "What is the name?", "Alias": FIELD_STUDENT_NAME},
        {"Text": "What is the date of birth?", "Alias": FIELD_DOB},
        {"Text": "What is the Aadhaar number?", "Alias": "aadhaar_number"},
        {"Text": "What is the gender?", "Alias": FIELD_GENDER},
    ],
    ROLE_INCOME_CERTIFICATE: [
        {"Text": "Whose income is certified?", "Alias": FIELD_PARENT_NAME},
        {"Text": "What is the annual income?", "Alias": FIELD_ANNUAL_INCOME},
        {"Text": "What is the date of issue?", "Alias": FIELD_INCOME_CERT_DATE},
        {"Text": "Which authority issued this certificate?", "Alias": FIELD_INCOME_CERT_AUTHORITY},
        {"Text": "What is the certificate number?", "Alias": FIELD_INCOME_CERT_NO},
    ],
    ROLE_MARKSHEET: [
        {"Text": "What is the student's name?", "Alias": FIELD_STUDENT_NAME},
        {"Text": "What is the father's name?", "Alias": FIELD_FATHER_NAME},
        {"Text": "What is the roll number?", "Alias": FIELD_ROLL_NO},
        {"Text": "Which board or university issued this?", "Alias": FIELD_BOARD_OR_UNIVERSITY},
        {"Text": "What is the institution or college name?", "Alias": FIELD_INSTITUTION_NAME},
        {"Text": "What is the year of passing?", "Alias": FIELD_PASSING_YEAR},
        {"Text": "What is the percentage or CGPA?", "Alias": FIELD_PREVIOUS_PERCENTAGE},
    ],
    ROLE_BANK_PROOF: [
        {"Text": "What is the account holder's name?", "Alias": FIELD_ACCOUNT_HOLDER_NAME},
        {"Text": "What is the account number?", "Alias": FIELD_BANK_ACCOUNT_NUMBER},
        {"Text": "What is the IFSC code?", "Alias": FIELD_IFSC},
        {"Text": "What is the bank and branch name?", "Alias": FIELD_BANK_BRANCH},
    ],
}
