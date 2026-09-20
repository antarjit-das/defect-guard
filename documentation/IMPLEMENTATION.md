# IMPLEMENTATION.md — Defect Guard

**Status:** Final engineering plan. Source of truth for *how* and *when*.
**Companion document:** `PROJECT.md` (what and why). Read it first; this document does not restate the product.
**Audience:** Team Member A, Team Member B, and Antigravity (our AI implementation agent).
**Execution window:** 17 September 2026 (kickoff, setup only) → 20 September 2026 (submission).
**Region:** `ap-south-1` (Mumbai) for everything.

> **For Antigravity:** treat §2 (Architecture), §5 (Data Model), §6 (API Contract), §7 (AI Implementation) and §9 (Integration Contracts) as binding specifications. Do not invent endpoints, field names, table designs or AWS services beyond those listed. Do not add authentication, orchestration services, or extra database tables. When a detail is genuinely underspecified, follow the existing naming conventions and note the choice in the pull request description rather than changing an existing contract.

---

## 1. Implementation Goal

Build and deploy, inside the event window, a public web application where a student uploads five scholarship documents and receives — within about a minute — an Application Snapshot, a ranked list of likely defects with specific fixes, and a readiness score, with AWS doing the OCR, the reasoning, the storage and the hosting.

**The organising constraint:** a working vertical slice (one document → upload → Textract → Bedrock → rule → persisted verdict → rendered on screen) must exist by the end of **Friday 18 September**. Everything after that is breadth, polish, video and submission.

---

## 2. Architecture

### Text diagram

```
                         ┌──────────────────────────────────────────┐
                         │  Browser (phone or laptop)               │
                         │  Next.js 15 static export                │
                         └───────┬───────────────────────┬──────────┘
                                 │                       │
             (1) JSON API calls  │                       │  (2) PUT file bytes
                                 │                       │      directly to S3
                                 ▼                       ▼      (presigned URL,
                    ┌────────────────────────┐   ┌──────────────── 5 min TTL)
                    │  API Gateway (HTTP API)│   │  Amazon S3              │
                    │  CORS, throttle, /v1/* │   │  defect-guard-uploads   │
                    └───────────┬────────────┘   │  SSE-S3, BPA on,        │
                                │                │  lifecycle: expire 1 day│
            ┌───────────────────┼────────────────└──────────┬──────────────┘
            │                   │                           │
            ▼                   ▼                           │ read by
   ┌──────────────────┐ ┌──────────────────┐                │ Textract only
   │ fn_create_packet │ │ fn_create_upload │                │
   │ fn_get_packet    │ │ _url             │                │
   └────────┬─────────┘ └────────┬─────────┘                │
            │                    │                          │
            │   async invoke     │  async invoke            │
            │  (InvocationType   │  (InvocationType         │
            │      = Event)      │      = Event)            │
            ▼                    ▼                          │
   ┌──────────────────────┐  ┌─────────────────────┐        │
   │  fn_run_check        │  │ fn_extract_document │◀───────┘
   │  60 s timeout        │  │ 60 s timeout        │
   │                      │  │                     │
   │  1. build Snapshot   │  │ 1. Textract         │
   │  2. rule engine      │  │    AnalyzeDocument  │──────▶ ┌──────────────────┐
   │     (deterministic)  │  │    QUERIES + FORMS  │        │ Amazon Textract  │
   │  3. Bedrock          │  │ 2. Bedrock extract  │        │   (ap-south-1)   │
   │     adjudicate ──────┼──┼─── call ────────┐   │        └──────────────────┘
   │  4. validate JSON    │  │ 3. mask Aadhaar │   │
   │  5. score (Python)   │  │ 4. write DOC#   │   │        ┌──────────────────┐
   │  6. write VERDICT#   │  └─────────────────┼───┘        │ Amazon Bedrock   │
   └──────────┬───────────┘                    └───────────▶│ Claude 4.5 via   │
              │                                             │ global CRIS      │
              ▼                                             │ structured output│
   ┌─────────────────────────────────────────┐              └──────────────────┘
   │  Amazon DynamoDB — table "DefectGuard"  │
   │  PK = PACKET#<id>                       │
   │  SK = META | DOC#<id> | VERDICT#<ts>    │
   │  TTL = expiresAt (24 h)                 │
   └─────────────────────────────────────────┘

   Frontend hosting:  AWS Amplify Hosting  ← git push → GitHub repo (public)
   Logs:              CloudWatch Logs, 7-day retention, structured JSON lines
```

### Component responsibilities and boundaries

| Component | Owns | Must not |
|---|---|---|
| **Frontend (static)** | All rendering, upload orchestration, polling, clipboard export, client-side pre-upload warnings. | Contain any AWS SDK calls other than the presigned `PUT`; contain any business rule; compute the score. |
| **API Lambdas** (`create_packet`, `create_upload_url`, `get_packet`) | Request validation, DynamoDB reads/writes, presigned URL issuance, async invocation of workers. Must return in < 2 s. | Call Textract or Bedrock; handle file bytes. |
| **Worker Lambdas** (`extract_document`, `run_check`) | Everything slow: Textract, Bedrock, rule evaluation, scoring, persistence. Invoked asynchronously; never on the API request path. | Be invoked synchronously from API Gateway. |
| **`core/`** (pure Python, no AWS imports) | Normalization, snapshot construction, rule engine, scoring, masking, validators. | Import `boto3`. This is what makes it unit-testable offline and is the single most valuable parallelisation lever. |
| **`aws/`** | Thin clients over boto3 for S3, Textract, Bedrock, DynamoDB. | Contain business logic. |

### The two flows, end to end

**Document flow:** browser → presigned PUT → S3 object → frontend calls `POST /documents/{id}/uploaded` → API Lambda marks `UPLOADED` and async-invokes `fn_extract_document` → Textract `AnalyzeDocument` on the S3 object (QUERIES + FORMS) → Bedrock extraction call maps output to typed fields → Aadhaar/account masked → `DOC#` item written with `status = EXTRACTED` → frontend polling `GET /packets/{id}` sees it.

**Check flow:** frontend calls `POST /packets/{id}/check` → API Lambda sets `status = CHECKING`, async-invokes `fn_run_check` → snapshot built from all `DOC#` items → deterministic rule engine emits candidate findings → Bedrock adjudication call → response schema-validated and evidence-checked → surviving findings scored in Python → `VERDICT#<ts>` written and packet `status = CHECKED` → frontend polling sees the verdict.

### Why not the alternatives (recorded so nobody relitigates them mid-event)

- **S3 event notification instead of the explicit `/uploaded` call:** rejected. It saves one HTTP call but introduces a well-known SAM circular-dependency trap between a bucket and a function defined in the same template, hides the `role` metadata, and is harder to debug live. The explicit call is deterministic and costs the frontend nothing.
- **Step Functions for the pipeline:** rejected. There is no long-running, multi-branch, failure-prone orchestration here — two async Lambdas cover it.
- **Synchronous check via API Gateway:** rejected. Textract plus Bedrock will exceed the 30-second HTTP API integration limit on a five-document packet.
- **Next.js SSR on Amplify:** rejected. Static export removes an entire class of failure for a team new to AWS; the app is client-side anyway.

---

## 3. Technology Stack

| Layer | Choice | Version pinning notes |
|---|---|---|
| Frontend framework | **Next.js 15, App Router, TypeScript, `output: 'export'`** | Static export is mandatory, not optional. No `next/image` optimisation, no route handlers, no server actions. |
| Styling | **Tailwind CSS v4** | Already the fastest path to a clean responsive table. No component library beyond `lucide-react` for icons. |
| Frontend state | React `useState` + a single `usePacket(packetId)` polling hook | No Redux, no React Query, no websockets. |
| Backend runtime | **Python 3.13 Lambdas** | `boto3` ergonomics for Textract and Bedrock are materially better than Node's, and the samples are Python. **Pin `boto3 >= 1.40` in `requirements.txt`** — Bedrock structured outputs (`outputConfig.textFormat`) require a recent SDK and the Lambda-bundled boto3 may lag. Ship boto3 in the deployment package. |
| Validation | **Pydantic v2** | Schema validation of AI output and of API payloads, in one library. |
| Rule set format | **YAML** (`pyyaml`) | Human-readable and reviewable on camera. |
| Infrastructure as code | **AWS SAM** (`template.yaml` + `sam deploy --guided`) | One file for Lambda + HTTP API + DynamoDB + S3 + IAM role. Also gives `sam local` as the Build It contingency. |
| Hosting | **AWS Amplify Hosting** connected to the GitHub repo | Build command `npm run build`, output directory `out`. |
| AI | **Amazon Bedrock Converse API**, `global.anthropic.claude-sonnet-4-5-20250929-v1:0` | Global CRIS inference profile ID, not a base model ID. Cost/throttle swap: `global.anthropic.claude-haiku-4-5-20251001-v1:0`, changed via the `BEDROCK_MODEL_ID` environment variable only. |
| OCR | **Amazon Textract `AnalyzeDocument`**, `FeatureTypes = ["QUERIES", "FORMS"]` | Synchronous API. Inputs are single-page PDF/JPEG/PNG under our 5 MB cap, so no async job, no SNS, no polling of Textract. |
| Testing | `pytest` for `core/`; a `scripts/e2e.py` script for the deployed API | No test framework on the frontend. |

