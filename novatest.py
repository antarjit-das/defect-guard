"""
novatest.py
AWS Bedrock Nova 2 Lite diagnostic test.

Purpose:
    Diagnose WHY a Bedrock model invocation is failing.

Checks:
    1. Python / boto3 environment
    2. AWS caller identity
    3. Bedrock control-plane connectivity
    4. Foundation model discovery
    5. Nova model metadata
    6. Nova 2 Lite availability / authorization
    7. Inference profiles available in the region
    8. Whether the expected Nova 2 Lite profile exists
    9. IAM permissions required for invocation
    10. Converse API invocation
    11. Detailed error classification

This file is intended for local debugging only.
DO NOT commit credentials or secrets.
"""

import os
import sys
import json
import time
import traceback
import platform
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError, BotoCoreError


# ============================================================
# CONFIG
# ============================================================

REGION = os.environ.get("AWS_REGION", "ap-south-1")

# The model we actually want to test.
MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "apac.amazon.nova-micro-v1:0",
)

PROMPT = (
    "Hello Nova. What is 15 + 27? "
    "Give the answer and one short greeting."
)

MAX_TOKENS = 200
TEMPERATURE = 0.2


# ============================================================
# OUTPUT HELPERS
# ============================================================

def section(title):
    print("\n")
    print("=" * 72)
    print(title)
    print("=" * 72)


def ok(message):
    print(f"[OK]      {message}")


def info(message):
    print(f"[INFO]    {message}")


def warn(message):
    print(f"[WARNING] {message}")


def fail(message):
    print(f"[FAILED]  {message}")


def dump_json(data):
    print(json.dumps(data, indent=2, default=str))


def error_details(exc):
    """
    Extract useful AWS error information without hiding details.
    """
    if isinstance(exc, ClientError):
        response = exc.response or {}
        error = response.get("Error", {})

        return {
            "exception_type": type(exc).__name__,
            "error_code": error.get("Code"),
            "error_message": error.get("Message"),
            "http_status": response.get("ResponseMetadata", {}).get(
                "HTTPStatusCode"
            ),
            "request_id": response.get("ResponseMetadata", {}).get(
                "RequestId"
            ),
        }

    return {
        "exception_type": type(exc).__name__,
        "error_code": None,
        "error_message": str(exc),
        "http_status": None,
        "request_id": None,
    }


# ============================================================
# 1. ENVIRONMENT
# ============================================================

def check_environment():
    section("1. ENVIRONMENT")

    print(f"Python       : {platform.python_version()}")
    print(f"Platform     : {platform.platform()}")
    print(f"boto3        : {__import__('boto3').__version__}")
    print(f"botocore     : {__import__('botocore').__version__}")
    print(f"AWS Region   : {REGION}")
    print(f"Model ID     : {MODEL_ID}")
    print(f"Timestamp    : {datetime.now(timezone.utc).isoformat()}")

    if os.environ.get("AWS_PROFILE"):
        print(f"AWS Profile  : {os.environ['AWS_PROFILE']}")
    else:
        print("AWS Profile  : <default credential chain>")

    print(f"AWS_ACCESS_KEY_ID present: "
          f"{bool(os.environ.get('AWS_ACCESS_KEY_ID'))}")

    print(f"AWS_SESSION_TOKEN present: "
          f"{bool(os.environ.get('AWS_SESSION_TOKEN'))}")


# ============================================================
# 2. AWS IDENTITY
# ============================================================

def check_identity(sts):
    section("2. AWS IDENTITY")

    try:
        response = sts.get_caller_identity()

        ok("STS authentication works.")

        print(f"Account : {response.get('Account')}")
        print(f"ARN     : {response.get('Arn')}")
        print(f"UserId  : {response.get('UserId')}")

        return True

    except Exception as exc:
        fail("Could not authenticate with AWS.")

        details = error_details(exc)
        dump_json(details)

        return False


# ============================================================
# 3. BEDROCK CONNECTIVITY
# ============================================================

