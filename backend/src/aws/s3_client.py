"""S3 thin client for Defect Guard.

Handles:
- Presigned PUT URL generation (5-minute TTL) with bound ContentType.
- HeadObject authoritative metadata retrieval (ContentLength, ContentType).
- Read raw bytes or string content if needed.
"""

import os
from typing import Dict, Any, Optional
import boto3
from botocore.config import Config

DEFAULT_REGION = os.environ.get("AWS_REGION", "ap-south-1")
DEFAULT_BUCKET = os.environ.get("UPLOADS_BUCKET", "defect-guard-uploads")
PRESIGNED_URL_EXPIRATION_SECONDS = 300  # 5 minutes


def get_s3_client(region_name: str = DEFAULT_REGION):
    """Factory to get an S3 client with standard retry configuration."""
    return boto3.client(
        "s3",
        region_name=region_name,
        config=Config(retries={"max_attempts": 3, "mode": "standard"}),
    )


def generate_presigned_upload_url(
    packet_id: str,
    document_id: str,
    file_name: str,
    content_type: str,
    bucket_name: Optional[str] = None,
    client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Generate a presigned PUT URL for browser uploads directly to S3.

    Args:
        packet_id: Unique identifier of the scholarship packet.
        document_id: Unique identifier for this uploaded document slot.
        file_name: Original user filename (used to extract file extension).
        content_type: MIME type (application/pdf, image/jpeg, image/png).
        bucket_name: S3 bucket name (defaults to env var UPLOADS_BUCKET).
        client: Optional boto3 client override.

    Returns:
        Dict with 'uploadUrl', 'objectKey', and 'expiresInSeconds'.
    """
    s3 = client or get_s3_client()
    bucket = bucket_name or DEFAULT_BUCKET

    ext = ""
    if "." in file_name:
        parts = file_name.rsplit(".", 1)
        if len(parts) > 1:
            ext = "." + parts[1].lower()

    object_key = f"packets/{packet_id}/{document_id}{ext}"

    url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": bucket,
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=PRESIGNED_URL_EXPIRATION_SECONDS,
    )

    return {
        "uploadUrl": url,
        "objectKey": object_key,
        "expiresInSeconds": PRESIGNED_URL_EXPIRATION_SECONDS,
    }


def get_authoritative_metadata(
    object_key: str,
    bucket_name: Optional[str] = None,
    client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Fetch authoritative metadata (ContentLength, ContentType) via S3 HeadObject.

    Never trust user-reported file sizes from browser headers.
    """
    s3 = client or get_s3_client()
    bucket = bucket_name or DEFAULT_BUCKET

    resp = s3.head_object(Bucket=bucket, Key=object_key)
    return {
        "contentLength": resp.get("ContentLength", 0),
        "contentType": resp.get("ContentType", "application/octet-stream"),
        "eTag": resp.get("ETag", "").strip('"'),
    }
