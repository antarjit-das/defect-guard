# Defect Guard — Nijut Babu Pre-Submission Checker

> **Mukhya Mantrir Nijut Babu Aasoni (MMNBA 2026-27)**  
> Cross-document consistency verification and defect prevention for scholarship applications.

Defect Guard checks a student's scholarship documents *before* final portal submission. It extracts information across all supporting documents independently, generates a cross-document **Application Snapshot**, evaluates deterministic scheme rules, adjudicates discrepancies, and provides a ranked **Defect Report** with a mathematically traceable **Application Document Readiness Score**.

---

## Operating Modes

Defect Guard supports two operating modes:

### 1. Demo Mock Mode (Default & Hackathon Recommended)
- **100% Offline & Deterministic**: Zero AWS credentials, Bedrock, Textract, or DynamoDB required.
- **Fast & Repeatable**: Simulates upload, extraction, check, and replacement in predictable time slices (~1.5s total).
- **Faithful Contracts**: Reuses the exact Pydantic-validated fixtures (`packet_checked.json`, `packet_rechecked.json`) and shared business logic.
- **Dual-Mode Landing Page**: The landing view provides a clean mode selection card with the Live AWS mode disabled (`BUILD IN PROGRESS — NOT DEMOABLE`).

### 2. Live AWS Cloud Mode
- Connects to Amazon API Gateway (HTTP API), Amazon Bedrock Nova 2 Lite structured outputs, Amazon Textract synchronous `AnalyzeDocument` (`QUERIES` + `FORMS`), and DynamoDB single-table storage (`DefectGuard`).
- Configured via `frontend/config.js` (`window.DEFECT_GUARD_MOCK = false`) or URL parameter `?mock=0`.

---

## Quick Start (Demo Mock Mode)

### Prerequisites
- Node.js (v18+) or Python (v3.10+) for serving static files.

### 1. Start the Local Server
```bash
npm run serve
```
*Alternatively:*
```bash
python -m http.server 3000 --directory frontend
```

### 2. Open in Browser
Visit:
```text
http://localhost:3000
```
or open `frontend/index.html` directly in Google Chrome.

### 3. Run the Demo Flow
1. Click **"Enter Demo Mode (Hackathon Evaluation)"** on the landing screen.
2. Click **"Quick-load Demo Pack"** (or drag and drop the synthetic specimen PDFs from `samples/demo-pack/`).
3. Click **"2. Run Defect Check"**.
   - Review the **Score: 40 / 100 [NOT READY]**.
   - Inspect the **Snapshot Matrix** (name mismatch highlighted).
   - Review the 3 defects: `[R-01] RED` (Name mismatch), `[R-07] RED` (Income ceiling breach: ₹4,50,000 > ₹4,00,000), `[R-04] AMBER` (Institution verification).
4. Click **"🔄 Replace with Compliant Income Cert"** (or upload `samples/demo-pack/Income 250k.pdf`).
5. Click **"3. Re-check Application (Updated Documents)"**.
   - Finding R-07 clears!
   - Score dynamically improves: **40 → 65 [RISKY]** (`100 - 25x1 red - 10x1 amber = 65`).

See [`docs/demo-script.md`](docs/demo-script.md) for the complete video recording script.

---

## Sample Document Pack (`samples/demo-pack/`)

The repository includes 5 synthetic specimen documents for demo student `Antarjit Das`:
- `Aadhar.pdf`: Aadhaar card (ANTARJIT DAS, Male, DOB 12/03/2004)
- `HS Marksheet.pdf`: Higher Secondary marksheet (ANTARJEET DASS — planted name variant)
- `Income 450k.pdf`: Revenue Circle income certificate (₹4,50,000 — breaches ₹4.00L ceiling)
- `Income 250k.pdf`: Compliant replacement income certificate (₹2,50,000 — within ceiling)
- `Bank Statement.pdf`: Bank statement/passbook (ANTARJIT DAS, SBI Dispur)

---

## Automated Verification & Testing

### 1. Verify Demo Mock Flow (Headless Node.js)
```bash
npm test
```
*Executes the complete student journey in Node.js, validating packet creation, upload progress, extraction completion, initial score 40, document replacement, re-check, and score improvement to 65.*

### 2. Validate Mock Fixtures Against Backend Pydantic Models
```bash
npm run test:fixtures
```
*Validates that `packet_checked.json`, `packet_extracting.json`, and `packet_rechecked.json` strictly adhere to the backend `Packet` Pydantic models.*

### 3. Run Complete Backend Test Suite
```bash
npm run test:backend
```
*Executes all 101 unit tests across rule engine, scoring, normalizers, and API handlers.*

### 4. Syntax & Static Build Verification
```bash
npm run build
```

---

## Architecture & File Structure

```
defect-guard/
├── frontend/
│   ├── config.js               # Runtime config (mock toggle & deterministic timings)
│   ├── fixtures/
│   │   ├── packet_checked.json       # Initial verdict (Score: 40, R-01, R-07, R-04)
│   │   ├── packet_extracting.json    # In-progress extraction fixture
│   │   └── packet_rechecked.json     # Post-replacement verdict (Score: 65, R-07 cleared)
│   ├── lib/
│   │   ├── types.js            # Shared domain contracts, Enums, roles
│   │   ├── mock-data.js        # Inlined Pydantic-verified fixture payloads
│   │   ├── mock.js             # Deterministic Mock State Machine (sessionStorage-backed)
│   │   └── api.js              # Universal API adapter (routes to Mock or AWS API Gateway)
│   └── index.html              # Presentation layer with dual-mode landing & studio UI
├── samples/
│   └── demo-pack/              # 5 synthetic specimen PDFs + expected.json
├── docs/
│   └── demo-script.md          # 3-minute video presentation script
├── scripts/
│   └── verify_mock.js          # Automated headless mock verification test
└── backend/                    # Pure-Python core rules, models, and serverless handlers
```

---

## License
MIT
