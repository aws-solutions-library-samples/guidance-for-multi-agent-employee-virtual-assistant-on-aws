import aws_cdk as cdk
import os
import uuid
from employee_assistant_cdk.employee_assistant_stack import EmployeeAssistantStack

# Define static stack name
stack_name = "emp-virtual-assistant"

# Get UUID from environment (set by deploy.py)
uuid_value = os.environ.get("CDK_DEPLOY_UUID")
if not uuid_value:
    print("⚠️ WARNING: CDK_DEPLOY_UUID environment variable not set.")
    print("⚠️ This may cause resources to be replaced if deployed.")
    uuid_value = str(uuid.uuid4())

# Initialize CDK app
app = cdk.App()

# Create the main stack
EmployeeAssistantStack(
    app, 
    stack_name, 
    uuid_value=uuid_value,
    tavily_api_key=app.node.try_get_context("tavily_api_key") or "TAVILY_KEY_NOT_PROVIDED"
)

app.synth()