---

## 4. Repository Structure

```
defect-guard/
├── README.md                      # problem, build, where AWS fits, what we learned, AI tools used   # will stay in main, not in branch
├── .gitignore                     # includes samples/private/, .env*, .aws-sam/                      # will stay in main, not in branch
│
├── infra/
│   ├── template.yaml              # SAM: 5 Lambdas, HTTP API, DynamoDB, S3, 1 IAM role
│   └── samconfig.toml
│
├── backend/
│   ├── requirements.txt           # boto3>=1.40, pydantic>=2, pyyaml
│   ├── src/
│   │   ├── handlers/
│   │   │   ├── create_packet.py
│   │   │   ├── create_upload_url.py
│   │   │   ├── mark_uploaded.py
│   │   │   ├── run_check_api.py        # 202 + async invoke
│   │   │   ├── get_packet.py
│   │   │   ├── extract_document.py     # WORKER, async-invoked
│   │   │   └── run_check.py            # WORKER, async-invoked
│   │   ├── core/                       # PURE PYTHON — no boto3 imports, ever
│   │   │   ├── models.py               # Pydantic models = the contracts in §9
│   │   │   ├── fields.py               # field keys, per-role field sets, Textract queries
│   │   │   ├── normalize.py            # names, dates, money, IFSC, account numbers
│   │   │   ├── validators.py           # verhoeff(), ifsc_valid(), mime/size checks
│   │   │   ├── snapshot.py             # build_snapshot(extractions) -> Snapshot
│   │   │   ├── scoring.py              # score(findings) -> (int, band, arithmetic)
│   │   │   ├── masking.py              # mask_aadhaar(), mask_account()
│   │   │   └── rules/
│   │   │       ├── engine.py           # evaluate(snapshot, docs, ruleset) -> [Finding]
│   │   │       └── NIJUT_BABU_2026.yaml   # THE RULE SET — 11 rules with source citations
│   │   ├── aws/
│   │   │   ├── s3_client.py
│   │   │   ├── textract_client.py
│   │   │   ├── bedrock_client.py
│   │   │   └── ddb.py
│   │   └── ai/
│   │       ├── schemas.py              # JSON Schemas passed to Bedrock structured outputs
│   │       ├── extract.py              # prompt assembly + call + validation
│   │       └── adjudicate.py
│   └── tests/
│       ├── fixtures/
│       │   ├── textract_income_cert.json
│       │   ├── extractions_demo_packet.json
│       │   └── expected_findings_demo.json
│       ├── test_normalize.py
│       ├── test_validators.py
│       ├── test_rules.py               # the highest-value test in the repo
│       ├── test_scoring.py
│       └── test_ai_validation.py
│
├── frontend/
│   ├── next.config.ts                  # output: 'export'
│   ├── .env.example                    # NEXT_PUBLIC_API_BASE_URL
│   ├── app/
│   │   ├── page.tsx                    # landing + start check
│   │   └── p/[packetId]/page.tsx       # the whole product: upload, snapshot, findings
│   ├── components/
│   │   ├── UploadSlot.tsx
│   │   ├── SnapshotTable.tsx
│   │   ├── FindingCard.tsx
│   │   ├── ReadinessScore.tsx
│   │   └── FixListButton.tsx
│   ├── lib/
│   │   ├── api.ts                      # the only place that knows the API shape
│   │   ├── types.ts                    # generated by hand from §9 contracts
│   │   └── mock.ts                     # MOCK MODE: returns fixtures/packet_checked.json
│   └── fixtures/
│       ├── packet_extracting.json
│       └── packet_checked.json         # committed by A at T-002, used by B all of Friday
│
├── samples/
│   ├── generator/                      # HTML/CSS templates + render script
│   ├── demo-pack/                      # 5 synthetic documents + expected.json
│   ├── stress-pack/                    # messier variants for testing
│   └── README.md                       # states the synthetic-data policy
│
├── docs/
│   ├── architecture.txt                # the diagram from §2, for the video
│   └── demo-script.md
│
└── scripts/
    ├── e2e.py                          # hits the deployed API end to end
    └── grep_pii.sh                     # pre-submission check for 12-digit sequences
```

---

## 5. Data Model

### DynamoDB — single table `DefectGuard`

- **Partition key:** `pk` (String) — always `PACKET#<packetId>`
- **Sort key:** `sk` (String) — `META` | `DOC#<documentId>` | `VERDICT#<isoTimestamp>`
- **TTL attribute:** `expiresAt` (Number, epoch seconds) — set to `now + 86400` on every item written
- **Billing:** PAY_PER_REQUEST
- **No GSI. No Scan. Ever.**

#### Entity: `META`

| Attribute | Type | Notes |
|---|---|---|
| `pk` / `sk` | S | `PACKET#<uuid4>` / `META` |
| `packetId` | S | uuid4 |
| `schemeId` | S | `NIJUT_BABU_2026` |
| `status` | S | `DRAFT` \| `EXTRACTING` \| `READY_TO_CHECK` \| `CHECKING` \| `CHECKED` |
| `createdAt` / `updatedAt` | S | ISO 8601 UTC |
| `latestVerdictSk` | S | `VERDICT#<ts>` or absent |
| `previousScore` | N | the score before the most recent check, for the "40 → 50" display |
| `expiresAt` | N | TTL |

#### Entity: `DOC#<documentId>`

| Attribute | Type | Notes |
|---|---|---|
| `documentId` | S | uuid4 |
| `role` | S | `AADHAAR` \| `objectKey` | S | `packets/<packetId>/<documentId>.<ext>` |
| `fileName` | S | original name, sanitised |
| `contentType` | S | `application/pdf` \| `image/jpeg` \| `image/png` |
| `sizeBytes` | N | reported by the client at request time, re-read from S3 `head_object` at extraction time (authoritative) |
| `pageCount` | N | 1 unless Textract reports more |
| `status` | S | `PENDING_UPLOAD` \| `UPLOADED` \| `EXTRACTING` \| `EXTRACTED` \| `EXTRACTION_FAILED` |
| `supersededBy` | S | documentId of a replacement, if any — superseded docs are excluded from the snapshot |
| `extraction` | M | `DocumentExtraction` (see §9) — masked values only |
| `error` | S | short message when `EXTRACTION_FAILED` |
| `expiresAt` | N | TTL |

#### Entity: `VERDICT#<isoTimestamp>`

| Attribute | Type | Notes |
|---|---|---|
| `checkRunId` | S | uuid4 |
| `snapshot` | M | `Snapshot` (see §9) |
| `findings` | L | ordered list of `Finding` |
| `score` | N | 0–100 |
| `band` | S | `NOT_READY` \| `RISKY` \| `READY` |
| `scoreArithmetic` | S | e.g. `"100 − 25×1 red − 10×1 amber = 65"` |
| `ruleSetVersion` | S | `NIJUT_BABU_2026@1` |
| `modelId` | S | the Bedrock inference profile actually used |
| `aiStatus` | S | `OK` \| `FALLBACK_TEMPLATE` \| `FALLBACK_AFTER_INVALID_JSON` |
| `createdAt` | S | ISO 8601 |
| `expiresAt` | N | TTL |

### Access patterns

