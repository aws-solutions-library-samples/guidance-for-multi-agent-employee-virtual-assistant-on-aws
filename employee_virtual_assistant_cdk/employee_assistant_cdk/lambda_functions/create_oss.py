import boto3
import os
import time
import json
import logging
import re
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def validate_bedrock_role(iam_client, role_arn, account_id, s3_bucket):
    """Validates and fixes the Bedrock role trust policy and permissions"""
    try:
        # Extract role name from ARN (format: arn:aws:iam::account-id:role/role-name)
        match = re.search(r"role/(?:(?:service-role/)*)?(.+)", role_arn)
        if not match:
            print(f"Invalid role ARN: {role_arn}")
            return
        
        role_name = match.group(1)

        # Check if role exists
        role = iam_client.get_role(RoleName=role_name)
        role_arn = role['Role']['Arn']

        # Check and update trust policy if needed
        trust_policy = role['Role']['AssumeRolePolicyDocument']
        needs_update = False
        
        # Make sure bedrock.amazonaws.com is in the trust policy
        bedrock_found = False
        for statement in trust_policy.get('Statement', []):
            if statement.get('Effect') == 'Allow' and 'Service' in statement.get('Principal', {}):
                services = statement['Principal']['Service']
                if isinstance(services, str):
                    services = [services]
                if 'bedrock.amazonaws.com' in services:
                    bedrock_found = True
                    break
        
        if not bedrock_found:
            logger.info(f"Adding bedrock.amazonaws.com to trust policy for {role_name}")
            trust_policy['Statement'].append({
                'Effect': 'Allow',
                'Principal': {'Service': 'bedrock.amazonaws.com'},
                'Action': 'sts:AssumeRole'
            })
            needs_update = True
        
        if needs_update:
            iam_client.update_assume_role_policy(
                RoleName=role_name,
                PolicyDocument=json.dumps(trust_policy)
            )
            logger.info(f"Updated trust policy for {role_name}")
            time.sleep(30)  # Increased wait time for policy propagation
        
        # Add inline policy for S3 and OpenSearch
        policy_name = 'BedrockKBPermissionsExpanded'
        try:
            # Check if policy exists
            iam_client.get_role_policy(RoleName=role_name, PolicyName=policy_name)
            logger.info(f"Policy {policy_name} already exists for {role_name}")
        except Exception as e:
            if 'NoSuchEntity' in str(e):
                # Create new inline policy with expanded permissions
                policy_document = {
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Effect': 'Allow',
                            'Action': [
                                's3:GetObject',
                                's3:ListBucket',
                                's3:GetBucketLocation'  # Added permission
                            ],
                            'Resource': [
                                f"arn:aws:s3:::{s3_bucket}",
                                f"arn:aws:s3:::{s3_bucket}/*"
                            ]
                        },
                        {
                            'Effect': 'Allow',
                            'Action': [
                                'aoss:*',
                                'aoss:APIAccessAll'  # Added broader permission
                            ],
                            'Resource': '*'
                        },
                        {
                            'Effect': 'Allow',
                            'Action': [
                                'bedrock:InvokeModel'  # Add permission to invoke embedding model
                            ],
                            'Resource': '*'
                        }
                    ]
                }
                
                iam_client.put_role_policy(
                    RoleName=role_name,
                    PolicyName=policy_name,
                    PolicyDocument=json.dumps(policy_document)
                )
                logger.info(f"Created policy {policy_name} for {role_name} with expanded permissions")
                time.sleep(40)  # Increased wait time for policy propagation
        
        return role_arn
    except Exception as e:
        logger.error(f"Error validating Bedrock role: {str(e)}")
        raise e