def check_bedrock_connectivity(bedrock):
    section("3. BEDROCK CONTROL-PLANE CONNECTIVITY")

    try:
        response = bedrock.list_foundation_models(
            byProvider="Amazon"
        )

        models = response.get("modelSummaries", [])

        ok(f"Connected to Bedrock in {REGION}.")
        print(f"Amazon models returned: {len(models)}")

        nova_models = [
            m for m in models
            if "nova" in str(m.get("modelId", "")).lower()
        ]

        print(f"Nova models returned   : {len(nova_models)}")

        for model in nova_models:
            print(
                f"  - {model.get('modelId')} "
                f"| provider={model.get('providerName')} "
                f"| inference={model.get('inferenceTypesSupported')}"
            )

        return True

    except Exception as exc:
        fail("Bedrock control-plane request failed.")
        dump_json(error_details(exc))
        return False


# ============================================================
# 4. FIND NOVA MODELS
# ============================================================

def find_nova_models(bedrock):
    section("4. NOVA MODEL DISCOVERY")

    try:
        response = bedrock.list_foundation_models(
            byProvider="Amazon"
        )

        models = response.get("modelSummaries", [])

        for model in models:
            model_id = model.get("modelId", "")

            if "nova" in model_id.lower():
                print("\nModel:")
                print(f"  ID              : {model_id}")
                print(f"  ARN             : {model.get('modelArn')}")
                print(f"  Provider        : {model.get('providerName')}")
                print(f"  Input modalities: {model.get('inputModalities')}")
                print(f"  Output modalities: {model.get('outputModalities')}")
                print(
                    f"  Inference types : "
                    f"{model.get('inferenceTypesSupported')}"
                )

        return True

    except Exception as exc:
        fail("Could not discover foundation models.")
        dump_json(error_details(exc))
        return False


# ============================================================
# 5. FOUNDATION MODEL AVAILABILITY
# ============================================================

def check_model_availability(bedrock):
    section("5. FOUNDATION MODEL AVAILABILITY")

    # Check the actual base model rather than only the global profile.
    base_model_id = "amazon.nova-2-lite-v1:0"

    print(f"Checking: {base_model_id}")
    print()

    try:
        response = bedrock.get_foundation_model_availability(
            modelId=base_model_id
        )

        ok("AWS returned model availability information.")

        dump_json(response)

        return True

    except ClientError as exc:
        fail("AWS could not return foundation-model availability.")

        details = error_details(exc)
        dump_json(details)

        return False

    except Exception as exc:
        fail("Unexpected availability-check failure.")
        dump_json(error_details(exc))
        return False


# ============================================================
# 6. GET FOUNDATION MODEL DETAILS
# ============================================================

def check_model_details(bedrock):
    section("6. FOUNDATION MODEL DETAILS")

    base_model_id = "amazon.nova-2-lite-v1:0"

    try:
        response = bedrock.get_foundation_model(
            modelIdentifier=base_model_id
        )

        ok("Foundation model metadata is accessible.")

        model_details = response.get("modelDetails", response)

        print(f"Model ID: {model_details.get('modelId')}")
        print(f"Model ARN: {model_details.get('modelArn')}")
        print(f"Provider : {model_details.get('providerName')}")
        print(
            f"Inference types: "
            f"{model_details.get('inferenceTypesSupported')}"
        )

        return True

    except ClientError as exc:
        fail("Could not retrieve Nova 2 Lite metadata.")
        dump_json(error_details(exc))
        return False

    except Exception as exc:
        fail("Unexpected model-details failure.")
        dump_json(error_details(exc))
        return False


# ============================================================
# 7. LIST INFERENCE PROFILES
# ============================================================

def check_inference_profiles(bedrock):
    section("7. INFERENCE PROFILES")

    try:
        response = bedrock.list_inference_profiles(
            maxResults=100
        )

        profiles = response.get(
            "inferenceProfileSummaries",
            []
        )

        ok(f"Found {len(profiles)} inference profiles.")

        nova_profiles = []

        for profile in profiles:
            profile_id = profile.get(
                "inferenceProfileId",
                ""
            )

            profile_name = profile.get(
                "inferenceProfileName",
                ""
            )

            if "nova" in (
                f"{profile_id} {profile_name}"
            ).lower():
                nova_profiles.append(profile)

        print(f"Nova profiles: {len(nova_profiles)}")

        for profile in nova_profiles:
            print("\nNova inference profile:")
            print(
                f"  ID       : "
                f"{profile.get('inferenceProfileId')}"
            )
            print(
                f"  Name     : "
                f"{profile.get('inferenceProfileName')}"
            )
            print(
                f"  ARN      : "
                f"{profile.get('inferenceProfileArn')}"
            )
            print(
                f"  Status   : "
                f"{profile.get('status')}"
            )
            print(
                f"  Models   : "
                f"{profile.get('models')}"
            )

        return profiles

    except ClientError as exc:
        fail("Could not list inference profiles.")
        dump_json(error_details(exc))
        return []

    except Exception as exc:
        fail("Unexpected inference-profile failure.")
        dump_json(error_details(exc))
        return []


