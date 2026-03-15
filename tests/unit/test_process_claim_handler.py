"""
Unit tests for the process_claim Lambda handler.
Uses moto to mock S3 and unittest.mock to mock Bedrock.

Run from the project root:
    pytest tests/unit/test_process_claim_handler.py -v
"""

import json
import os
import sys
from io import BytesIO
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

# Make the lambda directory importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda/process_claim"))

BUCKET_NAME = "test-claims-bucket"
MODEL_ID = "amazon.nova-lite-v1:0"

SAMPLE_CLAIM = """
Claimant: Jane Doe
Policy Number: POL-20240101
Date of Incident: 2024-01-15
Type: Auto Accident
Description: Vehicle rear-ended at a traffic stop. Damage to rear bumper and trunk.
Estimated Repair Cost: $4,200
"""

SAMPLE_ANALYSIS = "Claim summary: Auto accident with rear-end collision. Recommended action: approve."


def _make_bedrock_response(text: str) -> MagicMock:
    """Build a mock Bedrock invoke_model response matching Nova's response format."""
    body = json.dumps({
        "output": {
            "message": {
                "content": [{"text": text}]
            }
        }
    }).encode("utf-8")
    mock_response = MagicMock()
    mock_response["body"].read.return_value = body
    return mock_response


@mock_aws
class TestProcessClaimHandler:

    def setup_method(self):
        """Create S3 bucket and upload a sample claim before each test."""
        os.environ["CLAIMS_BUCKET"] = BUCKET_NAME
        os.environ["BEDROCK_MODEL_ID"] = MODEL_ID

        self.s3 = boto3.client("s3", region_name="us-east-1")
        self.s3.create_bucket(Bucket=BUCKET_NAME)
        self.s3.put_object(
            Bucket=BUCKET_NAME,
            Key="claims/sample-claim.txt",
            Body=SAMPLE_CLAIM.encode("utf-8"),
        )

        # Re-import handler after env vars are set so module-level clients use moto
        import importlib
        import handler as h
        importlib.reload(h)
        self.handler = h

    @patch("handler.bedrock_client")
    def test_successful_claim_processing(self, mock_bedrock):
        """Happy path: claim is read from S3, analyzed by Bedrock, result saved to S3."""
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(SAMPLE_ANALYSIS)

        event = {"key": "claims/sample-claim.txt"}
        response = self.handler.lambda_handler(event, {})

        assert response["statusCode"] == 200
        assert response["result_key"] == "results/claims/sample-claim.txt"
        assert response["analysis"] == SAMPLE_ANALYSIS

        # Verify result was written to S3
        result = self.s3.get_object(Bucket=BUCKET_NAME, Key="results/claims/sample-claim.txt")
        saved_text = result["Body"].read().decode("utf-8")
        assert saved_text == SAMPLE_ANALYSIS

    @patch("handler.bedrock_client")
    def test_bedrock_called_with_correct_payload(self, mock_bedrock):
        """Verify the Bedrock request body matches Nova's expected format."""
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(SAMPLE_ANALYSIS)

        self.handler.lambda_handler({"key": "claims/sample-claim.txt"}, {})

        call_kwargs = mock_bedrock.invoke_model.call_args[1]
        assert call_kwargs["modelId"] == MODEL_ID
        body = json.loads(call_kwargs["body"])
        assert "messages" in body
        assert body["messages"][0]["role"] == "user"
        assert SAMPLE_CLAIM.strip() in body["messages"][0]["content"][0]["text"]

    @patch("handler.bedrock_client")
    def test_bucket_override_in_event(self, mock_bedrock):
        """Event can specify a different bucket to read from."""
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(SAMPLE_ANALYSIS)

        # Upload claim to a second bucket
        self.s3.create_bucket(Bucket="other-bucket")
        self.s3.put_object(
            Bucket="other-bucket",
            Key="claims/other-claim.txt",
            Body=b"Other claim content",
        )

        event = {"key": "claims/other-claim.txt", "bucket": "other-bucket"}
        response = self.handler.lambda_handler(event, {})

        assert response["statusCode"] == 200

    def test_missing_key_raises_error(self):
        """Missing 'key' in event payload should raise KeyError."""
        with pytest.raises(KeyError):
            self.handler.lambda_handler({}, {})

    @patch("handler.bedrock_client")
    def test_nonexistent_s3_key_raises_error(self, mock_bedrock):
        """Requesting a key that doesn't exist in S3 should raise an exception."""
        from botocore.exceptions import ClientError
        with pytest.raises(ClientError):
            self.handler.lambda_handler({"key": "claims/does-not-exist.txt"}, {})
