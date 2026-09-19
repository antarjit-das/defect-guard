/**
 * mock-data.js — Pre-compiled Pydantic-verified Fixture Data
 *
 * Source of truth: frontend/fixtures/packet_checked.json and packet_rechecked.json.
 * Embedded directly to allow 100% offline operation without fetch/CORS obstacles.
 */

const DEMO_EXTRACTIONS = {
  AADHAAR: {
    roleConfirmed: true,
    documentQuality: "GOOD",
    fields: [
      { fieldKey: "student_name", rawValue: "ANTARJIT DAS", normalizedValue: "antarjit das", confidence: 0.98, evidence: "Name / নাম: ANTARJIT DAS", source: "TEXTRACT_QUERY", needsConfirmation: false },
      { fieldKey: "dob", rawValue: "12/03/2004", normalizedValue: "2004-03-12", confidence: 0.96, evidence: "DOB: 12/03/2004", source: "TEXTRACT_QUERY", needsConfirmation: false },
      { fieldKey: "gender", rawValue: "Male", normalizedValue: "male", confidence: 0.99, evidence: "Gender / লিঙ্গ: Male", source: "TEXTRACT_QUERY", needsConfirmation: false },
      { fieldKey: "aadhaar_last4", rawValue: "XXXX-XXXX-4821", normalizedValue: "4821", confidence: 0.97, evidence: "Aadhaar: XXXX XXXX 4821", source: "TEXTRACT_QUERY", needsConfirmation: false }
    ],
    notes: null
  },
  MARKSHEET: {
    roleConfirmed: true,
    documentQuality: "GOOD",
    fields: [
      { fieldKey: "student_name", rawValue: "ANTARJEET DASS", normalizedValue: "antarjeet dass", confidence: 0.96, evidence: "Candidate Name: ANTARJEET DASS", source: "TEXTRACT_QUERY", needsConfirmation: false },
      { fieldKey: "father_name", rawValue: "PRODIP DAS", normalizedValue: "prodip das", confidence: 0.95, evidence: "Father's Name: PRODIP DAS", source: "TEXTRACT_QUERY", needsConfirmation: false },
      { fieldKey: "roll_no", rawValue: "GU2024-883", normalizedValue: "gu2024-883", confidence: 0.93, evidence: "Roll No: GU2024-883", source: "TEXTRACT_QUERY", needsConfirmation: false },
      { fieldKey: "board_or_university", rawValue: "Gauhati University", normalizedValue: "gauhati university", confidence: 0.95, evidence: "Gauhati University Examination 2024", source: "TEXTRACT_QUERY", needsConfirmation: false },
      { fieldKey: "institution_name", rawValue: "Cotton University", normalizedValue: "cotton university", confidence: 0.91, evidence: "College: Cotton University, Guwahati", source: "TEXTRACT_QUERY", needsConfirmation: false },
      { fieldKey: "passing_year", rawValue: "2024", normalizedValue: "2024", confidence: 0.98, evidence: "Year of Examination: 2024", source: "TEXTRACT_QUERY", needsConfirmation: false },
      { fieldKey: "previous_percentage", rawValue: "72.4%", normalizedValue: "72.4", confidence: 0.94, evidence: "Percentage of Marks: 72.4%", source: "TEXTRACT_QUERY", needsConfirmation: false }
    ],
    notes: null
  },
  INCOME_DEFECTIVE: {
    roleConfirmed: true,
    documentQuality: "GOOD",
    fields: [
      { fieldKey: "parent_name", rawValue: "PRODIP DAS", normalizedValue: "prodip das", confidence: 0.95, evidence: "Son of Shri PRODIP DAS", source: "TEXTRACT_QUERY", needsConfirmation: false },
      { fieldKey: "annual_income", rawValue: "₹4,50,000/-", normalizedValue: 450000, confidence: 0.94, evidence: "Annual family income is Rs. 4,50,000/- (Rupees Four Lakh Fifty Thousand)", source: "TEXTRACT_QUERY", needsConfirmation: false },
      { fieldKey: "income_cert_date", rawValue: "10/05/2026", normalizedValue: "2026-05-10", confidence: 0.92, evidence: "Date of issue: 10/05/2026", source: "TEXTRACT_QUERY", needsConfirmation: false },
      { fieldKey: "income_cert_authority", rawValue: "Circle Officer, Dispur Revenue Circle", normalizedValue: "circle officer dispur revenue circle", confidence: 0.93, evidence: "Office of the Circle Officer, Dispur", source: "TEXTRACT_QUERY", needsConfirmation: false },
      { fieldKey: "income_cert_no", rawValue: "DIS/INC/2026/9821", normalizedValue: "dis/inc/2026/9821", confidence: 0.91, evidence: "Certificate No: DIS/INC/2026/9821", source: "TEXTRACT_QUERY", needsConfirmation: false }
    ],
    notes: null
  },
  INCOME_COMPLIANT: {
    roleConfirmed: true,
    documentQuality: "GOOD",
    fields: [
      { fieldKey: "parent_name", rawValue: "PRODIP DAS", normalizedValue: "prodip das", confidence: 0.96, evidence: "Son of Shri PRODIP DAS", source: "TEXTRACT_QUERY", needsConfirmation: false },
      { fieldKey: "annual_income", rawValue: "₹2,50,000/-", normalizedValue: 250000, confidence: 0.95, evidence: "Annual family income is Rs. 2,50,000/- (Rupees Two Lakh Fifty Thousand)", source: "TEXTRACT_QUERY", needsConfirmation: false },
      { fieldKey: "income_cert_date", rawValue: "15/06/2026", normalizedValue: "2026-06-15", confidence: 0.93, evidence: "Date of issue: 15/06/2026", source: "TEXTRACT_QUERY", needsConfirmation: false },
      { fieldKey: "income_cert_authority", rawValue: "Circle Officer, Dispur Revenue Circle", normalizedValue: "circle officer dispur revenue circle", confidence: 0.94, evidence: "Office of the Circle Officer, Dispur", source: "TEXTRACT_QUERY", needsConfirmation: false },
      { fieldKey: "income_cert_no", rawValue: "DIS/INC/2026/10442", normalizedValue: "dis/inc/2026/10442", confidence: 0.92, evidence: "Certificate No: DIS/INC/2026/10442", source: "TEXTRACT_QUERY", needsConfirmation: false }
    ],
    notes: null
  },
  BANK_PROOF: {
    roleConfirmed: true,
    documentQuality: "GOOD",
    fields: [
      { fieldKey: "account_holder_name", rawValue: "ANTARJIT DAS", normalizedValue: "antarjit das", confidence: 0.97, evidence: "Account Name: ANTARJIT DAS", source: "TEXTRACT_QUERY", needsConfirmation: false },
      { fieldKey: "bank_account_number", rawValue: "XXXXXX9821", normalizedValue: "9821", confidence: 0.96, evidence: "A/C No: XXXXXX9821", source: "TEXTRACT_QUERY", needsConfirmation: false },
      { fieldKey: "ifsc", rawValue: "SBIN0001234", normalizedValue: "sbin0001234", confidence: 0.95, evidence: "IFSC Code: SBIN0001234", source: "TEXTRACT_QUERY", needsConfirmation: false },
      { fieldKey: "bank_name", rawValue: "State Bank of India", normalizedValue: "state bank of india", confidence: 0.98, evidence: "Bank: State Bank of India, Dispur Branch", source: "TEXTRACT_QUERY", needsConfirmation: false },
      { fieldKey: "branch_name", rawValue: "Dispur Branch", normalizedValue: "dispur branch", confidence: 0.92, evidence: "Branch: Dispur Branch, Guwahati", source: "TEXTRACT_QUERY", needsConfirmation: false }
    ],
    notes: null
  }
};

