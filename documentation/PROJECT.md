# PROJECT.md — Defect Guard

**Status:** Final planning document. Source of truth for *what* we are building and *why*.
**Companion document:** `IMPLEMENTATION.md` (how and when).
**Event:** First Commit — Bharat Builds Tour (WeMakeDevs × AWS), 17–20 September 2026, online.
**Track:** Ship It (deployed on AWS, public URL). One submission is also considered for Build It and Best UI.
**Last updated:** 18 September 2026.

---

## 1. Project Overview

### Project name
**Defect Guard — Nijut Babu Pre-Submission Checker**

### One-line description
Defect Guard checks a student's Nijut Babu application documents before submission, detects inconsistent or potentially defective information, explains exactly what needs to be fixed, and lets the student re-check after replacing a document.

### Product definition
A student uploads the 4 documents they are about to attach to their Mukhya Mantrir Nijut Babu Aasoni application (Aadhaar, Income Certificate, Marksheet, Bank Proof). Defect Guard:

1. Extracts the identity, economic, bank and academic fields from each document independently.
2. Builds a single **Application Snapshot** — one row per field, one column per document — that shows what each document actually says.
3. Runs a **scheme rule set** (deterministic) over that snapshot: cross-document contradictions, threshold breaches, missing mandatory documents, file-format and size violations.
4. Uses AI reasoning as an **ambiguity adjudicator** for the parts that are genuinely judgement calls — chiefly "are `RAHUL DAS` and `RAHUL DASS` the same person or a real mismatch?" — and to write the fix instruction in plain language grounded in the actual evidence.
5. Returns a **Defect Report**: a ranked red/amber/verify list, each item naming the rule, the documents that disagree, the value in each, and the specific action to take, plus a deterministic **Application Document Readiness** score.

The output is not a chat answer or a summary. It is a verdict table plus a fix list.

### The problem
Government scholarship applications in India are rejected or returned far more often for **clerical** reasons than for eligibility reasons. The verification process is essentially a document-versus-form matching exercise. A student who spells their surname one way on the marksheet and another on the Aadhaar card, or whose income certificate says ₹4,60,000 against a ₹4,00,000 ceiling, or who uploaded an unreadable scan, will not be told at submission time. They will be told weeks later that the application is defective. Nothing in the student's tooling checks the documents *against each other* before submission.

### Product Identity & Positioning
The product is a:
- pre-submission document checker
- document extraction system
- cross-document consistency checker
- deterministic validation engine
- AI-assisted ambiguity adjudicator
- readiness/reporting tool

It is **NOT**:
- the official Assam government application portal
- the official MMNBA eligibility authority
- a benefit approval system
- a submission bot
- an application decision engine
- a document generator
- a document forgery system
- a replacement for institutional verification
- a guarantee of receiving MMNBA financial assistance

The product makes a clear distinction between:
"Defect Guard found a document inconsistency" and "The Government of Assam has determined that this student is eligible." We never conflate the two.

---

## 2. Target User

### Primary user
**An undergraduate or postgraduate male student in Assam, applying for the Mukhya Mantrir Nijut Babu Aasoni, AY 2026, as a fresh applicant, in the week before they hit final submit.**

### User pain
1. **No pre-flight check exists.** The portal validates format, not truth. Nothing compares Aadhaar to the marksheet.
2. **The feedback loop is weeks long.**
3. **The fix is often trivial once known** — re-scan at lower size, use the correct income certificate, correct one digit of the account number — but the student does not know *which* of the documents is wrong.
4. **Nobody owns the cross-document view.**

---

## 3. Problem Evidence

Each claim below is tagged **FACT** (verified against the official MMNBA 2026 guideline or application form) or **SECONDARY** (inferred).