# ============================================================
# 8. CHECK TARGET PROFILE
# ============================================================

def inspect_target_profile(profiles):
    section("8. TARGET MODEL / PROFILE CHECK")

    target = MODEL_ID

    print(f"Target: {target}")
    print()

    matching = []

    for profile in profiles:
        profile_id = profile.get(
            "inferenceProfileId",
            ""
        )

        profile_arn = profile.get(
            "inferenceProfileArn",
            ""
        )

        if target in profile_id or target in profile_arn:
            matching.append(profile)

    if matching:
        ok("Target inference profile appears in ListInferenceProfiles.")

        for profile in matching:
            dump_json(profile)

        return True

    warn(
        "Target model/profile was NOT found in "
        "ListInferenceProfiles."
    )

    print()
    print(
        "This does not automatically mean invocation is impossible, "
        "because the target may be a base model rather than an "
        "inference profile."
    )

    return False


# ============================================================
# 9. IAM SIMULATION / PERMISSION CHECK
# ============================================================

def check_iam_permissions(sts):
    section("9. IAM PERMISSION CHECK")

    try:
        identity = sts.get_caller_identity()

        arn = identity.get("Arn", "")

        print(f"Current identity: {arn}")

        if ":user/" in arn:
            iam = boto3.client(
                "iam",
                region_name=REGION
            )

            username = arn.split(":user/")[-1]

            print(f"IAM user: {username}")

            try:
                response = iam.simulate_principal_policy(
                    PolicySourceArn=arn,
                    ActionNames=[
                        "bedrock:Converse",
                        "bedrock:InvokeModel",
                    ],
                    ResourceArns=[
                        "*"
                    ],
                )

                results = response.get(
                    "EvaluationResults",
                    []
                )

                for result in results:
                    print(
                        f"{result.get('EvalActionName')}: "
                        f"{result.get('EvalDecision')}"
                    )

                return True

            except ClientError as exc:
                warn(
                    "IAM policy simulation could not be performed. "
                    "This is common when the current identity is a role."
                )
                dump_json(error_details(exc))
                return False

        else:
            warn(
                "Current identity is not a direct IAM user. "
                "Skipping IAM policy simulation."
            )

            print(
                "The STS ARN above tells us whether you're using "
                "an assumed role, SSO role, etc."
            )

            return False

    except Exception as exc:
        fail("IAM diagnostic failed.")
        dump_json(error_details(exc))
        return False


# ============================================================
# 10. CONVERSE TEST
# ============================================================

def test_converse(runtime):
    section("10. BEDROCK CONVERSE INVOCATION")

    print(f"Region   : {REGION}")
    print(f"Model ID : {MODEL_ID}")
    print(f"Prompt   : {PROMPT}")

    print()
    info("Sending ONE inference request...")

    start = time.time()

    try:
        response = runtime.converse(
            modelId=MODEL_ID,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "text": PROMPT
                        }
                    ],
                }
            ],
            inferenceConfig={
                "maxTokens": MAX_TOKENS,
                "temperature": TEMPERATURE,
            },
        )

        elapsed = time.time() - start

        ok(f"Converse succeeded in {elapsed:.2f}s.")

        print()

        output = response.get("output", {})
        message = output.get("message", {})
        content = message.get("content", [])

        response_text = ""

        for block in content:
            if "text" in block:
                response_text += block["text"]

        print("Response:")
        print(response_text)

        print()
        print(f"Stop reason: {response.get('stopReason')}")

        usage = response.get("usage", {})

        print(
            f"Input tokens : "
            f"{usage.get('inputTokens')}"
        )

        print(
            f"Output tokens: "
            f"{usage.get('outputTokens')}"
        )

        return True

    except ClientError as exc:
        elapsed = time.time() - start

        fail(
            f"Converse failed after {elapsed:.2f}s."
        )

        details = error_details(exc)

        print()
        print("AWS ERROR DETAILS:")
        dump_json(details)

        classify_error(details)

        return False

    except Exception as exc:
        elapsed = time.time() - start

        fail(
            f"Unexpected Converse failure after "
            f"{elapsed:.2f}s."
        )

        print()
        traceback.print_exc()

        return False