def create_policies_for_collection(aoss_client, collection_name, enc_policy_name, network_policy_name, 
                                  access_policy_name, bedrock_kb_execution_role_arn, account_id):
    """Creates OpenSearch Serverless policies with proper permissions"""
    # Create encryption policy
    encryption_policy = aoss_client.create_security_policy(
        name=enc_policy_name,
        policy=json.dumps({
            'Rules': [{'Resource': [f'collection/{collection_name}'],
                      'ResourceType': 'collection'}],
            'AWSOwnedKey': True
        }),
        type='encryption'
    )
    logger.info(f"Created encryption policy {enc_policy_name}")

    # Create network policy
    network_policy = aoss_client.create_security_policy(
        name=network_policy_name,
        policy=json.dumps([
            {'Rules': [{'Resource': [f'collection/{collection_name}'],
                       'ResourceType': 'collection'}],
             'AllowFromPublic': True}
        ]),
        type='network'
    )
    logger.info(f"Created network policy {network_policy_name}")

    # Include all necessary principals in the access policy
    principals = [
        # Root account - gives full access
        f"arn:aws:iam::{account_id}:root",
        
        # Bedrock role - needed for Bedrock to access OpenSearch
        bedrock_kb_execution_role_arn
    ]

    # Create access policy
    access_policy = aoss_client.create_access_policy(
        name=access_policy_name,
        policy=json.dumps([
            {
                'Rules': [
                    {
                        'Resource': [f'collection/{collection_name}'],
                        'Permission': [
                            'aoss:CreateCollectionItems',
                            'aoss:DeleteCollectionItems',
                            'aoss:UpdateCollectionItems',
                            'aoss:DescribeCollectionItems'],
                        'ResourceType': 'collection'
                    },
                    {
                        'Resource': [f'index/{collection_name}/*'],
                        'Permission': [
                            'aoss:CreateIndex',
                            'aoss:DeleteIndex',
                            'aoss:UpdateIndex',
                            'aoss:DescribeIndex',
                            'aoss:ReadDocument',
                            'aoss:WriteDocument'],
                        'ResourceType': 'index'
                    }],
                'Principal': principals,
                'Description': f'Access policy for {collection_name}'
            }
        ]),
        type='data'
    )
    logger.info(f"Created access policy {access_policy_name} with {len(principals)} principals")

    # Wait for policies to propagate
    logger.info(f"Waiting for policies to propagate...")
    time.sleep(20)
    return True

def create_or_get_collection(aoss_client, collection_name, region_name):
    """Creates or gets existing OpenSearch Serverless collection"""
    try:
        # Check if collection exists
        response = aoss_client.batch_get_collection(names=[collection_name])
        if response['collectionDetails']:
            collection_details = response['collectionDetails'][0]
            collection_id = collection_details['id']
            collection_arn = collection_details['arn']
            host = collection_id + '.' + region_name + '.aoss.amazonaws.com'
            logger.info(f"Collection {collection_name} already exists with ID: {collection_id}")
            return collection_id, collection_arn, host
    except ClientError as e:
        if e.response['Error']['Code'] != 'ResourceNotFoundException':
            raise e

    # Create new collection
    collection = aoss_client.create_collection(
        name=collection_name,
        type='VECTORSEARCH'
    )

    collection_id = collection['createCollectionDetail']['id']
    collection_arn = collection['createCollectionDetail']['arn']
    host = collection_id + '.' + region_name + '.aoss.amazonaws.com'
    logger.info(f"Created new collection with host: {host}")

    # Wait for collection creation to complete
    response = aoss_client.batch_get_collection(names=[collection_name])
    while (response['collectionDetails'][0]['status']) == 'CREATING':
        logger.info('Collection creation in progress...')
        time.sleep(30)
        response = aoss_client.batch_get_collection(names=[collection_name])

    logger.info('Collection successfully created')

    # Sleep for a bit to ensure policies are fully applied
    time.sleep(30)

    return collection_id, collection_arn, host

