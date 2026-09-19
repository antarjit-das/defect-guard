"""Unit tests for AWS thin clients (S3, Textract, Bedrock, DynamoDB single-table).

Tests use mock/offline responses without requiring active AWS credentials.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from backend.src.aws.s3_client import generate_presigned_upload_url, get_authoritative_metadata, get_s3_client
from backend.src.aws.textract_client import parse_textract_blocks
from backend.src.aws.bedrock_client import invoke_bedrock_structured
from backend.src.aws.ddb import (
    floats_to_decimals,
    decimals_to_floats,
    create_packet_meta,
    get_packet_meta,
    get_full_packet,
    register_document,
    update_document_extraction,
    save_verdict,
    update_packet_status,
)
from backend.src.core.models import (
    DocumentItem,
    DocumentRole,
    DocumentStatus,
    Snapshot,
    Finding,
    Severity,
    FindingCategory,
    Verdict,
    VerdictBand,
    PacketStatus,
)


# =====================================================================
# S3 Client Tests
# =====================================================================


@patch("backend.src.aws.s3_client.boto3.client")
def test_s3_client_uses_regional_endpoint(mock_client):
    """Presigned URLs must not redirect from the global S3 endpoint."""
    get_s3_client("ap-south-1")

    assert mock_client.call_args.kwargs["endpoint_url"] == "https://s3.ap-south-1.amazonaws.com"

def test_s3_presigned_url_generation():
    """Verify presigned PUT URL generator formats the key and calls S3."""
    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://s3.mock/presigned-put"

    res = generate_presigned_upload_url(
        packet_id="pkt-123",
        document_id="doc-456",
        file_name="marksheet.pdf",
        content_type="application/pdf",
        bucket_name="test-bucket",
        client=mock_s3,
    )

    assert res["uploadUrl"] == "https://s3.mock/presigned-put"
    assert res["objectKey"] == "packets/pkt-123/doc-456.pdf"
    assert res["expiresInSeconds"] == 300

    mock_s3.generate_presigned_url.assert_called_once_with(
        ClientMethod="put_object",
        Params={
            "Bucket": "test-bucket",
            "Key": "packets/pkt-123/doc-456.pdf",
            "ContentType": "application/pdf",
        },
        ExpiresIn=300,
    )


def test_s3_head_object_authoritative_metadata():
    """Verify head_object retrieves ContentLength and ContentType."""
    mock_s3 = MagicMock()
    mock_s3.head_object.return_value = {
        "ContentLength": 204800,
        "ContentType": "image/jpeg",
        "ETag": '"abc123etag"',
    }

    meta = get_authoritative_metadata("packets/pkt-1/doc-1.jpg", bucket_name="my-bucket", client=mock_s3)
    assert meta["contentLength"] == 204800
    assert meta["contentType"] == "image/jpeg"
    assert meta["eTag"] == "abc123etag"


# =====================================================================
# Textract Client Parser Tests
# =====================================================================

def test_textract_parse_blocks():
    """Verify parser extracts QUERY_RESULT, KEY_VALUE_SET, and LINE blocks."""
    mock_response = {
        "Blocks": [
            {"Id": "b1", "BlockType": "PAGE", "Page": 1},
            {
                "Id": "q1",
                "BlockType": "QUERY",
                "Query": {"Text": "What is the name?"},
                "Relationships": [{"Type": "ANSWER", "Ids": ["ans1"]}],
            },
            {"Id": "ans1", "BlockType": "QUERY_RESULT", "Text": "ANTARJIT DAS"},
            {
                "Id": "k1",
                "BlockType": "KEY_VALUE_SET",
                "EntityTypes": ["KEY"],
                "Relationships": [{"Type": "CHILD", "Ids": ["w1"]}, {"Type": "VALUE", "Ids": ["v1"]}],
            },
            {"Id": "w1", "BlockType": "WORD", "Text": "DOB:"},
            {
                "Id": "v1",
                "BlockType": "KEY_VALUE_SET",
                "EntityTypes": ["VALUE"],
                "Relationships": [{"Type": "CHILD", "Ids": ["w2"]}],
            },
            {"Id": "w2", "BlockType": "WORD", "Text": "12/03/2004"},
            {"Id": "l1", "BlockType": "LINE", "Text": "Government of Assam", "Confidence": 99.5},
        ]
    }

    parsed = parse_textract_blocks(mock_response)
    assert parsed["query_answers"]["What is the name?"] == "ANTARJIT DAS"
    assert parsed["form_kvs"]["DOB:"] == "12/03/2004"
    assert "Government of Assam" in parsed["raw_lines"]
    assert parsed["mean_confidence"] > 0.99
    assert parsed["page_count"] == 1


# =====================================================================
# Bedrock Client Tests
# =====================================================================

def test_bedrock_converse_invocation_success():
    """Verify converse API invocation parses JSON message output."""
    mock_bedrock = MagicMock()
    mock_bedrock.converse.return_value = {
        "output": {
            "message": {
                "content": [{"text": '{"results": []}'}]
            }
        }
    }

    text = invoke_bedrock_structured(
        system_prompt="Test sys",
        user_prompt="Test user",
        output_config={"textFormat": {}},
        client=mock_bedrock,
    )

    assert text == '{"results": []}'
    mock_bedrock.converse.assert_called_once()


# =====================================================================
# DynamoDB Single-Table Client Tests
# =====================================================================

def test_dynamodb_serialization_helpers():
    """Verify float <-> Decimal conversions for DynamoDB types."""
    data = {"score": 40, "confidence": 0.95, "items": [{"val": 1.25}]}
    converted = floats_to_decimals(data)
    assert isinstance(converted["confidence"], Decimal)
    assert converted["confidence"] == Decimal("0.95")

    restored = decimals_to_floats(converted)
    assert restored["confidence"] == 0.95
    assert restored["score"] == 40


def test_dynamodb_single_table_operations():
    """Verify AP1 to AP5 against a mocked DynamoDB Table."""
    mock_table = MagicMock()
    mock_ddb = MagicMock()
    mock_ddb.Table.return_value = mock_table

    # 1. Create packet meta
    meta = create_packet_meta("pkt-999", table_name="TestTable", resource=mock_ddb)
    assert meta["pk"] == "PACKET#pkt-999"
    assert meta["sk"] == "META"
    mock_table.put_item.assert_called()

    # 2. Register document (AP3)
    doc = DocumentItem(
        documentId="doc-1",
        role=DocumentRole.AADHAAR,
        fileName="aadhaar.pdf",
        contentType="application/pdf",
        sizeBytes=100000,
        status=DocumentStatus.UPLOADED,
    )
    register_document("pkt-999", doc, table_name="TestTable", resource=mock_ddb)
    mock_table.put_item.assert_called()

    # 3. Store extraction (AP4)
    update_document_extraction(
        "pkt-999",
        "doc-1",
        extraction_dict={"roleConfirmed": True, "fields": []},
        status=DocumentStatus.EXTRACTED,
        table_name="TestTable",
        resource=mock_ddb,
    )
    mock_table.update_item.assert_called()

    # 4. Save verdict (AP5)
    verdict = Verdict(
        checkRunId="chk-1",
        snapshot=Snapshot(rows=[]),
        findings=[
            Finding(
                findingId="f1",
                ruleId="R-01",
                title="Mismatch",
                severity=Severity.RED,
                category=FindingCategory.IDENTITY,
                reason="Discrepancy",
                fixInstruction="Fix doc",
                source="Manual",
            )
        ],
        score=75,
        band=VerdictBand.RISKY,
        scoreArithmetic="100 - 25 = 75",
        createdAt="2026-09-19T00:00:00Z",
    )
    mock_table.get_item.return_value = {"Item": {"latestVerdictScore": 40}}
    save_verdict("pkt-999", verdict, table_name="TestTable", resource=mock_ddb)
    mock_table.put_item.assert_called()


def test_dynamodb_get_full_packet():
    """Verify AP2 query reconstitutes full Packet Pydantic object."""
    mock_table = MagicMock()
    mock_ddb = MagicMock()
    mock_ddb.Table.return_value = mock_table

    mock_table.query.return_value = {
        "Items": [
            {
                "pk": "PACKET#pkt-123",
                "sk": "META",
                "packetId": "pkt-123",
                "schemeId": "NIJUT_BABU_2026",
                "status": "CHECKED",
                "createdAt": "2026-09-19T00:00:00Z",
                "updatedAt": "2026-09-19T00:01:00Z",
                "previousScore": Decimal("40"),
            },
            {
                "pk": "PACKET#pkt-123",
                "sk": "DOC#doc-1",
                "documentId": "doc-1",
                "role": "AADHAAR",
                "fileName": "aadhaar.pdf",
                "contentType": "application/pdf",
                "sizeBytes": Decimal("150000"),
                "status": "EXTRACTED",
            },
            {
                "pk": "PACKET#pkt-123",
                "sk": "VERDICT#2026-09-19T00:01:00Z",
                "checkRunId": "chk-1",
                "snapshot": {"rows": []},
                "findings": [],
                "score": Decimal("100"),
                "band": "READY",
                "scoreArithmetic": "100 = 100",
                "ruleSetVersion": "NIJUT_BABU_2026@1",
                "aiStatus": "OK",
                "createdAt": "2026-09-19T00:01:00Z",
            },
        ]
    }

    pkt = get_full_packet("pkt-123", table_name="TestTable", resource=mock_ddb)
    assert pkt is not None
    assert pkt.packetId == "pkt-123"
    assert pkt.status == PacketStatus.CHECKED
    assert len(pkt.documents) == 1
    assert pkt.verdict is not None
    assert pkt.verdict.score == 100
    assert pkt.previousScore == 40
