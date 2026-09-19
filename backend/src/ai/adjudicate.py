"""Prompt assembly for Bedrock finding adjudication and student fix generation.

Frames ambiguous discrepancies from the perspective of an NSP (National Scholarship Portal)
Institute Nodal Officer to distinguish benign spelling/transliteration variants
from true disqualifying defects.
Zero external AWS/boto3 imports.
"""

from typing import List, Tuple, Dict, Any
from ..core.models import Finding, Snapshot


ADJUDICATION_SYSTEM_PROMPT = """You are an expert scholarship verification adjudicator assisting an NSP (National Scholarship Portal) Institute Nodal Officer in Assam.
Your role is to evaluate candidate document discrepancies flagged during pre-submission checks for the Mukhya Mantrir Nijut Babu Aasoni (MMNBA 2026).

FRAMEWORK FOR JUDGMENT:
Ask yourself: "Would a government institute nodal officer, comparing the application form to this document, reject this application as a mismatch, or treat it as the same individual?"

WORKED EXAMPLES:
1. BENIGN TRANSLITERATION / TYPOGRAPHICAL VARIANT (isRealConflict = False):
   - Example: Aadhaar has 'ANTARJIT DAS', Marksheet has 'ANTARJEET DASS'.
   - Judgment: Common phonetic transliteration of the Assamese/Bengali surname 'Das'/'Dass' and vowel substitution 'i'/'ee'. Not a fraudulent identity mismatch.
   - Action: Downgrade severity to AMBER warning; advise checking college registration.

2. GENUINE IDENTITY MISMATCH (isRealConflict = True):
   - Example: Aadhaar has 'RAHUL DAS', Marksheet has 'ROHIT DAS'.
   - Judgment: Completely different first names. Direct basis for rejection under scrutiny.
   - Action: Maintain RED severity; instruct applicant to obtain correct mark record or update application.

3. GUARDIAN / FATHER'S NAME VARIANT:
   - Example: 'PRODIP DAS' vs 'PRADIP KUMAR DAS'.
   - Judgment: Addition of middle name 'Kumar' or vowel shift 'o'/'a' in regional transliteration. Set isRealConflict = False with cautionary verification note.

RULES:
- Never invent new findings. Only adjudicate the findingIds supplied.
- Never alter the scoring arithmetic.
- Keep reason and fixInstruction concise (under 320 characters), polite, and specifically naming the participating document.
"""


def build_adjudication_prompt(
    snapshot: Snapshot,
    candidate_findings: List[Finding],
) -> Tuple[str, str]:
    """Assemble the system and user prompts for Bedrock defect adjudication.

    Returns:
        Tuple of (system_prompt: str, user_prompt: str).
    """
    # Format candidate findings requiring adjudication
    findings_blocks = []
    for f in candidate_findings:
        docs_desc = []
        for doc_ref in f.documents:
            docs_desc.append(f"  * {doc_ref.role.value}: '{doc_ref.value}'")
        docs_str = "\n".join(docs_desc) if docs_desc else "  * (Scheme level check)"

        findings_blocks.append(
            f"Finding ID: {f.findingId}\n"
            f"Rule ID: {f.ruleId} ({f.title})\n"
            f"Category: {f.category.value}\n"
            f"Current Severity: {f.severity.value}\n"
            f"Participating Documents:\n{docs_str}\n"
            f"Preliminary Reason: {f.reason}\n"
            f"Preliminary Fix: {f.fixInstruction}\n"
        )

    findings_text = "\n---\n".join(findings_blocks)

    # Format snapshot summary for context
    snapshot_lines = []
    for row in snapshot.rows:
        roles_val_str = ", ".join([f"{k}: '{v}'" for k, v in row.valuesByRole.items()])
        snapshot_lines.append(f"- {row.label} [{row.fieldKey}] => Canonical: '{row.canonicalValue}' ({roles_val_str})")

    snapshot_text = "\n".join(snapshot_lines)

    user_prompt = f"""Application Snapshot Summary:
{snapshot_text}

Candidate Findings to Adjudicate:
{findings_text}

Instructions:
Evaluate each candidate finding above according to the Nodal Officer guidelines.
For each finding, return:
- findingId: matching the provided ID exactly.
- isRealConflict: boolean indicating if this is a genuine disqualifying defect.
- confidence: your confidence score (0.0 to 1.0).
- reason: 1-2 clear sentences explaining the finding to the student (max 320 chars).
- fixInstruction: exact single document and action to take (max 320 chars).
- rankHint: integer priority rank (1 = highest urgency).
"""

    return ADJUDICATION_SYSTEM_PROMPT, user_prompt.strip()
