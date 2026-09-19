"""Amazon Bedrock Runtime thin client for Defect Guard.

Uses the Bedrock Converse API with structured outputs (`outputConfig.textFormat`)
and Amazon Nova Pro (`apac.amazon.nova-pro-v1:0`).
Handles retries, exponential backoff for throttling, and gracefully returns raw text
or fallback indicators.
"""

import os
import time
import logging
from typing import Dict, Any, Optional
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

DEFAULT_REGION = os.environ.get("AWS_REGION", "ap-south-1")
DEFAULT_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "apac.amazon.nova-pro-v1:0",
)


def get_bedrock_client(region_name: str = DEFAULT_REGION):
    """Factory to get bedrock-runtime client."""
    return boto3.client(
        "bedrock-runtime",
        region_name=region_name,
        config=Config(retries={"max_attempts": 2, "mode": "standard"}),
    )


def invoke_bedrock_structured(
    system_prompt: str,
    user_prompt: str,
    output_config: Dict[str, Any],
    max_tokens: int = 2000,
    temperature: float = 0.0,
    model_id: Optional[str] = None,
    client: Optional[Any] = None,
) -> Optional[str]:
    """Invoke Amazon Bedrock Converse API with structured outputConfig.

    Includes retry with exponential backoff on ThrottlingException (1s, 3s, 7s).

    Args:
        system_prompt: Instructs model role, schema compliance, rules.
        user_prompt: Payload (OCR text / candidate findings).
        output_config: Dictionary containing textFormat -> structure -> jsonSchema.
        max_tokens: Limit on generation tokens.
        temperature: Set to 0.0 for deterministic output.
        model_id: Model ID / CRIS inference profile.
        client: Optional boto3 client.

    Returns:
        The raw text response from Bedrock (which is guaranteed JSON if successful),
        or None if all retries failed / model unaccessible.
    """
    br = client or get_bedrock_client()
    target_model = model_id or DEFAULT_MODEL_ID

    messages = [
        {
            "role": "user",
            "content": [{"text": user_prompt}],
        }
    ]

    system = [{"text": system_prompt}]

    inference_config = {
        "maxTokens": max_tokens,
        "temperature": temperature,
    }

    # Exponential backoff schedule: 1s, 3s, 7s
    delays = [1, 3, 7]
    for attempt, delay in enumerate(delays):
        try:
            logger.info("Invoking Bedrock model '%s' (attempt %d)...", target_model, attempt + 1)
            response = br.converse(
                modelId=target_model,
                messages=messages,
                system=system,
                inferenceConfig=inference_config,
                outputConfig=output_config,
            )

            output_message = response.get("output", {}).get("message", {})
            content_blocks = output_message.get("content", [])
            if len(content_blocks) > 0:
                text = content_blocks[0].get("text")
                return text
            return None

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            error_msg = e.response.get("Error", {}).get("Message", "")
            logger.warning("Bedrock ClientError [%s]: %s", error_code, error_msg)

            if error_code in ("ThrottlingException", "TooManyRequestsException"):
                time.sleep(delay)
                continue
            elif error_code in ("AccessDeniedException", "ResourceNotFoundException", "ValidationException"):
                logger.error("Non-retryable Bedrock error [%s]. Fast-failing to fallback.", error_code)
                return None
            else:
                logger.warning("Unexpected Bedrock error [%s]. Retrying if attempts remain.", error_code)
                time.sleep(delay)

        except Exception as ex:
            logger.error("Unexpected exception invoking Bedrock: %s", str(ex))
            time.sleep(delay)

    logger.warning("All Bedrock invocation attempts exhausted. Returning None for fallback.")
    return None
