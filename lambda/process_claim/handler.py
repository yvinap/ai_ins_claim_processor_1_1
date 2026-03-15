import json
import os

import boto3

s3_client = boto3.client("s3")
bedrock_client = boto3.client("bedrock-runtime")

CLAIMS_BUCKET = os.environ["CLAIMS_BUCKET"]
BEDROCK_MODEL_ID = os.environ["BEDROCK_MODEL_ID"]


def lambda_handler(event, context):
    """
    Expected event payload:
    {
        "key": "claims/my-claim.txt",
        "bucket": "optional-override-bucket"  # optional
    }
    """
    key = event["key"]
    bucket = event.get("bucket", CLAIMS_BUCKET)

    # Read claim document from S3
    s3_response = s3_client.get_object(Bucket=bucket, Key=key)
    claim_text = s3_response["Body"].read().decode("utf-8")

    # Build prompt for Bedrock
    prompt = (
        "You are an insurance claim processor. Analyze the following insurance claim and provide:\n"
        "1. Claim summary\n"
        "2. Coverage assessment\n"
        "3. Recommended action (approve / deny / investigate)\n"
        "4. Justification\n\n"
        f"Claim:\n{claim_text}"
    )

    # Invoke Amazon Bedrock (Nova)
    bedrock_response = bedrock_client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "messages": [
                {"role": "user", "content": [{"text": prompt}]}
            ],
            "inferenceConfig": {
                "max_new_tokens": 1024,
            },
        }),
    )

    result_body = json.loads(bedrock_response["body"].read())
    analysis = result_body["output"]["message"]["content"][0]["text"]

    # Write analysis result back to S3
    result_key = f"results/{key}"
    s3_client.put_object(
        Bucket=CLAIMS_BUCKET,
        Key=result_key,
        Body=analysis.encode("utf-8"),
        ContentType="text/plain",
    )

    return {
        "statusCode": 200,
        "result_key": result_key,
        "analysis": analysis,
    }