| # | Claim | Status | Source |
|---|---|---|---|
| E1 | Scheme is explicitly for male students enrolled in UG 1st and 2nd Years and PG 1st and 2nd Years in Govt/Provincialised Institutions. | **FACT** | MMNBA 2026 Executive Order |
| E2 | Students must belong to families with an annual income below ₹4.00 lakh. | **FACT** | MMNBA 2026 Executive Order |
| E3 | Students must be admitted under the Fee Waiver Scheme of the Govt of Assam. | **FACT** | MMNBA 2026 Executive Order |
| E4 | A valid Aadhaar number and an Aadhaar-seeded bank account are mandatory for DBT. | **FACT** | MMNBA 2026 Executive Order |
| E5 | A valid income certificate from the competent authority or ration card is required for verification and upload. | **FACT** | MMNBA 2026 Executive Order |
| E6 | Married UG male students are NOT eligible. | **FACT** | MMNBA 2026 Executive Order |
| E7 | Students who opted for Dr. Banikanta Kakati Merit Award (Scooter) or CM's Jibon Prerana Scheme are NOT eligible. | **FACT** | MMNBA 2026 Executive Order |

---

## 4. Product Vision

**Ultimately:** Defect Guard becomes the pre-flight check that sits between a student and any Indian government benefit application.

**What matters most, in order:**
1. **The verdict must be trustworthy and specific.**
2. **Every finding must be traceable to a rule and to evidence in a named document.**
3. **The student stays in control.**
4. **Privacy is part of the product, not a disclaimer.**

---

## 5. Core User Journey

The central demo loop:
**UPLOAD ↓ EXTRACT ↓ SNAPSHOT ↓ FIND DEFECTS ↓ FIX ↓ RE-CHECK ↓ READY**

1. **Land.** Student lands on Defect Guard and enters the Nijut Babu 2026 workflow.
2. **Upload.** Student uploads the required application documents (Aadhaar, Income Certificate, Marksheet, Bank Proof).
3. **Extraction.** Defect Guard identifies each uploaded document by role. Textract extracts relevant fields. Defect Guard stores extracted values with confidence and evidence locations.
4. **Snapshot.** The system builds an Application Snapshot.
5. **Rules.** Deterministic MMNBA rules run. AI adjudication handles ambiguous/conflicting evidence.
6. **Defect Report.** Defect Guard generates a ranked defect report. Each finding contains: issue, severity, evidence, why it matters, exact recommended fix, confidence, and FIX vs VERIFY status.
7. **Readiness Score.** Defect Guard calculates an Application Document Readiness score.
8. **Fix and Re-check.** Student replaces or corrects a document. Student clicks Re-check. The system re-runs extraction and validation. Findings are updated. Student receives a final fix list.

---

## 6. MMNBA-Specific Data Model

The document roles required for the MVP:
- `AADHAAR`
- `INCOME_CERTIFICATE`
- `MARKSHEET`
- `BANK_PROOF`

### Normalized Field Model

| Field | Type | Normalized | Source Documents | Evidence Required | Cross-document check | Verification Level |
|---|---|---|---|---|---|---|
| `student_name` | string | true | Aadhaar, Marksheet, Bank Proof, Income Cert | true | true | document_consistency |
| `dob` | date | true | Aadhaar | true | false | document_consistency |
| `father_name` | string | true | Marksheet, Income Cert | true | true | document_consistency |
| `gender` | string | true | Aadhaar | true | false | scheme_rule |
| `annual_income` | number | true | Income Cert | true | false | scheme_rule |
| `institution_name` | string | true | Marksheet | true | false | verify |
| `account_holder_name` | string | true | Bank Proof | true | true | document_consistency |
| `bank_account_number` | string | true | Bank Proof | true | false | document_consistency |
| `ifsc` | string | true | Bank Proof | true | false | format_check |

---

## 7. Rule Engine

The rule categories derived directly from the MMNBA 2026 guidelines.

### Rule category A — Identity consistency
- R-01: Student name mismatch across documents (RED)
- R-02: Father's/guardian's name mismatch (RED)
- R-03: Account holder name mismatch (RED)

### Rule category B — Academic consistency
- R-04: Institution name mismatch or requires verification (VERIFY)

### Rule category C — Scheme-specific requirements
- R-05: Missing mandatory supporting document (RED)
- R-06: Gender is not Male (RED) — "The incentive shall be applicable to male students..."

