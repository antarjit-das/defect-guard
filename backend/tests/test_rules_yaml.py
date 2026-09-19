"""Unit tests verifying the integrity, citations, and structure of NIJUT_BABU_2026.yaml.

Ensures that the scheme ruleset is valid YAML and matches legal specifications.
"""

from pathlib import Path
import yaml

from backend.src.core.models import Severity, FindingCategory

RULES_YAML_PATH = (
    Path(__file__).resolve().parent.parent / "src" / "core" / "rules" / "NIJUT_BABU_2026.yaml"
)


def test_yaml_syntax_and_scheme_metadata():
    """Verify that the ruleset YAML parses and contains all required scheme metadata."""
    assert RULES_YAML_PATH.exists(), f"Rule file not found at {RULES_YAML_PATH}"

    with open(RULES_YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["version"] == 1
    scheme = data["scheme"]
    assert scheme["id"] == "NIJUT_BABU_2026"
    assert scheme["incomeCeiling"] == 400_000
    assert len(scheme["mandatoryRoles"]) == 4
    assert set(scheme["mandatoryRoles"]) == {
        "AADHAAR",
        "INCOME_CERTIFICATE",
        "MARKSHEET",
        "BANK_PROOF",
    }
    assert scheme["maxFileBytes"] == 204_800


def test_all_11_rules_integrity():
    """Verify that all 11 rules are defined with valid fields, citations, and severities."""
    with open(RULES_YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    rules = data["rules"]
    assert len(rules) == 11

    expected_rule_ids = [f"R-{i:02d}" for i in range(1, 12)]
    rule_ids = [r["id"] for r in rules]
    assert rule_ids == expected_rule_ids

    allowed_severities = {s.value for s in Severity}
    allowed_categories = {c.value for c in FindingCategory}

    for rule in rules:
        assert "id" in rule
        assert "title" in rule
        assert "severity" in rule
        assert rule["severity"] in allowed_severities

        assert "category" in rule
        assert rule["category"] in allowed_categories

        assert "source" in rule and len(rule["source"]) > 10, f"Missing citation for {rule['id']}"
        assert "sourceUrl" in rule and rule["sourceUrl"].startswith("http")
        assert "defaultReason" in rule and len(rule["defaultReason"]) > 10
        assert "defaultFix" in rule and len(rule["defaultFix"]) > 10
        assert "inspects" in rule and len(rule["inspects"]) > 0


def test_specific_scheme_rules():
    """Verify specific legal constraints like R-06 (Male only) and R-07 (4 Lakh income ceiling)."""
    with open(RULES_YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    rules_by_id = {r["id"]: r for r in data["rules"]}

    # R-01: Name mismatch is RED and needs adjudication
    assert rules_by_id["R-01"]["severity"] == "RED"
    assert rules_by_id["R-01"]["needsAdjudication"] is True

    # R-06: Gender rule is RED
    assert rules_by_id["R-06"]["severity"] == "RED"
    assert "Male" in rules_by_id["R-06"]["defaultReason"]

    # R-07: Income ceiling is RED
    assert rules_by_id["R-07"]["severity"] == "RED"
    assert "4,00,000" in rules_by_id["R-07"]["defaultReason"]
