"""Adversarial unit tests for AI guardrails and template fallback engine.

Tests 4 attack scenarios that could occur in production:
  1. Invalid JSON / garbage from Bedrock
  2. Hallucinated findingIds not produced by the rule engine
  3. Quoted values in reason text not found in extraction evidence
  4. AI attempting to escalate severity (AMBER→RED)
Plus tests for the confidence cap, score immunity, template fallback,
and the full orchestrator pipeline.
"""

import json

from backend.src.core.models import (
    Finding,
    Severity,
    FindingCategory,
    DocumentRole,
    DocumentReference,
    AIStatus,
)
from backend.src.ai.validation import (
    validate_ai_json,
    filter_hallucinated_ids,
    check_evidence_grounding,
    apply_severity_lock,
    apply_confidence_cap,
    assert_score_immunity,
    apply_template_fallback,
    apply_all_guardrails,
    CAUTIONARY_PREFIX,
    LOW_CONFIDENCE_THRESHOLD,
)


# =====================================================================
# Helper: Build a sample Finding for tests
# =====================================================================

def make_finding(
    finding_id="f1",
    rule_id="R-01",
    severity=Severity.RED,
    needs_adjudication=True,
    reason="Names disagree across documents.",
    fix="Ensure your Marksheet name matches Aadhaar.",
):
    """Create a sample Finding for testing."""
    return Finding(
        findingId=finding_id,
        ruleId=rule_id,
        title="Student name mismatch",
        severity=severity,
        category=FindingCategory.IDENTITY,
        documents=[
            DocumentReference(role=DocumentRole.AADHAAR, value="ANTARJIT DAS"),
            DocumentReference(role=DocumentRole.MARKSHEET, value="ANTARJEET DASS"),
        ],
        reason=reason,
        fixInstruction=fix,
        confidence=0.96,
        source="MMNBA 2026 Guidelines",
        needsAdjudication=needs_adjudication,
    )


# Sample YAML rules_by_id dictionary (mimics what RuleEngine loads)
SAMPLE_RULES = {
    "R-01": {
        "id": "R-01",
        "title": "Student name mismatch across documents",
        "severity": "RED",
        "category": "IDENTITY",
        "needsAdjudication": True,
        "defaultReason": "Your name is spelled differently across submitted documents.",
        "defaultFix": "Check your records and ensure the spelling matches your Aadhaar card.",
    },
    "R-02": {
        "id": "R-02",
        "title": "Father's name mismatch",
        "severity": "RED",
        "category": "IDENTITY",
        "needsAdjudication": True,
        "defaultReason": "Your father's name appears differently across documents.",
        "defaultFix": "Verify the correct spelling of your parent's name.",
    },
    "R-04": {
        "id": "R-04",
        "title": "Institution enrollment requires verification",
        "severity": "AMBER",
        "category": "ELIGIBILITY",
        "needsAdjudication": False,
        "defaultReason": "Your institution requires confirmation.",
        "defaultFix": "Verify with your college nodal officer.",
    },
}


# =====================================================================
# Test 1: Invalid JSON / Garbage from Bedrock
# =====================================================================

def test_guardrail1_invalid_json_garbage():
    """Bedrock returns complete garbage text (not JSON at all)."""
    parsed, error = validate_ai_json("This is not JSON at all, just random text.")
    assert parsed is None
    assert "Invalid JSON" in error


def test_guardrail1_invalid_json_missing_results():
    """Bedrock returns valid JSON but without the required 'results' key."""
    parsed, error = validate_ai_json('{"answer": "hello"}')
    assert parsed is None
    assert "missing required 'results' key" in error


def test_guardrail1_invalid_json_results_not_array():
    """Bedrock returns 'results' but it's a string, not an array."""
    parsed, error = validate_ai_json('{"results": "not an array"}')
    assert parsed is None
    assert "not an array" in error


def test_guardrail1_invalid_json_missing_required_fields():
    """Bedrock returns a result object missing required fields."""
    bad_response = json.dumps({
        "results": [
            {"findingId": "f1", "isRealConflict": True}
            # Missing: confidence, reason, fixInstruction, rankHint
        ]
    })
    parsed, error = validate_ai_json(bad_response)
    assert parsed is None
    assert "missing fields" in error


def test_guardrail1_valid_json_passes():
    """A properly structured AI response passes schema check."""
    good_response = json.dumps({
        "results": [
            {
                "findingId": "f1",
                "isRealConflict": False,
                "confidence": 0.85,
                "reason": "Common transliteration variant.",
                "fixInstruction": "Check college registration.",
                "rankHint": 2,
            }
        ]
    })
    parsed, error = validate_ai_json(good_response)
    assert parsed is not None
    assert error == ""
    assert len(parsed["results"]) == 1


# =====================================================================
# Test 2: Hallucinated Finding IDs
# =====================================================================