### Rule category D — Economic/income checks
- R-07: Declared annual income exceeds scheme ceiling (₹4.00 lakh) (RED) — "annual income below Rs. 4.00 lakh"
- R-08: Income certificate not issued by competent authority (VERIFY)

### Rule category E — Defect Guard upload requirements
- R-09: Document is unreadable or very low quality (AMBER)
- R-10: Uploaded document does not match its declared slot (AMBER)
- R-11: Unsupported file type or file too large (AMBER)

---

## 8. Defect Types

Findings are standardized around:
**BLOCKING, HIGH, MEDIUM, LOW, VERIFY**

- A **BLOCKING** or **HIGH** finding requires a documented MMNBA/application requirement, and sufficiently strong evidence that the uploaded information conflicts with that requirement.
- Use **VERIFY** for: ambiguous OCR, conflicting low-confidence evidence, requirements that require institutional confirmation, unclear document interpretation, or information that cannot safely be resolved automatically.

### Example Finding
HIGH: Student name mismatch
Identity document: RAHUL DAS
Academic document: RAHUL DASS
Why this was flagged: The student's name appears differently across two submitted documents.
Fix: Verify the correct spelling and ensure the application/supporting records use the correct name consistently.
Evidence: Identity document — page 1, Academic document — page 1
Confidence: 97%
Status: FIX

---

## 9. Application Snapshot

The snapshot contains fields supported by the scheme, masking sensitive info:
- **Student**: name, DOB, father's name, gender.
- **Academic**: institution.
- **Economic**: annual income.
- **Payment**: masked bank account, IFSC.

---

## 10. Readiness Score

The score is **Application Document Readiness**.
It is **NOT** a government eligibility score, probability of approval, probability of receiving financial assistance, or official MMNBA score.

---

## 11. AI Adjudication

AI adjudicates document evidence. Claude is responsible for document reasoning, not official scheme adjudication.
Claude may: compare names, interpret OCR variations, resolve formatting differences, classify FIX vs VERIFY.
Claude must NOT: invent MMNBA rules, invent eligibility criteria, declare official eligibility/rejection, override deterministic rules, fabricate evidence.

---

## 12. Scheme Configuration

Dedicated scheme configuration:
```yaml
scheme:
  id: NIJUT_BABU_2026
  name: Mukhya Mantrir Nijut Babu Aasoni
  short_name: Nijut Babu
  jurisdiction: Assam
  year: 2026
```

---

## 13. Demo Data

Synthetic MMNBA demo student. Fictional data only.
- Defect 1 — Name mismatch: RAHUL DAS (Aadhaar) vs RAHUL DASS (Marksheet).
- Defect 2 — Institution mismatch (VERIFY): Cotton University vs Gauhati University.
- Defect 3 — Income threshold breach: Income certificate shows ₹4,50,000 (Ceiling is ₹4.00 lakh).

---

## 14. Project Scope

**In scope**: one scheme (Nijut Babu), Assam, 2026 cycle, document upload, OCR/document extraction, structured Application Snapshot, deterministic MMNBA checks, AI adjudication for ambiguous evidence, ranked defects, readiness score, re-check, synthetic demo documents.
**Out of scope**: Nijut Moina, PMS-SC, multiple-scheme picker, generalized scholarship platform, official application submission, government approval decisions, benefit disbursement, automated appeals.

---

## 15. Definition of Done

- **Scheme**: MMNBA 2026 is the only active scheme. Scheme requirements are traceable to official Assam DHE material. PMS-SC assumptions have been removed.
- **Documents**: MMNBA MVP document roles defined. Extraction schemas exist. Evidence is stored.
- **Rules**: MMNBA-specific deterministic rules exist, sourced. Ambiguous requirements become VERIFY.
- **AI**: Adjudicates document evidence, cannot invent requirements, outputs evidence/confidence.
- **Product**: Application Snapshot, Defect report, readiness score, re-check work.
- **Demo**: Synthetic MMNBA student, synthetic documents, 3 meaningful findings, one successful replacement/re-check, deployed application.
