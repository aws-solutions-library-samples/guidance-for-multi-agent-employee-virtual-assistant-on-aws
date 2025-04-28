import subprocess  # nosec B404 - used with security measures
import json
import os
import sys
import time
import uuid
import argparse
import logging
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("deploy")

# Find absolute paths for executables
AWS_PATH = shutil.which("aws")
CDK_PATH = shutil.which("cdk")
NPM_PATH = shutil.which("npm")

# Check if required executables exist
if not AWS_PATH or not CDK_PATH or not NPM_PATH:
    logger.error("Required executables not found. Please install AWS CLI, CDK, and NPM.")
    sys.exit(1)

def safe_run(cmd_list, **kwargs):
    """Run a command safely using subprocess."""
    kwargs['shell'] = False  # Always ensure shell=False for security
    return subprocess.run(cmd_list, **kwargs)  # nosec B603

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Deploy the employee virtual assistant stack')
    parser.add_argument('--tavily-api-key', required=False, 
                       help='Tavily API key (optional)', default="ENTER_YOUR_TAVILY_API_KEY")
    parser.add_argument('--region', required=False,
                       help='AWS region to deploy to')
    
    args = parser.parse_args()
    
    # If default value is used, inform the user
    if args.tavily_api_key == "ENTER_YOUR_TAVILY_API_KEY":
        logger.warning("No Tavily API key provided. Using placeholder value.")
        logger.warning("Search functionality won't work until you provide a valid Tavily API key.")
        logger.warning("You can deploy again later with --tavily-api-key YOUR_KEY")
    
    return args

def get_aws_region():
    """Get AWS region from environment or AWS config."""
    # First check environment variable
    env_region = os.environ.get('AWS_REGION')
    if env_region:
        logger.info(f"Found region in environment: {env_region}")
        return env_region
    
    # If not set in environment, check AWS CLI config
    region_info = safe_run(
        [AWS_PATH, "configure", "get", "region"],
        capture_output=True, text=True, check=False
    )
    config_region = region_info.stdout.strip()
    if config_region:
        logger.info(f"Found region in AWS config: {config_region}")
        return config_region
    
    # Default to us-west-2 if still not found
    default_region = "us-west-2"
    logger.info(f"No region found, defaulting to: {default_region}")
    return default_region

def get_uuid_from_stack(stack_name, region):
    """Get UUID from CloudFormation stack if it exists."""
    logger.info(f"Looking for existing stack: {stack_name} in region {region}")
    
    # Call AWS CLI to describe the stack
    stack_info = safe_run(
        [AWS_PATH, "cloudformation", "describe-stacks", "--stack-name", stack_name, "--region", region],
        capture_output=True, text=True, check=False, env={"AWS_REGION": region, **os.environ}
    )
    
    # Check if stack exists
    if stack_info.returncode != 0:
        logger.info(f"Stack {stack_name} not found in region {region}")
        return None
    
    # Parse stack outputs to find UUID output
    try:
        stack_data = json.loads(stack_info.stdout)
        
        if "Stacks" in stack_data and len(stack_data["Stacks"]) > 0:
            outputs = stack_data["Stacks"][0].get("Outputs", [])
            logger.info(f"Found {len(outputs)} outputs in stack")
            
            # Look for exact UUID output key
            for output in outputs:
                if output.get("OutputKey") == "UUID":
                    uuid_value = output.get("OutputValue")
                    logger.info(f"Found UUID output: {uuid_value}")
                    return uuid_value
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON from stack output")
    
    return None

def get_deployment_uuid(region=None):
    """Get UUID from existing stack or create a new one."""
    stack_name = "emp-virtual-assistant"
    
    try:
        # Use provided region or detect it
        if not region:
            region = get_aws_region()
            
        # Check if stack exists and has a UUID
        uuid_value = get_uuid_from_stack(stack_name, region)
        
        # If UUID not found, generate a new one
        if not uuid_value:
            uuid_value = str(uuid.uuid4())
            logger.info(f"Generated new UUID: {uuid_value}")
        
        return uuid_value, region
        
    except Exception as e:
        logger.error(f"Error retrieving UUID from stack: {str(e)}")
        uuid_value = str(uuid.uuid4())
        region = region or "us-west-2"
        logger.info(f"Generated new UUID due to error: {uuid_value}")
        return uuid_value, region