def test_guardrail2_filters_hallucinated_ids():
    """AI invents findingIds that the rule engine never produced."""
    ai_results = [
        {"findingId": "f1", "isRealConflict": True, "confidence": 0.9,
         "reason": "Real finding.", "fixInstruction": "Fix it.", "rankHint": 1},
        {"findingId": "f99", "isRealConflict": False, "confidence": 0.5,
         "reason": "I made this up.", "fixInstruction": "Hallucinated.", "rankHint": 2},
        {"findingId": "f2", "isRealConflict": True, "confidence": 0.8,
         "reason": "Another real one.", "fixInstruction": "Fix.", "rankHint": 3},
    ]

    valid_ids = ["f1", "f2"]
    filtered = filter_hallucinated_ids(ai_results, valid_ids)

    assert len(filtered) == 2
    result_ids = []
    for r in filtered:
        result_ids.append(r["findingId"])
    assert "f99" not in result_ids
    assert "f1" in result_ids
    assert "f2" in result_ids


def test_guardrail2_all_hallucinated():
    """AI returns only hallucinated findingIds — everything gets discarded."""
    ai_results = [
        {"findingId": "f100", "isRealConflict": True, "confidence": 0.9,
         "reason": "Fake.", "fixInstruction": "Fake.", "rankHint": 1},
    ]
    filtered = filter_hallucinated_ids(ai_results, ["f1", "f2"])
    assert len(filtered) == 0


# =====================================================================
# Test 3: Evidence Grounding (Quoted Values Not in Extraction)
# =====================================================================

def test_guardrail3_ungrounded_quoted_value():
    """AI's reason quotes a value that doesn't exist in the extraction data."""
    ai_result = {
        "findingId": "f1",
        "reason": "The name 'RAHUL SHARMA' does not match the Aadhaar record.",
        "fixInstruction": "Upload the correct Marksheet.",
    }
    # Our extraction data only has ANTARJIT DAS and ANTARJEET DASS
    known = ["ANTARJIT DAS", "ANTARJEET DASS", "12/03/2004"]

    grounded = check_evidence_grounding(ai_result, known)
    assert grounded is False


def test_guardrail3_grounded_quoted_value():
    """AI's reason quotes actual values from the extraction — passes."""
    ai_result = {
        "findingId": "f1",
        "reason": "The name 'ANTARJIT DAS' on Aadhaar differs from 'ANTARJEET DASS' on Marksheet.",
        "fixInstruction": "Verify the correct spelling.",
    }
    known = ["ANTARJIT DAS", "ANTARJEET DASS"]

    grounded = check_evidence_grounding(ai_result, known)
    assert grounded is True


def test_guardrail3_no_quotes_passes():
    """AI's reason has no quoted values at all — passes by default."""
    ai_result = {
        "findingId": "f1",
        "reason": "The student name appears to be a transliteration variant.",
        "fixInstruction": "Check college records.",
    }
    grounded = check_evidence_grounding(ai_result, ["ANTARJIT DAS"])
    assert grounded is True


# =====================================================================
# Test 4: Severity Escalation Attempt
# =====================================================================

def test_guardrail4_cannot_escalate_amber_to_red():
    """AI cannot escalate an AMBER finding to RED — severity stays AMBER."""
    finding = make_finding(severity=Severity.AMBER, rule_id="R-01")
    ai_result = {"isRealConflict": True}  # AI says it IS a real conflict

    # Even with isRealConflict=True, AMBER cannot escalate to RED
    result = apply_severity_lock(finding, ai_result, SAMPLE_RULES)
    assert result == Severity.AMBER


def test_guardrail4_can_downgrade_red_to_amber():
    """AI CAN downgrade RED to AMBER when isRealConflict=False for identity rules."""
    finding = make_finding(severity=Severity.RED, rule_id="R-01")
    ai_result = {"isRealConflict": False}

    result = apply_severity_lock(finding, ai_result, SAMPLE_RULES)
    assert result == Severity.AMBER


def test_guardrail4_non_identity_rule_ignores_conflict():
    """For non-identity rules, isRealConflict is ignored entirely."""
    finding = make_finding(severity=Severity.AMBER, rule_id="R-04", needs_adjudication=False)
    ai_result = {"isRealConflict": False}

    result = apply_severity_lock(finding, ai_result, SAMPLE_RULES)
    # R-04 is not in ADJUDICABLE_RULE_IDS, so original severity is returned
    assert result == Severity.AMBER


def test_guardrail4_red_stays_red_when_real_conflict():
    """RED stays RED when AI confirms isRealConflict=True."""
    finding = make_finding(severity=Severity.RED, rule_id="R-01")
    ai_result = {"isRealConflict": True}

    result = apply_severity_lock(finding, ai_result, SAMPLE_RULES)
    assert result == Severity.RED


# =====================================================================
# Test 5: Confidence Cap
# =====================================================================

def test_guardrail5_low_confidence_forces_amber():
    """Confidence below 0.6 forces AMBER severity and adds cautionary prefix."""
    severity, reason = apply_confidence_cap(
        Severity.RED,
        0.45,
        "The names appear different.",
    )
    assert severity == Severity.AMBER
    assert reason.startswith(CAUTIONARY_PREFIX)


def test_guardrail5_high_confidence_keeps_severity():
    """Confidence above threshold keeps the severity unchanged."""
    severity, reason = apply_confidence_cap(
        Severity.RED,
        0.85,
        "The names are definitely different.",
    )
    assert severity == Severity.RED
    assert not reason.startswith(CAUTIONARY_PREFIX)