const INITIAL_FINDINGS = [
  {
    findingId: "f1",
    ruleId: "R-01",
    title: "Student name mismatch across documents",
    severity: "RED",
    category: "IDENTITY",
    documents: [
      { role: "AADHAAR", value: "ANTARJIT DAS" },
      { role: "MARKSHEET", value: "ANTARJEET DASS" }
    ],
    reason: "The student name is spelled ANTARJIT DAS on Aadhaar but ANTARJEET DASS on the Marksheet. Verification officers will reject this discrepancy during scrutiny.",
    fixInstruction: "Verify which spelling matches your institutional admission register and provide an updated marksheet or affidavit matching your Aadhaar card.",
    confidence: 0.96,
    source: "MMNBA 2026 Verification Guidelines §3",
    needsAdjudication: true
  },
  {
    findingId: "f2",
    ruleId: "R-07",
    title: "Declared annual income exceeds scheme ceiling",
    severity: "RED",
    category: "ELIGIBILITY",
    documents: [
      { role: "INCOME_CERTIFICATE", value: "₹4,50,000" }
    ],
    reason: "The income certificate declares an annual family income of ₹4,50,000, which exceeds the mandatory scheme ceiling of ₹4,00,000.",
    fixInstruction: "Upload an income certificate from the competent Revenue Circle Officer showing annual family income strictly below ₹4,00,000.",
    confidence: 0.99,
    source: "MMNBA 2026 Executive Order Clause 4(b)",
    needsAdjudication: false
  },
  {
    findingId: "f3",
    ruleId: "R-04",
    title: "Institution enrollment requires verification",
    severity: "AMBER",
    category: "ELIGIBILITY",
    documents: [
      { role: "MARKSHEET", value: "Cotton University" }
    ],
    reason: "Marksheet indicates Cotton University. Ensure current admission is under the Govt of Assam Fee Waiver Scheme for UG/PG 1st or 2nd year.",
    fixInstruction: "Confirm with your college nodal officer that your admission slip reflects the Fee Waiver scheme before final portal submission.",
    confidence: 0.85,
    source: "MMNBA 2026 Institutional Eligibility Norms",
    needsAdjudication: false
  }
];