def find_react_app_dir():
    """Find the React app directory relative to the script."""
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Find React app directory (sibling to the CDK directory)
    parent_dir = os.path.dirname(script_dir)
    react_app_dir = os.path.join(parent_dir, "employee_virtual_assistant_react")
    
    if not os.path.exists(react_app_dir):
        logger.error(f"React app directory not found at: {react_app_dir}")
        return None
        
    logger.info(f"Found React app directory: {react_app_dir}")
    return react_app_dir

def deploy_cdk_stack(stack_name, uuid_value, region, tavily_api_key):
    """Deploy CDK stack and return outputs."""
    # Set up script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    logger.info(f"Current directory: {os.getcwd()}")
    
    # Pass UUID to CDK using environment variables
    cdk_env = os.environ.copy()
    cdk_env["CDK_DEPLOY_UUID"] = uuid_value
    cdk_env["AWS_REGION"] = region

    # Generate a unique output directory
    cdk_out_dir = f"cdk.out-{uuid.uuid4()}"

    # Deploy CDK stack with explicit region
    logger.info(f"Deploying CDK stack to region {region}...")
    result = safe_run(
        [CDK_PATH, "deploy", stack_name, 
         "--outputs-file", "cdk-outputs.json", 
         "--require-approval", "never",
         "--context", f"tavily_api_key={tavily_api_key}",
         "--region", region,
         "--output", cdk_out_dir],
        capture_output=True,
        text=True,
        env=cdk_env
    )
    
    if result.returncode != 0:
        logger.error("CDK deployment failed:")
        logger.error(result.stderr)
        return None
    
    logger.info("CDK deployment successful!")

    # Check if outputs file exists
    if not os.path.exists("cdk-outputs.json"):
        logger.error("CDK outputs file not found")
        return None

    # Read outputs
    logger.info("Reading stack outputs...")
    with open("cdk-outputs.json", "r") as f:
        outputs = json.load(f)

    return outputs.get(stack_name)

def create_env_file(react_app_dir, stack_outputs, uuid_suffix):
    """Create environment file for React application."""
    logger.info(f"Creating .env file in {react_app_dir}")
    env_content = f"""REACT_APP_COGNITO_REGION={stack_outputs.get(f"CognitoRegion{uuid_suffix}", "")}
REACT_APP_COGNITO_USER_POOL_ID={stack_outputs.get(f"CognitoUserPoolId{uuid_suffix}", "")}
REACT_APP_COGNITO_CLIENT_ID={stack_outputs.get(f"CognitoClientId{uuid_suffix}", "")}
REACT_APP_API_GATEWAY_ENDPOINT={stack_outputs.get(f"ApiGatewayEndpoint{uuid_suffix}", "")}
REACT_APP_FILE_UPLOAD_ENDPOINT={stack_outputs.get(f"FileUploadEndpoint{uuid_suffix}", "")}
REACT_APP_HISTORY_ENDPOINT={stack_outputs.get(f"HistoryEndpoint{uuid_suffix}", "")}
REACT_APP_MESSAGES_ENDPOINT={stack_outputs.get(f"MessagesEndpoint{uuid_suffix}", "")}
REACT_APP_BEDROCK_SUPERVISOR_AGENT_ID={stack_outputs.get(f"SupervisorAgentId{uuid_suffix}", "")}
REACT_APP_BEDROCK_SUPERVISOR_AGENT_ALIAS_ID={stack_outputs.get(f"SupervisorAgentAliasId{uuid_suffix}", "")}
"""

    with open(os.path.join(react_app_dir, ".env"), "w") as f:
        f.write(env_content)
        logger.info("Environment file created successfully")
    
    return True