| # | Pattern | Operation |
|---|---|---|
| AP1 | Read packet metadata | `GetItem(pk, "META")` |
| AP2 | Read the whole packet for the UI | `Query(pk)` — returns META + all DOC# + all VERDICT#; the handler keeps only the newest verdict |
| AP3 | Create/replace a document | `PutItem` (DOC#), plus `UpdateItem` on the previously-current doc of that role setting `supersededBy` |
| AP4 | Store an extraction | `UpdateItem(pk, "DOC#<id>")` setting `extraction` and `status` |
| AP5 | Append a verdict | `PutItem` (VERDICT#) + `UpdateItem` on META setting `latestVerdictSk`, `previousScore`, `status` |

### S3

- Bucket `defect-guard-uploads-<accountId>`, region `ap-south-1`.
- Block Public Access: **all four settings on.** No bucket policy granting public access.
- Encryption: SSE-S3 (`AES256`), enabled by default.
- Lifecycle rule `expire-uploads`: expire current versions **1 day** after creation. Versioning off.
- CORS: `AllowedOrigins` = the Amplify domain plus `http://localhost:3000`; `AllowedMethods` = `PUT`, `GET`; `AllowedHeaders` = `*`; `MaxAge` = 3000.
- Key layout: `packets/<packetId>/<documentId>.<ext>`.

---

## 6. API Contract

Base path: `https://<api-id>.execute-api.ap-south-1.amazonaws.com/v1`
All request and response bodies are JSON. All errors use the shape `{"error": {"code": "...", "message": "..."}}`.

### 6.1 `POST /packets`
- **Purpose:** start a new check.
- **Input:** `{}` (scheme is fixed server-side in the MVP).
- **Output 201:** `{"packetId": "...", "schemeId": "NIJUT_BABU_2026", "status": "DRAFT", "createdAt": "..."}`
- **Errors:** 500 `INTERNAL`.

### 6.2 `POST /packets/{packetId}/documents`
- **Purpose:** register a document and get a presigned upload URL. Re-registering an existing role supersedes the previous document.
- **Input:** `{"role": "INCOME_CERTIFICATE", "fileName": "income.pdf", "contentType": "application/pdf", "sizeBytes": 184320}`
- **Output 201:** `{"documentId": "...", "uploadUrl": "https://...", "expiresInSeconds": 300, "objectKey": "packets/.../....pdf"}`
- **Rules:** `contentType` must be in `{application/pdf, image/jpeg, image/png}`; `sizeBytes` ≤ 5 242 880; `role` must be a known role.
- **Errors:** 400 `UNSUPPORTED_TYPE`, 400 `FILE_TOO_LARGE`, 400 `UNKNOWN_ROLE`, 404 `PACKET_NOT_FOUND`.

### 6.3 `POST /packets/{packetId}/documents/{documentId}/uploaded`
- **Purpose:** tell the backend the bytes have landed; start extraction.
- **Input:** `{}`
- **Output 202:** `{"documentId": "...", "status": "EXTRACTING"}`
- **Behaviour:** sets `status = EXTRACTING`, sets packet `status = EXTRACTING`, async-invokes `fn_extract_document` with `{packetId, documentId}`.
- **Errors:** 404 `DOCUMENT_NOT_FOUND`, 409 `OBJECT_MISSING` (S3 `head_object` fails — the upload did not actually complete).

### 6.4 `POST /packets/{packetId}/check`
- **Purpose:** run the defect check.
- **Input:** `{}`
- **Output 202:** `{"checkRunId": "...", "status": "CHECKING"}`
- **Behaviour:** requires ≥ 3 documents with `status = EXTRACTED`; sets packet `status = CHECKING`; async-invokes `fn_run_check`.
- **Errors:** 409 `NOT_ENOUGH_DOCUMENTS` (with `{"extracted": n, "required": 3}`), 409 `ALREADY_RUNNING`, 404 `PACKET_NOT_FOUND`.

### 6.5 `GET /packets/{packetId}`
- **Purpose:** the single read endpoint. The frontend polls this every 2 seconds while any status is in progress, and stops when `status ∈ {READY_TO_CHECK, CHECKED}` or after 90 seconds.
- **Output 200:**
```json
{
  "packetId": "…", "schemeId": "NIJUT_BABU_2026", "status": "CHECKED",
  "createdAt": "…", "updatedAt": "…",
  "documents": [
    { "documentId": "…", "role": "AADHAAR", "fileName": "aadhaar.jpg",
      "contentType": "image/jpeg", "sizeBytes": 152340, "pageCount": 1,
      "status": "EXTRACTED",
      "extraction": { "roleConfirmed": true, "documentQuality": "GOOD",
        "fields": [ { "fieldKey": "student_name", "rawValue": "ANTARJIT DAS",
                      "normalizedValue": "antarjit das", "confidence": 0.97,
                      "evidence": "Name / नाम  ANTARJIT DAS", "source": "TEXTRACT_QUERY",
                      "needsConfirmation": false } ] } }
  ],
  "verdict": {
    "checkRunId": "…", "createdAt": "…",
    "snapshot": { "rows": [ { "fieldKey": "student_name", "label": "Student name",
        "valuesByRole": { "AADHAAR": "ANTARJIT DAS", "MARKSHEET": "ANTARJEET DASS" },
        "canonicalValue": "ANTARJIT DAS", "canonicalSource": "AADHAAR",
        "hasDisagreement": true } ] },
    "findings": [ { "findingId": "f1", "ruleId": "R-01", "title": "Student name differs across documents",
        "severity": "RED", "category": "IDENTITY",
        "documents": [ { "role": "AADHAAR", "value": "ANTARJIT DAS" },
                       { "role": "MARKSHEET", "value": "ANTARJEET DASS" } ],
        "reason": "…", "fixInstruction": "…", "confidence": 0.92,
        "source": "NSP FAQ Q17 — verification checks form particulars against enclosed documents" } ],
    "score": 40, "band": "NOT_READY",
    "scoreArithmetic": "100 − 25×2 red − 10×1 amber = 40",
    "ruleSetVersion": "NIJUT_BABU_2026@1", "modelId": "global.anthropic…", "aiStatus": "OK"
  },
  "previousScore": null
}
```
- **Errors:** 404 `PACKET_NOT_FOUND`.

**No other endpoints are to be built.** In particular: no DELETE (replacement is a re-POST to `/documents`), no list-packets, no admin routes, no health endpoint beyond what API Gateway provides.

---

## 7. AI Implementation

### Model and invocation

- **Runtime client:** `boto3.client("bedrock-runtime", region_name="ap-south-1")`.
- **Model ID:** the environment variable `BEDROCK_MODEL_ID`, defaulting to `global.anthropic.claude-sonnet-4-5-20250929-v1:0`. This is a **Global cross-Region inference profile ID**, not a base model ID — using the base ID is the single most common day-one failure in `ap-south-1` ([AWS blog](https://aws.amazon.com/blogs/machine-learning/access-anthropic-claude-models-in-india-on-amazon-bedrock-with-global-cross-region-inference/)).
- **API:** `converse()` with `outputConfig.textFormat` set to a JSON Schema (Bedrock structured outputs, GA February 2026, [docs](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html)). Note that the schema is passed as a **JSON string** under `outputConfig.textFormat.structure.jsonSchema.schema` and a `name` field is required.
- **Inference config:** `temperature = 0`, `maxTokens = 2000` (extraction) / `3000` (adjudication).
- **IAM:** the Lambda role needs `bedrock:InvokeModel` on both the inference-profile ARN and the underlying foundation-model ARNs across regions, per the Global CRIS IAM guidance. If the policy is fiddly, use `Resource: "*"` for `bedrock:InvokeModel` during the event and say so in the README — this is a demo account with a $100 ceiling.

### Call 1 — Extraction (one per document)

- **System message (short):** you extract fields from Indian government documents; you only report what the text supports; you never guess.
- **User message contains:** the document `role`; the expected field list with descriptions; the Textract payload — query answers, form key-value pairs, and the first 4 000 characters of raw `LINE` text.
- **Output schema:**
```json
{
  "type": "object",
  "properties": {
    "roleConfirmed": {"type": "boolean"},
    "documentQuality": {"type": "string", "enum": ["GOOD", "POOR"]},
    "fields": {"type": "array", "items": {
      "type": "object",
      "properties": {
        "fieldKey": {"type": "string"},
        "rawValue": {"type": ["string", "null"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "evidence": {"type": ["string", "null"]}
      },
      "required": ["fieldKey", "rawValue", "confidence", "evidence"],
      "additionalProperties": false}},
    "notes": {"type": ["string", "null"]}
  },
  "required": ["roleConfirmed", "documentQuality", "fields"],
  "additionalProperties": false
}
```
- **Post-call deterministic work (in `core/`, not the model):** normalize every `rawValue` into `normalizedValue`; mask Aadhaar and account numbers; set `needsConfirmation = confidence < 0.55`; drop any `fieldKey` not in the role's schema.

### Call 2 — Adjudication (one per check run)

- **Input:** the snapshot rows (masked), the candidate findings with rule metadata and severity, and the evidence snippet for each participating value.
- **Asked for, per finding:** whether an identity-type conflict is real (`isRealConflict`), a confidence, a two-sentence `reason` written for a student, a one-action `fixInstruction` naming a specific document, and a `rankHint`.
- **The prompt frames the judgement explicitly:** *"Would an NSP institute nodal officer, comparing the form entry to this document, treat these as the same person?"* with two worked positive examples (case/spacing differences, common transliteration variants) and two worked negative examples (different given name, different father's name).
- **Output schema:**
```json
{
  "type": "object",
  "properties": {
    "results": {"type": "array", "items": {
      "type": "object",
      "properties": {
        "findingId": {"type": "string"},
        "isRealConflict": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string", "maxLength": 320},
        "fixInstruction": {"type": "string", "maxLength": 320},
        "rankHint": {"type": "integer", "minimum": 1}
      },
      "required": ["findingId", "isRealConflict", "confidence", "reason", "fixInstruction", "rankHint"],
      "additionalProperties": false}}
  },
  "required": ["results"],
  "additionalProperties": false
}
```

### Deterministic guard rails around the model (all in `ai/validation.py`)

1. **Schema validation** with Pydantic. Failure → one retry with `"Your previous response did not match the schema. Return only valid JSON matching it."` → then fallback.
2. **Finding-ID check:** any `findingId` not produced by the rule engine is discarded. The model cannot add findings.
3. **Evidence grounding:** every quoted value in `reason` and `fixInstruction` that looks like a field value must appear in the extraction payload for that packet. Implemented as a substring check over the set of raw and normalized values. Violations → that finding falls back to template text.
4. **Severity lock:** severity comes from the rule set. `isRealConflict = false` may only *downgrade* — RED identity findings (R-01, R-02, R-06) become AMBER with "we could not be certain"; they are never removed. Non-identity rules ignore `isRealConflict` entirely.
5. **Confidence cap:** `confidence < 0.6` forces AMBER and prefixes the reason with "We could not be certain, so please check:".
6. **The score never touches the model.** `core/scoring.py` computes it from the final finding list.

### Failure handling

| Failure | Behaviour |
|---|---|
| Bedrock throttling (`ThrottlingException`) | Exponential backoff, 3 attempts (1 s, 3 s, 7 s). Then fallback. |
| Access denied / model not enabled | Fail fast with a clear log line naming the model ID; `aiStatus = FALLBACK_TEMPLATE`; the verdict still renders with template reasons and fixes. |
| Invalid JSON after retry | `aiStatus = FALLBACK_AFTER_INVALID_JSON`; template text. |
| Extraction call fails for one document | That document is `EXTRACTION_FAILED`; the check still runs on the others; an INFO finding says which document could not be read. |
| Timeout | Lambda timeout is 60 s; the client-side poll gives up at 90 s and shows a Retry button that re-issues `POST /check`. |

**Template fallback text exists for all 11 rules** in `rules/NIJUT_BABU_2026.yaml` under each rule's `defaultReason` and `defaultFix`. This is written on Friday, before Bedrock is wired in — which is also what lets the frontend show real content on Friday.

---

## 8. Document Processing

The exact path of one document, with the field sets.

### 8.1 Upload
Client pre-check (warn, do not block): type in the allow-list, size ≤ 5 MB, and a soft warning above 200 KB — *"NSP accepts only 200 KB; we'll flag this."* Then `POST /documents` → presigned `PUT` (5-minute expiry, `ContentType` bound into the signature) → browser uploads → `POST /documents/{id}/uploaded`.

### 8.2 S3
Object lands at `packets/<packetId>/<documentId>.<ext>`. `fn_extract_document` calls `head_object` first: this confirms the upload really completed and gives the **authoritative** `ContentLength` and `ContentType` used by rules R-08 and R-13 (never trust the client's reported size).

### 8.3 Textract
`analyze_document(Document={"S3Object": {...}}, FeatureTypes=["QUERIES","FORMS"], QueriesConfig={"Queries":[...]})` with **role-specific queries** (max 15 per call, keep to ~8):

| Role | Textract queries | Field keys produced |
|---|---|---|
| `AADHAAR` | "What is the name?", "What is the date of birth?", "What is the Aadhaar number?", "What is the gender?" | `student_name`, `dob`, `aadhaar_number`, `gender` |
| `INCOME_CERTIFICATE` | "Whose income is certified?", "What is the annual income?", "What is the date of issue?", "Which authority issued this certificate?", "What is the certificate number?" | `parent_name`, `annual_income`, `income_cert_date`, `income_cert_authority`, `income_cert_no` |
| `MARKSHEET` | "What is the student's name?", "What is the father's name?", "What is the roll number?", "Which board or university issued this?", "What is the year of passing?", "What is the percentage or CGPA?" | `student_name`, `father_name`, `roll_no`, `board_or_university`, `passing_year`, `previous_percentage` |
| `BANK_PROOF` | "What is the account holder's name?", "What is the account number?", "What is the IFSC code?", "What is the bank and branch name?" | `account_holder_name`, `bank_account_number`, `ifsc`, `bank_branch` |

Also retained from the response: all `KEY_VALUE_SET` pairs, all `LINE` blocks with confidence, and the mean block confidence (feeds `documentQuality` and R-13).

### 8.4 Extraction (Bedrock call 1)
As specified in §7. Produces raw values with confidence and evidence.

### 8.5 Normalization (deterministic, `core/normalize.py`)
- **Names:** trim, collapse whitespace, upper→title handling, strip `Shri/Smt/Mr/Ms/Kum/S/o/D/o`, strip punctuation except internal hyphens, produce `normalizedValue` (lower-case, single-spaced) and a `tokens` list for comparison.
- **Dates:** accept `DD/MM/YYYY`, `DD-MM-YYYY`, `DD.MM.YYYY`, `D MMM YYYY`, `YYYY-MM-DD`, two-digit years (pivot at 40). Output ISO `YYYY-MM-DD`. Ambiguous or unparseable → `null` with a note.
- **Money:** strip `₹`, `Rs.`, `/-`, commas; expand `2.6 Lakh`/`2,60,000`/`Two Lakh Sixty Thousand` (digits only for the last case — if words, mark `needsConfirmation`). Output integer rupees.
- **IFSC:** upper-case, strip spaces.
- **Account number:** digits only.
- **Aadhaar:** digits only, then immediately masked — only the last 4 digits and a `verhoeffValid` boolean are retained.

### 8.6 Rule checking (deterministic, `core/rules/engine.py`)
Loads `NIJUT_BABU_2026.yaml`. Rule entry shape:

```yaml
version: 1
scheme:
  id: NIJUT_BABU_2026
  name: Mukhya Mantrir Nijut Babu Aasoni (AY 2026-27)
  incomeCeiling: 250000
  mandatoryRoles: [AADHAAR, INCOME_CERTIFICATE, MARKSHEET, BANK_PROOF]
  maxFileBytes: 204800
  allowedMimeTypes: [application/pdf, image/jpeg]
rules:
  - id: R-04
    title: Declared annual income exceeds the scheme ceiling
    severity: RED
    category: ELIGIBILITY
    kind: DETERMINISTIC
    inspects: [annual_income]
    source: "MMNBA scheme guidelines, Means Test — ceiling ₹4,00,000 p.a."
    sourceUrl: "https://sje.rajasthan.gov.in/Schemes/sc%20pms.pdf"
    defaultReason: "Your income certificate shows {annual_income}, which is above this scheme's ceiling of {incomeCeiling}."
    defaultFix: "Check the income certificate figure. If it is correct, this scheme's income ceiling is exceeded and you should speak to your institute's nodal officer about other schemes before submitting."
```

The engine emits `Finding` objects with stable `findingId`s (`f1`, `f2`, … in rule order) and sets `needsAdjudication: true` for R-01, R-02, R-06, R-09 and R-12. Merge step: if both R-01 and R-06 fire on the same name pair, keep R-01 and fold R-06's documents into it.

### 8.7 Bedrock reasoning (call 2)
As specified in §7, followed by the six guard rails.

### 8.8 Scoring and persistence
`score = max(0, 100 − 25×REDs − 10×AMBERs)`, band from the thresholds in `PROJECT.md` §8/F6, `scoreArithmetic` rendered as a string. `VERDICT#` written; META updated with `latestVerdictSk`, `previousScore` (the prior verdict's score, or `null`), `status = CHECKED`.

### 8.9 Display
The frontend's polling hook sees `status = CHECKED`, stops polling, and renders snapshot → findings → score. Rows with `hasDisagreement` are highlighted; findings are shown in the order returned (already sorted).

---

## 9. Integration Contracts

**These are agreed and committed in the first two hours (T-002) and are frozen. If a change is genuinely required, it is announced verbally, changed in `core/models.py` and `frontend/lib/types.ts` together, and the mock fixture is regenerated in the same commit.** Nothing else is allowed to break across the A/B boundary.

### C1 — Field keys (the shared vocabulary)
`student_name`, `father_name`, `parent_name`, `dob`, `gender`, `aadhaar_last4`, `annual_income`, `income_cert_date`, `income_cert_authority`, `income_cert_no`, `institution_name`, `admission_year`, `fee_waiver_status`, `bank_account_number`, `ifsc`, `account_holder_name`, `bank_branch`, `roll_no`, `board_or_university`, `passing_year`, `previous_percentage`.
Display labels live in **one** place: `frontend/lib/types.ts` → `FIELD_LABELS`.

### C2 — Roles
`AADHAAR`, `INCOME_CERTIFICATE`, `MARKSHEET`, `BANK_PROOF`. Order of display is that order.

### C3 — Enumerations
- `Packet.status`: `DRAFT | EXTRACTING | READY_TO_CHECK | CHECKING | CHECKED`
- `Document.status`: `PENDING_UPLOAD | UPLOADED | EXTRACTING | EXTRACTED | EXTRACTION_FAILED`
- `Finding.severity`: `RED | AMBER | INFO`
- `Finding.category`: `IDENTITY | ELIGIBILITY | BANK | DOCUMENT_FORMAT | COMPLETENESS | QUALITY`
- `Verdict.band`: `NOT_READY | RISKY | READY`
- `Verdict.aiStatus`: `OK | FALLBACK_TEMPLATE | FALLBACK_AFTER_INVALID_JSON`

### C4 — Object shapes
`DocumentExtraction`, `Snapshot`, `Finding`, `Verdict` and the full `GET /packets/{id}` envelope are exactly as printed in §6.5. That JSON block **is** the contract; `frontend/fixtures/packet_checked.json` is a valid instance of it.

### C5 — API contract
The five endpoints in §6, with those exact paths, methods, status codes and error codes.

### C6 — The mock fixture (the parallelism lever)
`frontend/fixtures/packet_checked.json` and `packet_extracting.json` are committed by Team Member A within the first two hours, before any backend exists. `frontend/lib/api.ts` reads `NEXT_PUBLIC_MOCK=1` and returns the fixtures with a 600 ms delay. **Team Member B builds the entire UI against these and does not wait for the backend.** Switching to the real API is a one-line environment-variable change.

### C7 — Environment variables
- Frontend: `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_MOCK`
- Backend: `TABLE_NAME`, `BUCKET_NAME`, `BEDROCK_MODEL_ID`, `EXTRACT_FUNCTION_NAME`, `CHECK_FUNCTION_NAME`, `RULESET_ID`, `LOG_LEVEL`

---

## 10. Development Phases

Effort assumption: **~4–5 hours per person per day.** Roles per `PROJECT.md` §16/A1 — **A = Antarjit Das** (backend, AWS, rules, AI); **B** (frontend, UX, video, writeup).

---

### DAY 0 — Wednesday 17 September (kickoff day, evening, ~2 hours each)

**Primary goal:** the repository exists, the contracts exist, both people can deploy a trivial thing to AWS, and Bedrock answers a call.

**Critical path:** AWS account usable → Bedrock model access → contracts committed.

**Team Member A**
- T-001 Create the public GitHub repo **after kickoff**, with `README.md`, `PROJECT.md`, `IMPLEMENTATION.md`, `.gitignore`. First commit timestamp must sit inside the event window.
- T-003 Confirm AWS account and the $100 credit; set a billing alarm at $20; **enable Bedrock model access in `ap-south-1`** and run one successful `converse()` call against `global.anthropic.claude-sonnet-4-5-20250929-v1:0` from a local script. Paste the output into the team chat.
- T-002 Write `core/models.py` (Pydantic) and both frontend fixtures; commit. **This unblocks B for the next 24 hours.**

**Team Member B**
- T-004 `npx create-next-app` with TypeScript and Tailwind, set `output: 'export'`, commit, connect the repo to **Amplify Hosting**, and get a live URL showing "Defect Guard — coming Friday". Record the URL in the README.
- T-005 Set up the recording pipeline: screen recorder tested, mic tested, a 3-minute timeline skeleton with placeholder sections in the editor.

**Integration checkpoint (end of evening, 15 minutes):** A demonstrates the Bedrock response; B demonstrates the live Amplify URL; both confirm `packet_checked.json` renders as valid JSON in the frontend's console.

**End-of-day acceptance:** public repo with the two planning docs and the contracts; a live Amplify URL; one proven Bedrock call.

**Cut if behind:** T-005 moves to Friday. Nothing else.

---

### DAY 1 — Friday 18 September

**Primary goal:** a working vertical slice — one real document goes upload → S3 → Textract → Bedrock → rule → DynamoDB → visible in the UI.

**Critical path:** `template.yaml` deploys → presigned upload works → `fn_extract_document` returns fields for one role → `GET /packets/{id}` serves them → frontend renders them.

**Team Member A (critical path, in this order)**
- T-006 SAM `template.yaml`: DynamoDB table, S3 bucket (BPA, SSE, lifecycle, CORS), HTTP API, five Lambdas, **one shared execution role** with S3 read/write on the bucket prefix, DynamoDB CRUD on the table, `textract:AnalyzeDocument`, `bedrock:InvokeModel`, `lambda:InvokeFunction` on the two workers. `sam deploy` succeeds.
- T-007 `create_packet`, `create_upload_url`, `mark_uploaded`, `get_packet` handlers + `ddb.py` + `s3_client.py`. Curl-testable.
- T-008 `textract_client.py` with the `INCOME_CERTIFICATE` query set; save one real response to `tests/fixtures/textract_income_cert.json`.
- T-009 `ai/extract.py`: Bedrock structured-output extraction for `INCOME_CERTIFICATE`; wire `fn_extract_document` end to end; document reaches `EXTRACTED` with real fields.
- T-010 `core/normalize.py` + `core/validators.py` (verhoeff, IFSC regex, money, dates) with unit tests.
- T-011 Rule set YAML skeleton with R-04, R-07, R-08 implemented; `core/rules/engine.py` returns findings for a fixture snapshot; `test_rules.py` green.

**Team Member B (fully parallel, zero dependency on A after T-002)**
- T-012 Design pass: type scale, colour tokens including the three severity colours (each paired with a word), 360 px layout sketch for the packet page. 45 minutes, no longer.
- T-013 `lib/api.ts` + `lib/types.ts` + mock mode from the committed fixtures.
- T-014 Landing page and "Start check" flow; route to `/p/[packetId]`.
- T-015 `UploadSlot` ×5 with client-side pre-checks, progress, and the per-document status chip; presigned-PUT upload function written against the contract (testable against A's API as soon as T-007 lands).
- T-016 `SnapshotTable` rendering the mock snapshot, with disagreement highlighting, horizontally scrollable inside its own container at 360 px.
- T-017 `FindingCard` and `ReadinessScore` rendering the mock verdict.

**Integration checkpoints**
- **Midday:** A publishes the deployed API base URL. B switches `NEXT_PUBLIC_MOCK=0` for the upload flow only and confirms a real file lands in S3. This is the first and most important integration.
- **Evening:** B points the whole app at the real API; A's single-role extraction shows up in B's UI.

**End-of-day acceptance (the day's real test):**
> Upload one income certificate on the deployed frontend → it appears in S3 → extraction completes → `GET /packets/{id}` returns real extracted fields → the UI displays them, and at least one rule (R-04 or R-08) fires correctly.

**Cut if behind:** drop R-07 and R-08 to Saturday; run the frontend from `localhost` against the deployed API rather than debugging Amplify; leave the snapshot table unstyled. **Do not cut the Bedrock extraction call** — it is the slice.

---

### DAY 2 — Saturday 19 September

**Primary goal:** the complete MVP. All four roles, all eleven rules, adjudication, scoring, the re-check loop, real demo documents, deployed and polished.

**Critical path:** four-role extraction → full rule set → adjudication call + guard rails → scoring → verdict rendered → demo pack produces the intended three findings.

**Team Member A**
- T-018 Extraction for the remaining three roles: query sets, field schemas, per-role prompt sections. (Highest-value block of the day — do it first.)
- T-019 `core/snapshot.py`: canonical-value precedence, disagreement detection using normalized values.
- T-020 Remaining rules R-01, R-02, R-03, R-05, R-06, R-09 to R-14, with `defaultReason`/`defaultFix` for every rule and a `sourceUrl` for every rule.
- T-021 `ai/adjudicate.py` + all six guard rails in `ai/validation.py` + `test_ai_validation.py`.
- T-022 `core/scoring.py` and the verdict-writing path; `previousScore` handling for the re-check display.
- T-023 Replacement and re-check: re-POST to `/documents` supersedes; `POST /check` produces a new verdict.
- T-024 Structured logging (`packetId`, stage, duration, outcome) and CloudWatch retention set to 7 days.

**Team Member B**
- T-025 **Build the demo pack** (critical, and B's most important task of the day): five synthetic documents as HTML/CSS → PDF/JPEG, each watermarked `SPECIMEN — NOT A REAL DOCUMENT`, sized ≤ 200 KB except the income certificate which is deliberately ~900 KB. Planted defects: surname spelled two ways between Aadhaar and marksheet; income ₹2,60,000 against a ₹4,00,000 ceiling; the oversized file. Plus a compliant replacement income certificate for the re-check beat. Commit with `expected.json`.
- T-026 Wire the polling hook to the real API; handle every status including `EXTRACTION_FAILED`.
- T-027 Re-check UI: replace-document affordance, "Re-check" button, the `40 → 50` score transition.
- T-028 `FixListButton` clipboard export including the "Values to type into NSP" section.
- T-029 Visual polish pass: empty states, loading skeletons, error states with retry, the standing advisory line near the score, 360 px verification on a real phone.
- T-030 Write `docs/demo-script.md` — shot list with timings from `PROJECT.md` §14 — and draft the README sections.

**Integration checkpoints**
- **Midday:** four-role extraction meets the real demo pack. Expect this to surface extraction bugs; budget for it.
- **Late afternoon:** full run on the deployed URL produces the three intended findings with the right severities. **This is the go/no-go moment for the demo.**
- **Evening:** both members run the demo pack independently, from cold, and compare outputs.

**End-of-day acceptance:**
> On the deployed URL: five demo documents upload, all extract, the check produces exactly the three planted findings with correct severities and specific fixes, the score reads 40, replacing the income certificate and re-checking clears one finding and moves the score. Run twice.

**Cut if behind, in this order:** (1) T-028 fix-list export; (2) rules R-11, R-12, R-14; (3) T-027 re-check loop — if this goes, the video loses its second beat, so cut it only to save the first; (4) the stress pack.

---

### DAY 3 — Sunday 20 September

**Primary goal:** freeze, verify, record, write, submit — with the submission in by **12:00 IST**.

**Critical path:** feature freeze → final smoke test → video recorded → README/writeup → submitted.

**Morning — both**
- T-031 **Feature freeze at 08:00.** After this, only bug fixes that break the demo path.
- T-032 (A) Final smoke test per §13.5: two cold end-to-end runs, `scripts/e2e.py` green, CloudWatch clean of errors.
- T-033 (A) `scripts/grep_pii.sh` over the repo: no 12-digit sequences, no `.env`, no real documents, no AWS keys. Check git history, not just the working tree.
- T-034 (B) **Record the demo video** against `docs/demo-script.md`. Multiple takes of the upload sequence; assemble; hard-check the 3:00 limit; confirm no personal data is visible in any frame including tab titles and notifications.
- T-035 (A) README completion: problem, build, where AWS fits (with the architecture diagram), what we learned, AI coding tools used (Antigravity and any others, named as the rules require), synthetic-data policy, known limitations.

**Afternoon — both**
- T-036 **Submit by 12:00 IST**: public repo URL, video link, writeup. Then keep improving and resubmit only if the form permits it.
- T-037 (optional) Publish the build-notes blog on AWS Builder Center and link it in the submission (Top 5 Blogs prize).
- T-038 (optional, only if everything above is done) Hindi labels on the snapshot rows; a second demo packet.

**End-of-day acceptance:** submission confirmed, repository public, video under three minutes and accessible without login, deployed URL live.

**Cut if behind:** T-037 and T-038 without hesitation. If the video and the writeup collide, the **video wins** — it is the judging surface.

---

## 11. Detailed Task Plan

**Priority key:** ⬛ Critical (on the critical path — the MVP fails without it) · ◼ Important (MVP is diminished without it) · ◻ Optional (drop freely).

| ID | Owner | Day | Task | Depends on | Deliverable | Acceptance criteria | Priority |
|---|---|---|---|---|---|---|---|
| T-001 | A | 0 | Create public repo after kickoff | — | Repo with docs, `.gitignore` | First commit timestamped inside the event window; repo is public | ⬛ |
| T-002 | A | 0 | Contracts: `core/models.py` + both frontend fixtures | T-001 | Pydantic models, `packet_checked.json`, `packet_extracting.json` | Fixtures validate against the models; B can render them | ⬛ |
| T-003 | A | 0 | AWS account, credit, billing alarm, Bedrock access | — | One successful `converse()` output pasted in chat | Response received in `ap-south-1` using the global CRIS profile ID | ⬛ |
| T-004 | B | 0 | Next.js static export + Amplify Hosting | T-001 | Live HTTPS URL | Placeholder page loads over HTTPS from the Amplify domain | ⬛ |
| T-005 | B | 0 | Recording pipeline ready | — | Tested recorder, mic, editor skeleton | A 30-second test clip records and exports cleanly | ◼ |
| T-006 | A | 1 | SAM template: DynamoDB, S3, HTTP API, 5 Lambdas, 1 role | T-003 | `infra/template.yaml`, deployed stack | `sam deploy` succeeds; API base URL returned; bucket has BPA on and a 1-day lifecycle | ⬛ |
| T-007 | A | 1 | API handlers: create packet, upload URL, mark uploaded, get packet | T-006, T-002 | Four working endpoints | curl creates a packet, gets a presigned URL, uploads a file, reads it back | ⬛ |
| T-008 | A | 1 | Textract client + income-certificate query set | T-006 | `textract_client.py`, saved response fixture | Returns query answers for a real income certificate image | ⬛ |
| T-009 | A | 1 | Bedrock extraction for one role, wired into the worker | T-008, T-003 | `ai/extract.py`, `fn_extract_document` | Document reaches `EXTRACTED` with ≥4 correct fields | ⬛ |
| T-010 | A | 1 | Normalizers + validators with unit tests | T-002 | `normalize.py`, `validators.py`, tests | `pytest` green; Verhoeff and IFSC cases pass | ⬛ |
| T-011 | A | 1 | Rule engine + first 3 rules | T-010 | `engine.py`, `NIJUT_BABU_2026.yaml` | Fixture snapshot produces exactly the expected finding IDs | ⬛ |
| T-012 | B | 1 | Design tokens and 360 px layout sketch | — | Tailwind theme, sketch | Three severity styles, each paired with a word, not colour alone | ◼ |
| T-013 | B | 1 | API client, types, mock mode | T-002 | `api.ts`, `types.ts`, `mock.ts` | App renders a full verdict with `NEXT_PUBLIC_MOCK=1` and no backend | ⬛ |
| T-014 | B | 1 | Landing + start-check flow | T-013 | `app/page.tsx`, routing | Clicking Start navigates to `/p/<id>` | ⬛ |
| T-015 | B | 1 | Upload slots with presigned PUT | T-013, T-007 | `UploadSlot.tsx` | A real file reaches S3 from the browser; oversized/wrong-type files warn correctly | ⬛ |
| T-016 | B | 1 | Snapshot table | T-013 | `SnapshotTable.tsx` | Renders the mock snapshot; disagreements highlighted; no page-level horizontal scroll at 360 px | ⬛ |
| T-017 | B | 1 | Finding cards + score display | T-013 | `FindingCard.tsx`, `ReadinessScore.tsx` | Renders the mock verdict including `scoreArithmetic` | ⬛ |
| T-018 | A | 2 | Extraction for the remaining three roles | T-009 | Query sets + field schemas for all roles | Each demo document yields ≥80 % of its expected fields | ⬛ |
| T-019 | A | 2 | Snapshot builder with canonical precedence | T-018 | `snapshot.py` | Name row shows both spellings; canonical equals the Aadhaar value | ⬛ |
| T-020 | A | 2 | Remaining 8 rules with sources and default text | T-011 | Complete `NIJUT_BABU_2026.yaml` | Every rule has `severity`, `source`, `sourceUrl`, `defaultReason`, `defaultFix`; `test_rules.py` green | ⬛ |
| T-021 | A | 2 | Adjudication call + six guard rails | T-020 | `adjudicate.py`, `validation.py`, tests | Model output is schema-validated; invented findings and ungrounded values are rejected in tests | ⬛ |
| T-022 | A | 2 | Scoring and verdict persistence | T-020 | `scoring.py`, verdict writer | Score matches the arithmetic string; `previousScore` populated on the second run | ⬛ |
| T-023 | A | 2 | Document replacement and re-check | T-022 | Supersede logic + new verdict | Replacing a document produces a new verdict with the expected finding cleared | ◼ |
| T-024 | A | 2 | Structured logging + 7-day log retention | T-006 | Log helper, retention config | One JSON line per stage with `packetId` and duration; no field values in logs | ◼ |
| T-025 | B | 2 | Build the synthetic demo pack + replacement document | T-012 | `samples/demo-pack/` + `expected.json` | four documents, all watermarked; the three planted defects present; income certificate ~900 KB; replacement ≤200 KB | ⬛ |
| T-026 | B | 2 | Polling hook against the real API | T-007 | `usePacket` hook | Statuses transition live; gives up at 90 s with a retry action | ⬛ |
| T-027 | B | 2 | Re-check UI and score transition | T-023 | Replace + Re-check UI | `40 → 50` transition visible on screen | ◼ |
| T-028 | B | 2 | Fix-list clipboard export | T-017 | `FixListButton.tsx` | Pasted text contains all fixes and masked values only | ◻ |
| T-029 | B | 2 | Polish: empty, loading, error states; advisory line | T-016, T-017 | Final UI | No dead ends; every failure offers an action; verified on a real phone | ◼ |
| T-030 | B | 2 | Demo script and README draft | T-025 | `docs/demo-script.md` | Shot list totals ≤ 2:50 when read aloud | ◼ |
| T-031 | Both | 3 | Feature freeze at 08:00 | — | Frozen `main` | No non-bugfix commits after the freeze | ⬛ |
| T-032 | A | 3 | Final smoke test | T-031 | `scripts/e2e.py` output | Two consecutive cold runs pass; no CloudWatch errors | ⬛ |
| T-033 | A | 3 | PII and secrets sweep | T-031 | `scripts/grep_pii.sh` output | No 12-digit sequences, keys, `.env` files or real documents in the working tree or history | ⬛ |
| T-034 | B | 3 | Record and edit the demo video | T-030, T-031 | ≤ 3:00 video, shareable link | Shows all seven beats from `PROJECT.md` §14; no personal data in any frame; plays without login | ⬛ |
| T-035 | A | 3 | README and writeup | T-031 | Complete README | Covers problem, build, where AWS fits, what we learned, AI tools named, synthetic-data policy, limitations | ⬛ |
| T-036 | Both | 3 | Submit by 12:00 IST | T-034, T-035 | Submission confirmation | Repo URL, video link and writeup submitted through the stop's form | ⬛ |
| T-037 | B | 3 | AWS Builder Center blog post | T-035 | Published post, linked in the submission | Post live and linked | ◻ |
| T-038 | Both | 3 | Hindi labels / second demo packet | T-036 | — | Only after submission is confirmed | ◻ |

### The critical path, stated as one line
**T-001 → T-002 → T-003 → T-006 → T-007 → T-009 → T-011 → T-018 → T-020 → T-021 → T-022 → T-025 → T-032 → T-034 → T-036.**
Anything not on that list can slip a day without killing the submission. Anything on it that slips must be escalated in the team chat the moment it is noticed, not at the end of the day.

---

## 12. Parallel Work Plan

The principle: **A owns everything behind the API; B owns everything in front of it; the contracts in §9 are the wall between them and the mock fixture makes the wall load-bearing from hour two.**

### Day 0
- **A:** repo, contracts, fixtures, AWS/Bedrock access.
- **B:** Next.js scaffold, Amplify Hosting, recording pipeline.
- **Integration:** 15 minutes — Bedrock output shown, live URL shown, fixtures confirmed renderable.
- **Blocking risk:** B needs the repo (T-001) and the fixtures (T-002). A does both first. B has zero further dependencies until Friday midday.

### Day 1
- **A:** infrastructure → API handlers → Textract → Bedrock extraction → normalizers → first rules.
- **B:** design tokens → API client + mock → landing → upload slots → snapshot table → finding cards. All of it against the mock.
- **Integration point 1 (midday):** A publishes the API base URL; B tests only the upload path live. Timeboxed to 30 minutes; if it fights back, B reverts to mock and A debugs alone.
- **Integration point 2 (evening):** whole app pointed at the real API for a single-document run.
- **If A is blocked on AWS:** B continues indefinitely on mock. **If B is blocked:** A continues indefinitely on `pytest`. Neither can stall the other for more than the two scheduled checkpoints.

### Day 2
- **A:** four more roles → snapshot → eleven more rules → adjudication → scoring → re-check backend.
- **B:** demo pack → polling → re-check UI → export → polish → demo script.
- **Integration point 3 (midday):** the demo pack meets real extraction. This is where the bugs are. Both people work on it together for up to an hour — this is the one deliberately shared block of the event.
- **Integration point 4 (late afternoon):** go/no-go on the full three-finding run.
- **Why this order:** B's demo pack (T-025) is an input to A's extraction tuning (T-018), so B builds it first thing; A works on roles from the stress pack until it lands.

### Day 3
- **A:** verification, security sweep, README.
- **B:** video, edit, submission assets.
- **Integration:** the freeze at 08:00, then the submission together at 12:00.
- **Rule for the day:** A does not push to `main` while B is recording. If a bug must be fixed mid-recording, B finishes the take first.

### Standing rules for working in parallel
1. Branch per task named `T-0xx-short-name`; small PRs; merge to `main` the same day.
2. `main` must always deploy. If a push breaks the deployed frontend or API, fixing it is the pusher's immediate and only task.
3. Never edit the other person's directory. `backend/` is A's; `frontend/` is B's; `samples/` is B's; `infra/` is A's; `docs/` is shared.
4. Contract changes are announced verbally and land as a single commit touching `core/models.py`, `frontend/lib/types.ts` and the fixtures together.
5. Fifteen-minute stand-up at the start and end of each day against the day's acceptance criteria — not a status report, a check of whether the criteria will be met.

---

## 13. Testing Plan

### 13.1 Unit tests (`pytest`, A, continuous)
- `test_normalize.py` — 20+ cases: `ANTARJIT DAS` / `Antarjit  das` / `Shri Antarjit Das`; `12/03/2004`, `12-3-04`, `12 Mar 2004`; `₹2,60,000`, `Rs. 260000/-`, `2.6 Lakh`.
- `test_validators.py` — Verhoeff valid and invalid Aadhaar numbers; valid and invalid IFSC strings including the mandatory `0` in position 5.
- `test_rules.py` — **the most valuable test in the repo.** Given `fixtures/extractions_demo_packet.json`, the engine must produce exactly the finding IDs in `fixtures/expected_findings_demo.json`. Plus one fixture per rule for the rules not exercised by the demo packet.
- `test_scoring.py` — the arithmetic and the band boundaries at 59/60 and 84/85.
- `test_ai_validation.py` — four adversarial model responses: invalid JSON, an invented `findingId`, a value not present in the evidence, and a severity escalation attempt. All four must be caught.

### 13.2 Integration tests (A, Day 1 evening and Day 2)
- Deployed API: create packet → presigned URL → upload → mark uploaded → poll until `EXTRACTED` → verify field values against `expected.json`.
- Textract against each of the five demo documents, asserting that the key field for each role is present.
- One live Bedrock adjudication call asserting schema conformance.

### 13.3 End-to-end workflow test (`scripts/e2e.py`, Day 2 and Day 3)
Scripted against the deployed stack: full five-document packet → check → assert the three expected findings, the score of 40, and total wall-clock under 60 seconds. Then the replacement document → re-check → assert the finding cleared and the score is 50.

### 13.4 AI output validation (Day 2, recorded in the repo)
- The **name-pair fixture**: ten curated pairs, five the same person (case difference, extra space, `DAS`/`DASS`, `ANTARJIT`/`ANTARJEET`, initial expansion) and five genuinely different (different given name, different father's name, different DOB attached, a sibling's name, a completely different person). Target ≥ 8/10 correct. Run once and commit the results as `tests/fixtures/name_pairs_result.json` — this is evidence for the writeup, not just a test.
- Run the full adjudication three times on the same packet and confirm the findings and severities are stable.

### 13.5 Failure-case tests (Day 2)
| Case | Expected behaviour |
|---|---|
| Upload a 4 MB blurry photo | `documentQuality = POOR`, R-13 fires, no silently wrong values |
| Upload a `.txt` renamed to `.pdf` | `EXTRACTION_FAILED`, INFO finding, check still runs on the others |
| Run check with only 2 documents | 409 `NOT_ENOUGH_DOCUMENTS`, UI explains what is missing |
| Bedrock disabled (temporarily remove the IAM permission) | Verdict still renders with `aiStatus = FALLBACK_TEMPLATE` and template reasons |
| Upload a marksheet into the Aadhaar slot | R-12 fires |
| Two browser tabs polling the same packet | Both converge on the same verdict; no duplicate check runs |

### 13.6 Final acceptance test (Sunday morning, both present)
> From a cold browser in a private window, on the deployed URL: run the full demo packet twice, including the replace-and-re-check beat. Both runs must produce identical findings and scores, complete in under 60 seconds each, show no console errors, and display no unmasked Aadhaar anywhere. If either run fails, the video is not recorded until it passes.

---

## 14. Deployment Plan

### Local setup
```bash
# backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pytest          # core/ tests need no AWS

# frontend
cd frontend && npm install
cp .env.example .env.local                          # NEXT_PUBLIC_MOCK=1 to start
npm run dev
```

### Environment variables

| Where | Variable | Value |
|---|---|---|
| Lambda (all) | `TABLE_NAME` | `DefectGuard` |
| Lambda (all) | `BUCKET_NAME` | `defect-guard-uploads-<accountId>` |
| Workers | `BEDROCK_MODEL_ID` | `global.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| API Lambdas | `EXTRACT_FUNCTION_NAME`, `CHECK_FUNCTION_NAME` | SAM-resolved function names |
| Workers | `RULESET_ID` | `NIJUT_BABU_2026` |
| All | `LOG_LEVEL` | `INFO` |
| Amplify build | `NEXT_PUBLIC_API_BASE_URL` | the HTTP API invoke URL + `/v1` |
| Amplify build | `NEXT_PUBLIC_MOCK` | `0` |

**No AWS credentials ever appear in the frontend, the repo, or an environment variable that reaches the browser.**

### AWS configuration (once, Day 1, in this order)
1. `aws configure` with an IAM user that has the needed deploy permissions, region `ap-south-1`.
2. Bedrock console → Model access → enable the Anthropic Claude models in `ap-south-1` (Day 0, T-003). **This is not instant; do it first.**
3. `cd infra && sam build && sam deploy --guided` → stack `defect-guard`. Record the API URL and bucket name from the outputs.
4. Add the Amplify domain to the S3 CORS `AllowedOrigins` and redeploy the stack.
5. Amplify console → connect the GitHub repo → app root `frontend` → build `npm run build` → output `out` → set the two `NEXT_PUBLIC_*` variables → deploy.

### Deployment order (and after every change)
Backend first (`sam deploy`), then set/confirm `NEXT_PUBLIC_API_BASE_URL`, then `git push` to trigger the Amplify build. Never ship a frontend that expects an endpoint the backend has not deployed.

### Production / demo deployment
The deployed Amplify URL *is* the demo environment. There is no staging. The contract is that `main` always deploys; anything experimental lives on a branch.

### Final smoke test (Sunday, before recording)
1. `curl POST /packets` → 201.
2. Deployed frontend in a private window → full demo packet → verdict in under 60 s.
3. `python scripts/e2e.py` → all assertions pass.
4. CloudWatch log groups for the last hour → zero `ERROR` lines.
5. S3 console → objects present, bucket shows Block Public Access on.
6. DynamoDB console → items present with a populated `expiresAt`.
7. `bash scripts/grep_pii.sh` → clean.

---

## 15. Demo Build Plan

**Assets that must exist before recording (all by Saturday night):**
- `samples/demo-pack/` — the five synthetic documents plus the compliant replacement income certificate, all watermarked.
- `docs/demo-script.md` — the seven beats from `PROJECT.md` §14 with timings, narration text, and the exact clicks.
- `docs/architecture.txt` — the §2 diagram, rendered as a clean slide for the 2:25–2:50 segment.
- A browser profile with no personal bookmarks, no notifications, no logged-in tabs, and a neutral window title.
- One screenshot each of a Textract query response and a Bedrock structured-output JSON, ready to cut in for the AWS segment.

**Recording plan (Sunday morning, T-034):** record the app sequence in three takes — upload, verdict, re-check — rather than one continuous run, so a slow extraction does not cost the whole take. Record narration separately over the assembled footage. Check the total against 3:00 *before* colour-correcting anything.

**The single rule for the edit:** if a beat does not appear on screen, it does not exist. No feature is described in narration unless it is visible while it is being described.

---

## 16. Submission Checklist

Every item below comes from the First Commit rules, schedule and overview pages.

**Eligibility and admin**
- [-] Both members registered individually for the tour under their own accounts (a team is not registered by its captain).
- [-] Both members have an AWS Builder Center profile with **student status verified** — entry is not complete without it.
- [-] Team of 1–4; one team per person for this stop; one submission per team.
- [-] Graduation year checked against the fast-track criterion (Pre-Final 2028 / Final 2027) if that matters to the team.

**The build**
- [-] All project work done inside the event window; repository history matches it.
- [-] No prior work carried in; any library, template or asset that is not ours is credited with a permitting licence.
- [-] **AWS is in the project and pointable-at in the video**, not only in the writeup.
- [-] AI coding tools used (Antigravity, and any others) are **named in the writeup** — this is a rule, not a courtesy.

**The submission itself**
- [ ] **Public repository** URL.
- [ ] **Demo video, three minutes maximum**, hosted somewhere that plays without a login.
- [ ] **Writeup** covering the problem, the build, and where AWS fits.
- [ ] Submitted through the stop's own submission form, once, **before the deadline published on the stop page** — confirm the exact hour on Day 1; internal target is 12:00 IST on Sunday 20 September. A late submission is not scored, whatever the reason.
- [ ] Deployed public URL included (Ship It track).
- [ ] Optional: build-notes blog published on AWS Builder Center and linked (Top 5 Blogs prize).

**Our own bar, before we submit**
- [ ] No real personal data anywhere in the repo, the deployed app, the video or the writeup.
- [ ] Every rule in the rule set carries a source citation.
- [ ] No unsourced statistic appears anywhere.
- [ ] The README states the limitations honestly: no authentication, one scheme, synthetic demo data, Bedrock global cross-Region routing.

---

## 17. Contingency Plan

One fallback per failure point. Not a menu — the named fallback, or nothing.

| Failure point | Primary approach | Fallback |
|---|---|---|
| **Bedrock model access not granted in `ap-south-1`** | Claude Sonnet 4.5 via the global CRIS inference profile, Converse + structured outputs. | Switch `BEDROCK_MODEL_ID` to `global.anthropic.claude-haiku-4-5-20251001-v1:0`. If no Anthropic model is reachable at all, switch to an Amazon Nova model available in `ap-south-1` using **forced tool use** (`toolChoice: {"tool": {...}}`) for typed JSON instead of `outputConfig`. The rest of the pipeline is unchanged because the model boundary is one module. |
| **Structured outputs unavailable or malfunctioning** | `outputConfig.textFormat` with a JSON Schema. | Forced tool use with a single tool whose `inputSchema` is the same schema, then Pydantic validation. Same guard rails, same code path. |
| **Textract accuracy too low on a document role** | `AnalyzeDocument` with role-specific `QUERIES` + `FORMS`. | Fall back to `DetectDocumentText` for that role and let the Bedrock extraction call work from raw text alone. If a specific demo document still fails, regenerate it with a simpler layout — the demo pack is ours. |
| **API Gateway or Lambda async invocation misbehaving** | `POST /check` returns 202 and async-invokes the worker; the client polls. | Run the check synchronously inside the API Lambda for a **three-document** packet only, with the Lambda timeout at 29 s. Reduces the demo to three documents but keeps the workflow whole. |
| **Amplify Hosting build fails** | Static export deployed from GitHub via Amplify. | `npm run build` locally and upload the `out/` directory to Amplify Hosting as a manual deployment. Same URL, no CI. |
| **AWS account unusable or credits never arrive** | Ship It track, fully deployed. | Pivot to the **Build It** track: SAM CLI + LocalStack for S3/DynamoDB/Lambda, the rule engine unchanged, and the AI step against a locally reachable model. This costs the deployed URL and the Ship It grand prize, so it is a genuine last resort and the decision must be made by Friday midday at the latest — not Saturday. |
| **Extraction quality collapses across the board on Saturday** | four-role extraction from real uploads. | Ship with three roles (Aadhaar, income certificate, bank proof), which still supports two of the three planted defects and the whole workflow. Reduce the demo narrative accordingly; do not fake extraction. |
| **A team member becomes unavailable** | Two-person parallel plan. | The remaining member drops everything marked ◼ and ◻, ships the mock-mode frontend against whatever backend exists, and records the video against the working subset. The critical path in §11 is the only thing defended. |
| **Sunday: something breaks after the freeze** | Freeze at 08:00, record from a known-good build. | Revert `main` to the last green commit and record from that. A working older build beats a broken newer one, every time. |

---

## 18. Final Definition of Done

### Product
- [ ] A student can upload four documents and receive a ranked defect report with specific fixes and a readiness score.
- [ ] Every finding names the rule, the documents involved and their conflicting values.
- [ ] Every fix instruction names a specific document and a specific action.
- [ ] The re-check loop demonstrably clears a finding and moves the score.
- [ ] The advisory line is visible; the product never claims approval and never submits anything.

### Backend
- [ ] The five endpoints in §6 behave exactly as specified, including the listed error codes.
- [ ] `core/` has no `boto3` import and its tests pass offline.
- [ ] All eleven rules are implemented, each with a severity, a source and a source URL, and default reason/fix text.
- [ ] All six AI guard rails are implemented and tested against adversarial responses.
- [ ] The score is computed in Python and matches the displayed arithmetic.
- [ ] Aadhaar and account numbers are masked at extraction time and appear masked in storage, responses and logs.

### Frontend
- [ ] Usable at 360 px with no page-level horizontal scroll.
- [ ] Every state is handled: empty, uploading, extracting, extraction failed, checking, checked, error-with-retry.
- [ ] Severity is conveyed by word as well as colour.
- [ ] Mock mode still works (it is how the video's fallback would be recorded).
- [ ] Deployed at a public HTTPS Amplify URL.

### AWS
- [ ] S3: Block Public Access on, SSE enabled, 1-day lifecycle rule active, CORS scoped to our origins.
- [ ] DynamoDB: single table, TTL enabled and populated, no Scan in any code path.
- [ ] Textract and Bedrock invoked from Lambda with a working IAM role.
- [ ] CloudWatch: structured logs present, 7-day retention set, no PII in them.
- [ ] Billing alarm set; spend inside the credit.

### Testing
- [ ] `pytest` green, including the rule-engine fixture test and the four adversarial AI cases.
- [ ] `scripts/e2e.py` passes against the deployed stack.
- [ ] The name-pair fixture scores ≥ 8/10 and the result is committed.
- [ ] The six failure cases in §13.5 behave as specified.
- [ ] The final acceptance test in §13.6 passed twice, from cold.

### Deployment
- [ ] `sam deploy` reproduces the backend from a clean checkout.
- [ ] Amplify builds from `main` without manual steps.
- [ ] `.env.example` documents every variable; no secret is committed.
- [ ] The smoke-test sequence in §14 passed on Sunday morning.

### Demo
- [ ] Video is ≤ 3:00 and shows all seven beats.
- [ ] The public URL appears on screen at least once.
- [ ] The AWS segment names each service and what it does.
- [ ] No real personal data in any frame; every document on screen is watermarked SPECIMEN.
- [ ] The video plays without a login.

### Submission
- [ ] Public repository, history inside the event window.
- [ ] Video link and writeup submitted through the stop's form before the deadline.
- [ ] Writeup covers problem, build, where AWS fits, what we learned, and names the AI coding tools used.
- [ ] Both members' Builder Center profiles exist with student status verified.
- [ ] The PII sweep is clean and the synthetic-data policy is stated in the README, the writeup and the video.