def test_guardrail5_exactly_at_threshold():
    """Confidence exactly at 0.6 keeps severity (threshold is strictly less-than)."""
    severity, reason = apply_confidence_cap(
        Severity.RED,
        LOW_CONFIDENCE_THRESHOLD,
        "Right at threshold.",
    )
    assert severity == Severity.RED


# =====================================================================
# Test 6: Score Immunity
# =====================================================================

def test_guardrail6_detects_score_tampering():
    """AI response with a 'score' key is rejected."""
    tampered_response = {"results": [], "score": 100}
    try:
        assert_score_immunity(tampered_response)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "score" in str(e)


def test_guardrail6_detects_score_inside_result():
    """AI tries to sneak a 'totalScore' into an individual result."""
    tampered_response = {
        "results": [
            {
                "findingId": "f1",
                "isRealConflict": True,
                "confidence": 0.9,
                "reason": "test",
                "fixInstruction": "test",
                "rankHint": 1,
                "totalScore": 95,
            }
        ]
    }
    try:
        assert_score_immunity(tampered_response)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "totalScore" in str(e)


def test_guardrail6_clean_response_passes():
    """A clean response with no score fields passes the check."""
    clean_response = {
        "results": [
            {
                "findingId": "f1",
                "isRealConflict": True,
                "confidence": 0.9,
                "reason": "test",
                "fixInstruction": "test",
                "rankHint": 1,
            }
        ]
    }
    # Should not raise
    assert_score_immunity(clean_response)


# =====================================================================
# Test 7: Template Fallback
# =====================================================================

def test_template_fallback_uses_yaml_defaults():
    """When AI fails, findings get populated with YAML template text."""
    finding = make_finding()
    result = apply_template_fallback(finding, SAMPLE_RULES)

    assert result.reason == SAMPLE_RULES["R-01"]["defaultReason"]
    assert result.fixInstruction == SAMPLE_RULES["R-01"]["defaultFix"]
    assert result.needsAdjudication is False


# =====================================================================
# Test 8: Full Orchestrator — Happy Path
# =====================================================================

def test_full_pipeline_happy_path():
    """Full pipeline with a valid AI response returns OK status."""
    finding = make_finding(finding_id="f1", rule_id="R-01")
    non_adj_finding = make_finding(
        finding_id="f2", rule_id="R-04",
        severity=Severity.AMBER, needs_adjudication=False,
        reason="Institution check.", fix="Check enrollment.",
    )

    ai_response = json.dumps({
        "results": [
            {
                "findingId": "f1",
                "isRealConflict": False,
                "confidence": 0.87,
                "reason": "Common transliteration of 'ANTARJIT DAS' vs 'ANTARJEET DASS'.",
                "fixInstruction": "Verify with college registration.",
                "rankHint": 2,
            }
        ]
    })

    known_values = ["ANTARJIT DAS", "ANTARJEET DASS"]
    updated, status = apply_all_guardrails(
        ai_response, [finding, non_adj_finding], SAMPLE_RULES, known_values,
    )

    assert status == AIStatus.OK
    assert len(updated) == 2

    # f1 should be downgraded from RED to AMBER (isRealConflict=False)
    f1 = updated[0]
    assert f1.findingId == "f1"
    assert f1.severity == Severity.AMBER
    assert f1.needsAdjudication is False

    # f2 should be unchanged (not adjudicable)
    f2 = updated[1]
    assert f2.findingId == "f2"
    assert f2.severity == Severity.AMBER


# =====================================================================
# Test 9: Full Orchestrator — Garbage JSON Triggers Template Fallback
# =====================================================================

def test_full_pipeline_garbage_json_fallback():
    """Garbage AI output triggers FALLBACK_AFTER_INVALID_JSON and template text."""
    finding = make_finding(finding_id="f1", rule_id="R-01")

    updated, status = apply_all_guardrails(
        "NOT VALID JSON {{{{",
        [finding],
        SAMPLE_RULES,
    )

    assert status == AIStatus.FALLBACK_AFTER_INVALID_JSON
    assert len(updated) == 1
    assert updated[0].reason == SAMPLE_RULES["R-01"]["defaultReason"]
    assert updated[0].needsAdjudication is False


# =====================================================================
# Test 10: Full Orchestrator — Score Tampering Triggers Fallback
# =====================================================================

def test_full_pipeline_score_tampering_fallback():
    """AI tries to inject a score field — triggers fallback."""
    finding = make_finding(finding_id="f1", rule_id="R-01")

    tampered = json.dumps({
        "results": [
            {
                "findingId": "f1",
                "isRealConflict": True,
                "confidence": 0.9,
                "reason": "test",
                "fixInstruction": "test",
                "rankHint": 1,
            }
        ],
        "score": 100,
    })

    updated, status = apply_all_guardrails(tampered, [finding], SAMPLE_RULES)
    assert status == AIStatus.FALLBACK_AFTER_INVALID_JSON
    assert updated[0].reason == SAMPLE_RULES["R-01"]["defaultReason"]