def build_react_app(react_app_dir):
    """Build React application."""
    # Change to React app directory
    os.chdir(react_app_dir)
    logger.info(f"Building React app in {react_app_dir}")
    
    # Install NPM dependencies
    logger.info("Installing npm dependencies...")
    result = safe_run([NPM_PATH, "install"], capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("npm install failed:")
        logger.error(result.stderr)
        return False
    
    # Build React app
    logger.info("Building React app...")
    result = safe_run([NPM_PATH, "run", "build"], capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("React build failed:")
        logger.error(result.stderr)
        return False
    
    logger.info("React app build successful!")
    
    # Verify build folder exists
    build_dir = os.path.join(react_app_dir, "build")
    if not os.path.exists(build_dir):
        logger.error(f"Build directory not found: {build_dir}")
        return False
    
    return build_dir

def upload_to_s3(build_dir, s3_bucket):
    """Upload React app to S3 bucket."""
    logger.info(f"Uploading React app to S3 bucket: {s3_bucket}")
    result = safe_run(
        [AWS_PATH, "s3", "sync", build_dir, f"s3://{s3_bucket}", "--delete"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        logger.error("S3 upload failed:")
        logger.error(result.stderr)
        return False
    
    logger.info("Uploaded React app to S3 successfully!")
    
    # List bucket contents to verify
    logger.info(f"Verifying S3 bucket contents:")
    safe_run([AWS_PATH, "s3", "ls", f"s3://{s3_bucket}"])
    
    return True

def invalidate_cloudfront(cloudfront_id):
    """Invalidate CloudFront cache."""
    if not cloudfront_id:
        return False
        
    logger.info(f"Invalidating CloudFront cache for distribution: {cloudfront_id}")
    result = safe_run(
        [AWS_PATH, "cloudfront", "create-invalidation", 
        "--distribution-id", cloudfront_id, 
        "--paths", "/*"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        logger.warning("CloudFront invalidation failed:")
        logger.warning(result.stderr)
        return False
        
    logger.info("CloudFront cache invalidated successfully")
    return True

def main():
    """Main deployment function."""
    # Parse command-line arguments
    args = parse_arguments()

    # Get UUID from existing stack or create new one
    uuid_value, detected_region = get_deployment_uuid()

    # Use command line region if provided, otherwise use detected region
    region = args.region if args.region else detected_region
    logger.info(f"Deploying to region: {region}")

    # Extract suffix from UUID for resource naming
    uuid_suffix = uuid_value[-5:]
    
    # Define static stack name
    stack_name = "emp-virtual-assistant"
    logger.info(f"Stack name: {stack_name}")
    logger.info(f"Using UUID: {uuid_value}")
    logger.info(f"Using UUID suffix: {uuid_suffix}")
    
    # Find React app directory
    react_app_dir = find_react_app_dir()
    if not react_app_dir:
        return 1
    
    # Deploy CDK stack
    stack_outputs = deploy_cdk_stack(stack_name, uuid_value, region, args.tavily_api_key)
    if not stack_outputs:
        return 1
    
    logger.info(f"Available stack outputs: {list(stack_outputs.keys())}")
    
    # Create .env file for React application
    create_env_file(react_app_dir, stack_outputs, uuid_suffix)
    
    # Build React app
    build_dir = build_react_app(react_app_dir)
    if not build_dir:
        return 1
    
    # Get S3 bucket name from stack outputs
    website_bucket_key = f"WebsiteBucketName{uuid_suffix}"
    s3_bucket = stack_outputs.get(website_bucket_key, "")
    if not s3_bucket:
        logger.error(f"{website_bucket_key} not found in stack outputs")
        return 1
    
    # Upload to S3
    if not upload_to_s3(build_dir, s3_bucket):
        return 1
    
    # Invalidate CloudFront
    cloudfront_id_key = f"CloudFrontDistributionId{uuid_suffix}"
    cloudfront_id = stack_outputs.get(cloudfront_id_key, "")
    invalidate_cloudfront(cloudfront_id)
    
    # Print the website URL
    cloudfront_url_key = f"CloudFrontURL{uuid_suffix}"
    cloudfront_url = stack_outputs.get(cloudfront_url_key, "")
    logger.info(f"\n🎉 Deployment complete! Your website is available at:\n{cloudfront_url}\n")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())