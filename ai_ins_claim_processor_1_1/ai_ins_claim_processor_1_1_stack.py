from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_s3 as s3,
)
from constructs import Construct


class AiInsClaimProcessor11Stack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # S3 bucket for claim documents and analysis results
        claims_bucket = s3.Bucket(
            self,
            "ClaimsBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # Lambda function
        process_claim_fn = _lambda.Function(
            self,
            "ProcessClaimFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("lambda/process_claim"),
            timeout=Duration.seconds(60),
            memory_size=256,
            environment={
                "CLAIMS_BUCKET": claims_bucket.bucket_name,
                "BEDROCK_MODEL_ID": "amazon.nova-lite-v1:0",
            },
        )

        # Grant Lambda read/write access to S3
        claims_bucket.grant_read_write(process_claim_fn)

        # Grant Lambda permission to invoke the Bedrock model
        process_claim_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    "arn:aws:bedrock:*::foundation-model/amazon.nova-lite-v1:0"
                ],
            )
        )