# BRAIN
## STATE
- phase: ALL_PHASES_COMPLETE (Phases 1 through 9 fully built, committed, and verified)
- blockers: none (All 83 tests passing, SAM template validated, E2E demo verified, PII sweep clean)

## DECISIONS
- D: Work strictly on branch 'backend' | why: isolated backend delivery before merge | src: user prompt
- D: Single table DefectGuard with PK=PACKET#<id>, SK=META|DOC#<id>|VERDICT#<ts> | why: zero-scan single-table design | src: IMPLEMENTATION.md §5
- D: Pure Python in core/ without any boto3 imports | why: enables offline unit testing without AWS | src: IMPLEMENTATION.md §2
- D: Pydantic v2 and boto3>=1.40 for structured outputs | why: Bedrock outputConfig compatibility | src: IMPLEMENTATION.md §3
- D: Build simple functional UI directly | why: functional proof-of-concept without waiting for design polish | src: user prompt
- D: Ignore agent_brain.md and agent_implementationplan.md in .gitignore for now | why: keep tracking internal to workspace | src: user prompt
- D: Strict Pydantic models with extra='forbid' on core domain objects | why: prevents AI output or API calls from injecting untyped attributes | src: Commit 1.2
- D: Frontend mock fixtures validated against backend Pydantic models in tests | why: ensures frontend and backend contracts cannot drift | src: Commit 1.3
- D: Verhoeff algorithm implemented offline for Aadhaar check-digit validation | why: instant mathematical fraud/typo detection without external API | src: Commit 2.1
- D: Mask Aadhaar (XXXXXXXX1234) and bank accounts (XXXXXX9821) immediately in core | why: strict privacy and regulatory compliance | src: Commit 2.1
- D: Snapshot canonical precedence: AADHAAR > MARKSHEET > INCOME_CERTIFICATE > BANK_PROOF | why: legal hierarchy of identity truth | src: Commit 2.2
- D: Cross-document disagreement detection uses normalized domain values | why: prevents false alerts on casing, honorifics, or currency symbols | src: Commit 2.2
- D: Scoring is 100% deterministic pure Python arithmetic, LLM never computes or alters score | why: eliminates AI hallucination / tampering in scoring | src: Commit 2.3
- D: All 11 scheme rules defined in YAML with legal citations and default fallback templates | why: policy transparency and offline fallback resilience | src: Commit 3.1
- D: RuleEngine evaluates snapshot deterministically and flags needsAdjudication for identity rules | why: separates hard deterministic criteria from AI judgment calls | src: Commit 3.2
- D: Bedrock Converse outputConfig.textFormat uses JSON Schema strings | why: enforces 100% typed JSON responses without chat filler | src: Commit 4.1
- D: 6 deterministic guardrails validate AI output before merging into findings | why: catches hallucinated IDs, ungrounded evidence, severity escalation, and score tampering | src: Commit 4.2
- D: Template fallback engine populates YAML defaultReason/defaultFix when Bedrock fails | why: app works without cloud AI, always delivers verified explanations | src: Commit 4.2
- D: S3 presigned PUT URLs with bound ContentType and head_object authoritative size check | why: prevents fake client file size attacks | src: Commit 5.1
- D: Single table DefectGuard query retrieves META + DOC# + latest VERDICT# in one request | why: achieves sub-10ms UI polling latency without secondary indexes | src: Commit 5.1
- D: REST endpoints enforce exact error shape {"error": {"code": "...", "message": "..."}} | why: guarantees seamless error handling across frontend/backend boundary | src: Commit 6.1
- D: Re-uploading a document role automatically sets supersededBy on the previous doc | why: preserves audit trail while excluding old documents from snapshot | src: Commit 6.1
- D: fn_extract_document runs normalizers and PII masking before persisting to DynamoDB | why: guarantees raw Aadhaar/bank numbers never land in DynamoDB | src: Commit 6.2
- D: fn_run_check connects RuleEngine -> Bedrock Adjudication -> 6 Guardrails -> deterministic scoring | why: guarantees end-to-end policy compliance with template fallback safety | src: Commit 6.2

## GOTCHAS
- Windows PowerShell requires refreshing PATH from registry to see newly installed SAM CLI (`C:\Program Files\Amazon\AWSSAMCLI\bin\sam.exe`).
- Python version in local environment is Python 3.14.7.
- Bedrock invocation in ap-south-1 requires Global CRIS inference profile ID `global.anthropic.claude-sonnet-4-5-20250929-v1:0`, never base model ID.

## UNKNOWN
- Exact AWS Account ID and S3 deployment bucket suffix for SAM deployment (to be populated at deployment time).
