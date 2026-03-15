import aws_cdk as core
import aws_cdk.assertions as assertions

from ai_ins_claim_processor_1_1.ai_ins_claim_processor_1_1_stack import AiInsClaimProcessor11Stack

# example tests. To run these tests, uncomment this file along with the example
# resource in ai_ins_claim_processor_1_1/ai_ins_claim_processor_1_1_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = AiInsClaimProcessor11Stack(app, "ai-ins-claim-processor-1-1")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
