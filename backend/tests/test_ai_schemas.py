"""Unit tests for Bedrock structured output schemas and AI prompt generators.

Verifies schema validities, Bedrock outputConfig formatting, and prompt assembly.
"""

import json

from backend.src.ai.schemas import (
    EXTRACTION_SCHEMA_DICT,
    ADJUDICATION_SCHEMA_DICT,
    get_extraction_output_config,
    get_adjudication_output_config,
)
from backend.src.ai.extract import build_extraction_prompt
from backend.src.ai.adjudicate import build_adjudication_prompt
from backend.src.core.models import (
    Snapshot,
    SnapshotRow,
    Finding,
    Severity,
    FindingCategory,
    DocumentRole,
    DocumentReference,
    DocumentExtraction,
)


def test_schemas_and_output_configs():
    """Verify JSON Schemas are valid and outputConfig structures match Bedrock specs."""
    assert EXTRACTION_SCHEMA_DICT["type"] == "object"
    assert "roleConfirmed" in EXTRACTION_SCHEMA_DICT["properties"]
    assert "documentQuality" in EXTRACTION_SCHEMA_DICT["properties"]
    assert "fields" in EXTRACTION_SCHEMA_DICT["properties"]

    extract_config = get_extraction_output_config()
    assert "textFormat" in extract_config
    json_schema_obj = extract_config["textFormat"]["structure"]["jsonSchema"]
    assert json_schema_obj["name"] == "DocumentExtraction"
    # Verify the schema string is valid JSON
    parsed_schema = json.loads(json_schema_obj["schema"])
    assert parsed_schema["type"] == "object"

    adjudicate_config = get_adjudication_output_config()
    assert "textFormat" in adjudicate_config
    adj_schema_obj = adjudicate_config["textFormat"]["structure"]["jsonSchema"]
    assert adj_schema_obj["name"] == "FindingAdjudication"
    parsed_adj = json.loads(adj_schema_obj["schema"])
    assert "results" in parsed_adj["properties"]


def test_build_extraction_prompt():
    """Verify extraction prompt incorporates role, target fields, queries, and text."""
    sys_prompt, user_prompt = build_extraction_prompt(
        role="AADHAAR",
        query_answers={"What is the name?": "ANTARJIT DAS"},
        form_kvs={"DOB": "12/03/2004"},
        raw_lines=["Government of India", "Name: ANTARJIT DAS"],
    )

    assert "specialized document extraction engine" in sys_prompt
    assert "Document Role: AADHAAR" in user_prompt
    assert "student_name" in user_prompt
    assert "ANTARJIT DAS" in user_prompt
    assert "12/03/2004" in user_prompt


def test_build_adjudication_prompt():
    """Verify adjudication prompt frames the Nodal Officer perspective and includes findings."""
    snapshot = Snapshot(
        rows=[
            SnapshotRow(
                fieldKey="student_name",
                label="Student Name",
                valuesByRole={"AADHAAR": "ANTARJIT DAS", "MARKSHEET": "ANTARJEET DASS"},
                canonicalValue="ANTARJIT DAS",
                canonicalSource="AADHAAR",
                hasDisagreement=True,
            )
        ]
    )

    finding = Finding(
        findingId="f1",
        ruleId="R-01",
        title="Student name mismatch",
        severity=Severity.RED,
        category=FindingCategory.IDENTITY,
        documents=[
            DocumentReference(role=DocumentRole.AADHAAR, value="ANTARJIT DAS"),
            DocumentReference(role=DocumentRole.MARKSHEET, value="ANTARJEET DASS"),
        ],
        reason="Names disagree across documents.",
        fixInstruction="Ensure records match.",
        confidence=0.95,
        source="MMNBA 2026 Guidelines",
        needsAdjudication=True,
    )

    sys_prompt, user_prompt = build_adjudication_prompt(snapshot, [finding])

    assert "Institute Nodal Officer" in sys_prompt
    assert "ANTARJIT DAS" in user_prompt
    assert "ANTARJEET DASS" in user_prompt
    assert "Finding ID: f1" in user_prompt
    assert "Rule ID: R-01" in user_prompt


def test_simulated_ai_extraction_response():
    """Verify that a mock JSON response from Bedrock conforms to DocumentExtraction."""
    mock_bedrock_json = {
        "roleConfirmed": True,
        "documentQuality": "GOOD",
        "fields": [
            {
                "fieldKey": "student_name",
                "rawValue": "ANTARJIT DAS",
                "confidence": 0.98,
                "evidence": "Name: ANTARJIT DAS",
            }
        ],
        "notes": "Clear scan",
    }

    extraction = DocumentExtraction.model_validate(mock_bedrock_json)
    assert extraction.roleConfirmed is True
    assert extraction.fields[0].rawValue == "ANTARJIT DAS"
