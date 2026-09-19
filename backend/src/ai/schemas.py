"""JSON Schemas for Amazon Bedrock structured output generation.

Strictly adheres to IMPLEMENTATION.md §7 (AI Implementation).
These schemas are supplied to the Bedrock Converse API via outputConfig.textFormat
to guarantee 100% deterministic, typed JSON responses without chat filler.
"""

import json
from typing import Dict, Any

# =====================================================================
# Call 1: Extraction Output Schema
# =====================================================================

EXTRACTION_SCHEMA_DICT: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "roleConfirmed": {
            "type": "boolean",
            "description": "True if the document content visually and textually matches its declared role.",
        },
        "documentQuality": {
            "type": "string",
            "enum": ["GOOD", "POOR"],
            "description": "GOOD if the scan is clear and readable, POOR if blurry, truncated, or low resolution.",
        },
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fieldKey": {
                        "type": "string",
                        "description": "The exact canonical fieldKey requested in the prompt.",
                    },
                    "rawValue": {
                        "type": ["string", "null"],
                        "description": "The verbatim raw text extracted from the document, or null if not found.",
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "Model confidence in the extracted value from 0.0 to 1.0.",
                    },
                    "evidence": {
                        "type": ["string", "null"],
                        "description": "Exact text snippet or line from the document where the value was found.",
                    },
                },
                "required": ["fieldKey", "rawValue", "confidence", "evidence"],
                "additionalProperties": False,
            },
        },
        "notes": {
            "type": ["string", "null"],
            "description": "Optional concise technical notes about unusual formatting, stamps, or watermarks.",
        },
    },
    "required": ["roleConfirmed", "documentQuality", "fields"],
    "additionalProperties": False,
}


# =====================================================================
# Call 2: Adjudication Output Schema
# =====================================================================

ADJUDICATION_SCHEMA_DICT: Dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "findingId": {
                        "type": "string",
                        "description": "The stable finding ID provided in the prompt (e.g. 'f1', 'f2').",
                    },
                    "isRealConflict": {
                        "type": "boolean",
                        "description": "True if this is a genuine disqualifying contradiction; False if benign transliteration/formatting variant.",
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "Confidence in the judgment decision from 0.0 to 1.0.",
                    },
                    "reason": {
                        "type": "string",
                        "maxLength": 320,
                        "description": "Concise 1-2 sentence explanation written for a student explaining the issue.",
                    },
                    "fixInstruction": {
                        "type": "string",
                        "maxLength": 320,
                        "description": "Specific single actionable step naming the exact document to verify or replace.",
                    },
                    "rankHint": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Relative priority ranking for the student to address (1 = most critical).",
                    },
                },
                "required": [
                    "findingId",
                    "isRealConflict",
                    "confidence",
                    "reason",
                    "fixInstruction",
                    "rankHint",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}


def get_extraction_output_config() -> Dict[str, Any]:
    """Return the outputConfig structure required by the Bedrock Converse API for extraction."""
    return {
        "textFormat": {
            "structure": {
                "jsonSchema": {
                    "name": "DocumentExtraction",
                    "schema": json.dumps(EXTRACTION_SCHEMA_DICT),
                }
            }
        }
    }


def get_adjudication_output_config() -> Dict[str, Any]:
    """Return the outputConfig structure required by the Bedrock Converse API for adjudication."""
    return {
        "textFormat": {
            "structure": {
                "jsonSchema": {
                    "name": "FindingAdjudication",
                    "schema": json.dumps(ADJUDICATION_SCHEMA_DICT),
                }
            }
        }
    }