const RECHECK_FINDINGS = [
  {
    findingId: "f1",
    ruleId: "R-01",
    title: "Student name mismatch across documents",
    severity: "RED",
    category: "IDENTITY",
    documents: [
      { role: "AADHAAR", value: "ANTARJIT DAS" },
      { role: "MARKSHEET", value: "ANTARJEET DASS" }
    ],
    reason: "The student name is spelled ANTARJIT DAS on Aadhaar but ANTARJEET DASS on the Marksheet. Verification officers will reject this discrepancy during scrutiny.",
    fixInstruction: "Verify which spelling matches your institutional admission register and provide an updated marksheet or affidavit matching your Aadhaar card.",
    confidence: 0.96,
    source: "MMNBA 2026 Verification Guidelines §3",
    needsAdjudication: true
  },
  {
    findingId: "f3",
    ruleId: "R-04",
    title: "Institution enrollment requires verification",
    severity: "AMBER",
    category: "ELIGIBILITY",
    documents: [
      { role: "MARKSHEET", value: "Cotton University" }
    ],
    reason: "Marksheet indicates Cotton University. Ensure current admission is under the Govt of Assam Fee Waiver Scheme for UG/PG 1st or 2nd year.",
    fixInstruction: "Confirm with your college nodal officer that your admission slip reflects the Fee Waiver scheme before final portal submission.",
    confidence: 0.85,
    source: "MMNBA 2026 Institutional Eligibility Norms",
    needsAdjudication: false
  }
];

function buildSnapshotRows(incomeValue) {
  return [
    {
      fieldKey: "student_name",
      label: "Student Name",
      valuesByRole: { AADHAAR: "ANTARJIT DAS", MARKSHEET: "ANTARJEET DASS", BANK_PROOF: "ANTARJIT DAS" },
      canonicalValue: "ANTARJIT DAS",
      canonicalSource: "AADHAAR",
      hasDisagreement: true
    },
    {
      fieldKey: "parent_name",
      label: "Father / Parent Name",
      valuesByRole: { MARKSHEET: "PRODIP DAS", INCOME_CERTIFICATE: "PRODIP DAS" },
      canonicalValue: "PRODIP DAS",
      canonicalSource: "INCOME_CERTIFICATE",
      hasDisagreement: false
    },
    {
      fieldKey: "dob",
      label: "Date of Birth",
      valuesByRole: { AADHAAR: "2004-03-12" },
      canonicalValue: "2004-03-12",
      canonicalSource: "AADHAAR",
      hasDisagreement: false
    },
    {
      fieldKey: "gender",
      label: "Gender",
      valuesByRole: { AADHAAR: "Male" },
      canonicalValue: "Male",
      canonicalSource: "AADHAAR",
      hasDisagreement: false
    },
    {
      fieldKey: "annual_income",
      label: "Annual Family Income",
      valuesByRole: { INCOME_CERTIFICATE: String(incomeValue) },
      canonicalValue: String(incomeValue),
      canonicalSource: "INCOME_CERTIFICATE",
      hasDisagreement: false
    },
    {
      fieldKey: "institution_name",
      label: "Institution / College Name",
      valuesByRole: { MARKSHEET: "Cotton University" },
      canonicalValue: "Cotton University",
      canonicalSource: "MARKSHEET",
      hasDisagreement: false
    },
    {
      fieldKey: "account_holder_name",
      label: "Account Holder Name",
      valuesByRole: { BANK_PROOF: "ANTARJIT DAS" },
      canonicalValue: "ANTARJIT DAS",
      canonicalSource: "BANK_PROOF",
      hasDisagreement: false
    },
    {
      fieldKey: "bank_account_number",
      label: "Bank Account Number",
      valuesByRole: { BANK_PROOF: "XXXXXX9821" },
      canonicalValue: "XXXXXX9821",
      canonicalSource: "BANK_PROOF",
      hasDisagreement: false
    },
    {
      fieldKey: "ifsc",
      label: "IFSC Code",
      valuesByRole: { BANK_PROOF: "SBIN0001234" },
      canonicalValue: "SBIN0001234",
      canonicalSource: "BANK_PROOF",
      hasDisagreement: false
    }
  ];
}

// Export for Node and Browser
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    DEMO_EXTRACTIONS,
    INITIAL_FINDINGS,
    RECHECK_FINDINGS,
    buildSnapshotRows,
  };
} else {
  window.DefectGuardMockData = {
    DEMO_EXTRACTIONS,
    INITIAL_FINDINGS,
    RECHECK_FINDINGS,
    buildSnapshotRows,
  };
}
