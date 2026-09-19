"""Deterministic AI guardrails and template fallback engine.

Sits between raw Bedrock adjudication output and the final findings list.
Implements 6 guard rails from IMPLEMENTATION.md §7:
  1. Schema Check        — Pydantic validation of AI JSON output
  2. Finding ID Lock     — Discard hallucinated finding IDs
  3. Evidence Grounding  — Verify quoted values exist in extraction text
  4. Severity Lock       — AI can only downgrade RED→AMBER, never escalate or delete
  5. Confidence Cap      — Low confidence forces AMBER with cautionary prefix
  6. Score Immunity      — AI never touches the score (enforced architecturally)

Also provides the template fallback engine: when Bedrock fails or returns
invalid output, populate findings from YAML defaultReason/defaultFix templates.

Zero external AWS/boto3 imports.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple

from ..core.models import (
    Finding,
    Severity,
    AIStatus,
)

logger = logging.getLogger(__name__)

# Rule IDs that are identity-type and eligible for AI adjudication.
# Only these rules can have isRealConflict evaluated.
ADJUDICABLE_RULE_IDS = {"R-01", "R-02", "R-03"}

# The confidence threshold below which we force AMBER severity
# and prepend a cautionary prefix to the reason.
LOW_CONFIDENCE_THRESHOLD = 0.6

CAUTIONARY_PREFIX = "We could not be certain, so please check: "


# =====================================================================
# Guardrail 1: Schema Check (Pydantic validation)
# =====================================================================

def validate_ai_json(raw_text: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """Parse and validate AI response as JSON.

    Returns:
        Tuple of (parsed_dict_or_None, error_message_or_empty_string).
        If parsing succeeds, error_message is empty.
        If parsing fails, parsed_dict is None and error_message explains why.
    """
    # Step 1: Try to parse as JSON
    try:
        parsed = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError) as e:
        return None, f"Invalid JSON from AI: {e}"

    # Step 2: Check it's a dict with a 'results' key
    if not isinstance(parsed, dict):
        return None, "AI response is not a JSON object."

    if "results" not in parsed:
        return None, "AI response missing required 'results' key."

    results = parsed["results"]
    if not isinstance(results, list):
        return None, "'results' is not an array."

    # Step 3: Validate each result has required fields
    required_fields = {"findingId", "isRealConflict", "confidence", "reason", "fixInstruction", "rankHint"}
    for i, result in enumerate(results):
        if not isinstance(result, dict):
            return None, f"Result at index {i} is not an object."

        missing = required_fields - set(result.keys())
        if len(missing) > 0:
            return None, f"Result at index {i} missing fields: {missing}"

    return parsed, ""


# =====================================================================
# Guardrail 2: Finding ID Lock
# =====================================================================

def filter_hallucinated_ids(
    ai_results: List[Dict[str, Any]],
    valid_finding_ids: List[str],
) -> List[Dict[str, Any]]:
    """Remove any AI results whose findingId was not produced by the rule engine.

    The AI model cannot add new findings — only adjudicate existing ones.
    Any findingId not in the valid set is a hallucination and gets discarded.

    Args:
        ai_results: The 'results' array from the AI response.
        valid_finding_ids: List of findingIds that the rule engine produced.

    Returns:
        Filtered list containing only results with valid findingIds.
    """
    valid_set = set(valid_finding_ids)
    filtered = []

    for result in ai_results:
        finding_id = result.get("findingId", "")
        if finding_id in valid_set:
            filtered.append(result)
        else:
            logger.warning(
                "Guardrail 2 (Finding ID Lock): Discarded hallucinated findingId '%s'. "
                "Valid IDs: %s",
                finding_id,
                valid_finding_ids,
            )

    return filtered


# =====================================================================
# Guardrail 3: Evidence Grounding
# =====================================================================

def check_evidence_grounding(
    ai_result: Dict[str, Any],
    known_values: List[str],
) -> bool:
    """Check if the AI's reason text references values that exist in extraction data.

    This is a soft check: we look for quoted strings (single or double quoted)
    in the reason and fixInstruction, and verify each quoted value appears
    somewhere in the known extraction values.

    Args:
        ai_result: One item from the AI 'results' array.
        known_values: All raw and normalized values from the extraction payload.

    Returns:
        True if evidence is grounded (or no quoted values found), False otherwise.
    """
    reason = ai_result.get("reason", "")
    fix = ai_result.get("fixInstruction", "")
    combined_text = reason + " " + fix

    # Extract quoted substrings (both single and double quotes)
    quoted_values = []
    for quote_char in ["'", '"']:
        parts = combined_text.split(quote_char)
        # Every odd-indexed part is inside quotes: text 'quoted' text 'quoted' ...
        #                                         0      1      2      3
        for i in range(1, len(parts), 2):
            quoted_val = parts[i].strip()
            if len(quoted_val) > 0:
                quoted_values.append(quoted_val)

    # If no quoted values, grounding passes by default
    if len(quoted_values) == 0:
        return True

    # Build a lowercase set of known values for substring matching
    known_lower = []
    for val in known_values:
        if val is not None:
            known_lower.append(str(val).lower())

    # Check each quoted value against known extraction data
    for quoted in quoted_values:
        quoted_lower = quoted.lower()
        found = False
        for known in known_lower:
            if quoted_lower in known or known in quoted_lower:
                found = True
                break
        if not found:
            logger.warning(
                "Guardrail 3 (Evidence Grounding): Quoted value '%s' not found in extraction data.",
                quoted,
            )
            return False

    return True


# =====================================================================
# Guardrail 4: Severity Lock
# =====================================================================

def apply_severity_lock(
    finding: Finding,
    ai_result: Dict[str, Any],
    rules_by_id: Dict[str, Dict[str, Any]],
) -> Severity:
    """Determine the final severity after AI adjudication.

    Rules:
    - Severity comes from the YAML ruleset, not from the AI.
    - For adjudicable identity rules (R-01, R-02, R-03):
      if isRealConflict is False, RED may be DOWNGRADED to AMBER.
      The AI can never escalate (AMBER→RED) or delete findings.
    - For non-identity rules: isRealConflict is ignored entirely.

    Args:
        finding: The original Finding from the rule engine.
        ai_result: The AI's adjudication result for this finding.
        rules_by_id: The YAML rules dictionary keyed by rule ID.

    Returns:
        The final Severity enum value.
    """
    original_severity = finding.severity
    rule_id = finding.ruleId
    is_real_conflict = ai_result.get("isRealConflict", True)

    # Only identity rules can be downgraded
    if rule_id not in ADJUDICABLE_RULE_IDS:
        return original_severity

    # If AI says it IS a real conflict, keep original severity
    if is_real_conflict:
        return original_severity

    # If AI says it's NOT a real conflict, downgrade RED→AMBER only
    if original_severity == Severity.RED:
        logger.info(
            "Guardrail 4 (Severity Lock): Downgrading %s from RED to AMBER "
            "(AI determined isRealConflict=False).",
            finding.findingId,
        )
        return Severity.AMBER

    # AMBER stays AMBER, INFO stays INFO (no escalation possible)
    return original_severity


# =====================================================================
# Guardrail 5: Confidence Cap
# =====================================================================

def apply_confidence_cap(
    severity: Severity,
    confidence: float,
    reason: str,
) -> Tuple[Severity, str]:
    """Force AMBER and prepend cautionary prefix when confidence is low.

    If confidence < 0.6, the severity is forced to AMBER (even if it was RED)
    and the reason is prefixed with a cautionary message.

    Args:
        severity: The current severity (possibly already modified by severity lock).
        confidence: The AI's reported confidence (0.0 to 1.0).
        reason: The current reason text.

    Returns:
        Tuple of (final_severity, final_reason).
    """
    if confidence < LOW_CONFIDENCE_THRESHOLD:
        logger.info(
            "Guardrail 5 (Confidence Cap): Confidence %.2f < %.2f threshold. "
            "Forcing AMBER severity.",
            confidence,
            LOW_CONFIDENCE_THRESHOLD,
        )
        # Don't double-prefix if it's already there
        if not reason.startswith(CAUTIONARY_PREFIX):
            reason = CAUTIONARY_PREFIX + reason
        return Severity.AMBER, reason

    return severity, reason


# =====================================================================
# Guardrail 6: Score Immunity
# =====================================================================
# This guardrail is enforced ARCHITECTURALLY — the AI response schema
# has no score field, and scoring.py runs AFTER validation completes.
# There is nothing for the AI to tamper with. This function exists as
# a documented assertion point and for testing.

def assert_score_immunity(ai_response: Dict[str, Any]) -> None:
    """Verify the AI response contains no score-related fields.

    The score is computed by core/scoring.py using pure deterministic
    arithmetic AFTER all guardrails run. This assertion confirms the
    AI has no avenue to inject or alter the score.

    Raises:
        ValueError: If the AI response contains score-related keys.
    """
    forbidden_keys = {"score", "totalScore", "readinessScore", "band", "scoreArithmetic"}

    for key in forbidden_keys:
        if key in ai_response:
            raise ValueError(
                f"Guardrail 6 (Score Immunity): AI response contains forbidden "
                f"score-related key '{key}'. Score must only come from core/scoring.py."
            )

    # Also check inside each result
    for result in ai_response.get("results", []):
        for key in forbidden_keys:
            if key in result:
                raise ValueError(
                    f"Guardrail 6 (Score Immunity): AI result contains forbidden "
                    f"score-related key '{key}' inside finding '{result.get('findingId', '?')}'."
                )


# =====================================================================
# Template Fallback Engine
# =====================================================================

def apply_template_fallback(
    finding: Finding,
    rules_by_id: Dict[str, Dict[str, Any]],
) -> Finding:
    """Populate a finding with YAML template reason and fix when AI is unavailable.

    This is the safety net: if Bedrock fails, throttles, or returns garbage,
    every finding still gets a clear, verified explanation from the YAML ruleset.

    Args:
        finding: The original Finding from the rule engine.
        rules_by_id: The YAML rules dictionary keyed by rule ID.

    Returns:
        A new Finding with template reason/fix text applied.
    """
    rule = rules_by_id.get(finding.ruleId)
    if rule is None:
        # If we somehow don't have the rule, keep existing text
        return finding

    template_reason = rule.get("defaultReason", finding.reason)
    template_fix = rule.get("defaultFix", finding.fixInstruction)

    # Create a new Finding with template text (Pydantic models are immutable-ish,
    # so we copy and override specific fields)
    return Finding(
        findingId=finding.findingId,
        ruleId=finding.ruleId,
        title=finding.title,
        severity=finding.severity,
        category=finding.category,
        documents=finding.documents,
        reason=template_reason,
        fixInstruction=template_fix,
        confidence=finding.confidence,
        source=finding.source,
        needsAdjudication=False,  # No longer needs adjudication after fallback
    )


# =====================================================================
# Main Orchestrator: Apply All Guardrails
# =====================================================================

def apply_all_guardrails(
    raw_ai_text: str,
    findings: List[Finding],
    rules_by_id: Dict[str, Dict[str, Any]],
    known_values: Optional[List[str]] = None,
) -> Tuple[List[Finding], AIStatus]:
    """Run all 6 guardrails on the AI response and return validated findings.

    This is the main entry point that the Lambda handler will call after
    receiving a Bedrock response. It chains all guardrails in order.

    Args:
        raw_ai_text: The raw JSON text returned by Bedrock.
        findings: The original findings list from the rule engine.
        rules_by_id: The YAML rules dictionary keyed by rule ID.
        known_values: All known raw/normalized values from extractions
                      (used for evidence grounding check).

    Returns:
        Tuple of (updated_findings_list, ai_status).
        ai_status is OK if guardrails passed, or a fallback status.
    """
    if known_values is None:
        known_values = []

    # --- Guardrail 1: Schema Check ---
    parsed, error = validate_ai_json(raw_ai_text)
    if parsed is None:
        logger.warning("Guardrail 1 failed: %s. Falling back to templates.", error)
        fallback_findings = []
        for f in findings:
            if f.needsAdjudication:
                fallback_findings.append(apply_template_fallback(f, rules_by_id))
            else:
                fallback_findings.append(f)
        return fallback_findings, AIStatus.FALLBACK_AFTER_INVALID_JSON

    # --- Guardrail 6: Score Immunity (check early, before processing) ---
    try:
        assert_score_immunity(parsed)
    except ValueError as e:
        logger.warning("Guardrail 6 failed: %s. Falling back to templates.", e)
        fallback_findings = []
        for f in findings:
            if f.needsAdjudication:
                fallback_findings.append(apply_template_fallback(f, rules_by_id))
            else:
                fallback_findings.append(f)
        return fallback_findings, AIStatus.FALLBACK_AFTER_INVALID_JSON

    ai_results = parsed["results"]

    # --- Guardrail 2: Finding ID Lock ---
    valid_ids = []
    for f in findings:
        if f.needsAdjudication:
            valid_ids.append(f.findingId)

    ai_results = filter_hallucinated_ids(ai_results, valid_ids)

    # Build a lookup of AI results by findingId for fast access
    ai_by_finding_id = {}
    for result in ai_results:
        ai_by_finding_id[result["findingId"]] = result

    # --- Apply Guardrails 3, 4, 5 to each finding ---
    updated_findings = []
    for finding in findings:
        # If this finding doesn't need adjudication, keep it as-is
        if not finding.needsAdjudication:
            updated_findings.append(finding)
            continue

        # If the AI didn't return a result for this finding, use template fallback
        ai_result = ai_by_finding_id.get(finding.findingId)
        if ai_result is None:
            logger.info(
                "No AI result for finding %s. Using template fallback.",
                finding.findingId,
            )
            updated_findings.append(apply_template_fallback(finding, rules_by_id))
            continue

        # --- Guardrail 3: Evidence Grounding ---
        grounded = check_evidence_grounding(ai_result, known_values)
        if not grounded:
            logger.info(
                "Evidence grounding failed for %s. Using template fallback text.",
                finding.findingId,
            )
            updated_findings.append(apply_template_fallback(finding, rules_by_id))
            continue

        # --- Guardrail 4: Severity Lock ---
        new_severity = apply_severity_lock(finding, ai_result, rules_by_id)

        # Get AI's reason and fix text
        ai_reason = ai_result.get("reason", finding.reason)
        ai_fix = ai_result.get("fixInstruction", finding.fixInstruction)
        ai_confidence = ai_result.get("confidence", 1.0)

        # Clamp confidence to valid range
        if ai_confidence < 0.0:
            ai_confidence = 0.0
        if ai_confidence > 1.0:
            ai_confidence = 1.0

        # --- Guardrail 5: Confidence Cap ---
        new_severity, ai_reason = apply_confidence_cap(new_severity, ai_confidence, ai_reason)

        # Build the updated finding
        updated_finding = Finding(
            findingId=finding.findingId,
            ruleId=finding.ruleId,
            title=finding.title,
            severity=new_severity,
            category=finding.category,
            documents=finding.documents,
            reason=ai_reason,
            fixInstruction=ai_fix,
            confidence=ai_confidence,
            source=finding.source,
            needsAdjudication=False,  # Adjudication complete
        )
        updated_findings.append(updated_finding)

    return updated_findings, AIStatus.OK