# ============================================================
# 11. ERROR CLASSIFICATION
# ============================================================

def classify_error(details):
    section("ERROR CLASSIFICATION")

    code = details.get("error_code")
    message = (
        details.get("error_message") or ""
    ).lower()

    print(f"AWS error code: {code}")
    print(f"AWS message   : {details.get('error_message')}")

    print()

    if code == "AccessDeniedException":
        print(
            "LIKELY CATEGORY: IAM permission denial."
        )
        print(
            "Check bedrock:Converse / bedrock:InvokeModel "
            "permissions and any explicit Deny."
        )

    elif code == "ResourceNotFoundException":
        print(
            "LIKELY CATEGORY: Model/profile not available "
            "under this identifier or region."
        )

    elif code == "ValidationException":
        if "operation not allowed" in message:
            print(
                "LIKELY CATEGORY: Bedrock operation/model "
                "availability restriction."
            )
            print()
            print(
                "Important: this is NOT the same as a normal "
                "IAM AccessDeniedException."
            )
            print()
            print(
                "Investigate:"
            )
            print(
                "  1. Exact model ID"
            )
            print(
                "  2. Inference profile availability"
            )
            print(
                "  3. Source region"
            )
            print(
                "  4. Model entitlement/authorization"
            )
            print(
                "  5. Account restrictions"
            )
            print(
                "  6. Whether the model supports this API"
            )

        else:
            print(
                "LIKELY CATEGORY: Request validation problem."
            )

    elif code == "ThrottlingException":
        print(
            "LIKELY CATEGORY: Request throttling."
        )

    elif code == "ModelNotReadyException":
        print(
            "LIKELY CATEGORY: Model is temporarily unavailable."
        )

    elif code == "ServiceQuotaExceededException":
        print(
            "LIKELY CATEGORY: Bedrock service quota."
        )

    else:
        print(
            "CATEGORY UNKNOWN."
        )
        print(
            "Use the AWS error code/message above for "
            "further diagnosis."
        )


# ============================================================
# MAIN
# ============================================================

def main():

    section("AWS BEDROCK NOVA 2 LITE DIAGNOSTIC")

    print(
        "This diagnostic performs discovery checks first "
        "and sends ONE inference request at the end."
    )

    print(
        "Target model:"
    )
    print(
        f"  {MODEL_ID}"
    )

    print(
        f"Region:"
    )
    print(
        f"  {REGION}"
    )

    # --------------------------------------------------------
    # Clients
    # --------------------------------------------------------

    try:
        session = boto3.Session(
            region_name=REGION
        )

        sts = session.client("sts")
        bedrock = session.client("bedrock")
        runtime = session.client("bedrock-runtime")

    except Exception as exc:
        fail("Could not create AWS clients.")
        dump_json(error_details(exc))
        return 1

    # --------------------------------------------------------
    # Checks
    # --------------------------------------------------------

    check_environment()

    identity_ok = check_identity(sts)

    if not identity_ok:
        print()
        fail(
            "Stopping because AWS credentials are not working."
        )
        return 1

    check_bedrock_connectivity(bedrock)

    find_nova_models(bedrock)

    check_model_availability(bedrock)

    check_model_details(bedrock)

    profiles = check_inference_profiles(bedrock)

    inspect_target_profile(profiles)

    check_iam_permissions(sts)

    # --------------------------------------------------------
    # Actual inference
    # --------------------------------------------------------

    success = test_converse(runtime)

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

    section("FINAL RESULT")

    if success:
        ok(
            "Nova 2 Lite inference is working."
        )
        return 0

    fail(
        "Nova 2 Lite inference failed."
    )

    print()
    print(
        "The diagnostic information above should identify "
        "which layer is failing."
    )

    return 1


if __name__ == "__main__":
    sys.exit(main())