def handler(event, context):
    request_type = event.get('RequestType')
    
    if request_type == 'Delete':
        return {
            'Status': 'SUCCESS',
            'PhysicalResourceId': event.get('PhysicalResourceId'),
            'RequestId': event.get('RequestId', ''),
            'LogicalResourceId': event.get('LogicalResourceId', ''),
            'StackId': event.get('StackId', '')
        }
    
    """Main Lambda handler that orchestrates the policy and collection creation process"""
    logger.info(f"Received event: {json.dumps(event)}")

    # Initialize clients
    iam_client = boto3.client('iam')
    aoss_client = boto3.client("opensearchserverless")

    # Get AWS account and region details
    session = boto3.session.Session()
    region_name = session.region_name
    sts_client = boto3.client("sts")
    account_id = sts_client.get_caller_identity()["Account"]

    # Get environment variables and configuration
    s3_bucket = os.environ.get('S3_BUCKET_NAME')
    
    # Generate or get UUID suffix
    uuid_suffix = os.environ.get('UUID_SUFFIX', '')[-5:]
    if not uuid_suffix:
        import uuid
        uuid_suffix = str(uuid.uuid4())[-5:]
    
    # Get account ID from Lambda function ARN
    account_id = context.invoked_function_arn.split(':')[4]

    # Get and validate Bedrock execution role
    bedrock_role_arn = os.environ.get('BEDROCK_ROLE_ARN')
    bedrock_kb_execution_role_arn = validate_bedrock_role(iam_client, bedrock_role_arn, account_id, s3_bucket)
    logger.info(f"Validated Bedrock role: {bedrock_kb_execution_role_arn}")

    # For OpenSearch:
    # Collection name must match pattern: [a-z][a-z0-9-]{2,31}
    os_prefix = "eva"  # OpenSearch policy and collection prefix
    
    # Create a valid collection name for OpenSearch
    collection_name = f"{os_prefix}-collection-{uuid_suffix}"
    if len(collection_name) > 32:
        collection_name = collection_name[:32]
    
    # For Knowledge Bases and other resources
    kb_prefix = "eva_"
    
    # Knowledge bases to create with prefixed names
    knowledge_bases = [
        {
            "name": f"{kb_prefix}hr_kb_{uuid_suffix}", 
            "description": "HR Knowledge Base for storing and managing HR-related documents, providing easy access to policies, procedures, and employee resources using Amazon Bedrock for enhanced AI-powered search.", 
            "folder": "hr",
            "index": f"{os_prefix}-hr-index-{uuid_suffix}"
        },
        {
            "name": f"{kb_prefix}payroll_kb_{uuid_suffix}", 
            "description": "Payroll Knowledge Base for storing and managing payroll-related documents, enabling AI-powered search and quick access to salary, tax, and benefits information using Amazon Bedrock.", 
            "folder": "payroll",
            "index": f"{os_prefix}-payroll-index-{uuid_suffix}"
        },
        {
            "name": f"{kb_prefix}benefits_kb_{uuid_suffix}", 
            "description": "Benefits Knowledge Base for storing and managing employee benefits-related documents, health plans, retirement, and other benefits details with AI-powered search via Amazon Bedrock.", 
            "folder": "benefits",
            "index": f"{os_prefix}-benefits-index-{uuid_suffix}"
        },
        {
            "name": f"{kb_prefix}it_helpdesk_kb_{uuid_suffix}", 
            "description": "IT Helpdesk Knowledge Base for storing and managing technical support documents, troubleshooting guides, and FAQs, enabling efficient AI-powered assistance through Amazon Bedrock.", 
            "folder": "it_help_desk",
            "index": f"{os_prefix}-it-helpdesk-index-{uuid_suffix}"
        },
        {
            "name": f"{kb_prefix}training_kb_{uuid_suffix}", 
            "description": "Training Knowledge Base for storing and managing employee training materials, courses, and resources, providing AI-powered learning assistance via Amazon Bedrock.", 
            "folder": "training",
            "index": f"{os_prefix}-training-index-{uuid_suffix}"
        }
    ]

    try:
        # Step 1: Create policies for the collection with prefixed names
        logger.info(f"Creating OpenSearch policies for collection: {collection_name}")
        enc_policy_name = f"{os_prefix}-encryption-policy-{uuid_suffix}"
        network_policy_name = f"{os_prefix}-network-policy-{uuid_suffix}"
        access_policy_name = f"{os_prefix}-access-policy-{uuid_suffix}"
        
        create_policies_for_collection(
            aoss_client, 
            collection_name, 
            enc_policy_name, 
            network_policy_name, 
            access_policy_name,
            bedrock_kb_execution_role_arn, 
            account_id
        )
        
        # Step 2: Create OpenSearch collection
        logger.info(f"Creating OpenSearch collection: {collection_name}")
        collection_id, collection_arn, host = create_or_get_collection(
            aoss_client, 
            collection_name, 
            region_name
        )
        
        responseData = {
            'collection_arn': collection_arn,
            'collection_host': host,
            'role_arn': bedrock_kb_execution_role_arn,
            'knowledge_bases': json.dumps(knowledge_bases)
        }
        
        return {
            'Status': 'SUCCESS',
            'PhysicalResourceId': f"policy-collection-{uuid_suffix}",
            'Data': responseData
        }
    except Exception as e:
        logger.error(f"Error in Lambda execution: {str(e)}")
        return {
            'Status': 'FAILED',
            'PhysicalResourceId': f"policy-collection-error-{uuid_suffix}",
            'RequestId': event.get('RequestId', ''),
            'LogicalResourceId': event.get('LogicalResourceId', ''),
            'StackId': event.get('StackId', ''),
            'Reason': str(e)
        }