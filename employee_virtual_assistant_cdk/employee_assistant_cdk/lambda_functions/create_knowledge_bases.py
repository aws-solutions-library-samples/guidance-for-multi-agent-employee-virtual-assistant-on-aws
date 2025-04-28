import boto3
import os
import time
import json
import logging
import requests
from requests_aws4auth import AWS4Auth
from botocore.exceptions import ClientError
from opensearchpy import OpenSearch, RequestsHttpConnection, exceptions

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Constants for configuration
VECTOR_DIMENSION = 1024
MAX_TOKENS = 1024
OVERLAP_PERCENTAGE = 20
INDEX_CREATION_WAIT_TIME = 60  # seconds
RETRY_WAIT_TIME = 20  # seconds
KB_STATUS_CHECK_INTERVAL = 30  # seconds
INGESTION_JOB_CHECK_INTERVAL = 20  # seconds
EMBEDDING_MODEL_VERSION = "amazon.titan-embed-text-v2:0"

def create_vector_index(host, index_name, region_name, max_retries=3):
    """
    Creates a vector index in OpenSearch using OpenSearch Python client
    
    Args:
        host (str): OpenSearch host endpoint
        index_name (str): Name of the index to create
        region_name (str): AWS region
        max_retries (int): Maximum number of retry attempts
        
    Returns:
        bool: True if successful, False otherwise
    """
    # AWS Auth for OpenSearch
    session = boto3.Session()
    credentials = session.get_credentials()

    # Create AWS4Auth for OpenSearch
    auth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        region_name,
        'aoss',
        session_token=credentials.token
    )

    # Index configuration with KNN vector
    body_json = {
       "settings": {
          "index.knn": "true",
           "number_of_shards": 1,
           "knn.algo_param.ef_search": 512,
           "number_of_replicas": 0,
       },
       "mappings": {
          "properties": {
             "vector": {
                "type": "knn_vector",
                "dimension": VECTOR_DIMENSION,
                 "method": {
                     "name": "hnsw",
                     "engine": "faiss",
                     "space_type": "l2"
                 },
             },
             "text": {
                "type": "text"
             },
             "text-metadata": {
                "type": "text"
             }
          }
       }
    }

    # Try to create index with multiple retries
    for attempt in range(max_retries):
        try:
            logger.info(f"Creating OpenSearch client for host: {host}")
            
            # Build the OpenSearch client
            client = OpenSearch(
                hosts=[{'host': host, 'port': 443}],
                http_auth=auth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection,
                timeout=60
            )
            
            # Create index
            logger.info(f"Creating index {index_name}, attempt {attempt+1}")
            response = client.indices.create(
                index=index_name, 
                body=json.dumps(body_json)
            )
            
            logger.info(f"Index creation successful: {response}")
            time.sleep(INDEX_CREATION_WAIT_TIME)  # Wait for index to be fully available
            logger.info(f"Index creation completed")
            return True
            
        except exceptions.RequestError as e:
            if "resource_already_exists_exception" in str(e):
                logger.info(f"Index {index_name} already exists")
                return True
            
            logger.warning(f"Error creating index (attempt {attempt+1}/{max_retries}): {e}")
            time.sleep(RETRY_WAIT_TIME)
            
        except Exception as e:
            logger.warning(f"Unexpected error creating index (attempt {attempt+1}/{max_retries}): {str(e)}")
            time.sleep(RETRY_WAIT_TIME)

    logger.warning(f"Could not create index {index_name} after {max_retries} attempts, continuing anyway")
    return True

def create_knowledge_base(bedrock_agent, name, description, role_arn, collection_arn, vector_index_name, region_name, account_id, max_retries=5):
    """
    Creates a knowledge base with OpenSearch Serverless configuration
    
    Args:
        bedrock_agent: Bedrock agent client
        name (str): Knowledge base name
        description (str): Knowledge base description
        role_arn (str): IAM role ARN
        collection_arn (str): OpenSearch collection ARN
        vector_index_name (str): Vector index name
        region_name (str): AWS region
        account_id (str): AWS account ID
        max_retries (int): Maximum number of retry attempts
        
    Returns:
        dict: Created knowledge base details
    """
    embedding_model_arn = f"arn:aws:bedrock:{region_name}::foundation-model/{EMBEDDING_MODEL_VERSION}"

    opensearch_serverless_configuration = {
        "collectionArn": collection_arn,
        "vectorIndexName": vector_index_name,
        "fieldMapping": {
            "vectorField": "vector",
            "textField": "text",
            "metadataField": "text-metadata"
        }
    }

    tags = {
        "CreatedBy": "LambdaFunction",
        "AccountId": account_id,
        "Region": region_name
    }

    for attempt in range(max_retries):
        try:
            create_kb_response = bedrock_agent.create_knowledge_base(
                name=name,
                description=description,
                roleArn=role_arn,
                knowledgeBaseConfiguration={
                    "type": "VECTOR",
                    "vectorKnowledgeBaseConfiguration": {
                        "embeddingModelArn": embedding_model_arn
                    }
                },
                storageConfiguration={
                    "type": "OPENSEARCH_SERVERLESS",
                    "opensearchServerlessConfiguration": opensearch_serverless_configuration
                },
                tags=tags
            )
            
            logger.info(f"Successfully created knowledge base {name}")
            return create_kb_response["knowledgeBase"]
            
        except Exception as e:
            logger.error(f"Error creating knowledge base (attempt {attempt+1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(10)
    
    raise Exception(f"Failed to create knowledge base {name} after {max_retries} attempts")

def create_data_source(bedrock_agent, kb_id, name, s3_bucket, folder):
    """
    Creates a data source pointing to S3 with chunking configuration
    
    Args:
        bedrock_agent: Bedrock agent client
        kb_id (str): Knowledge base ID
        name (str): Data source name
        s3_bucket (str): S3 bucket name
        folder (str): S3 folder path
        
    Returns:
        dict: Created data source details
    """
    chunking_strategy_config = {
        "chunkingStrategy": "FIXED_SIZE",
        "fixedSizeChunkingConfiguration": {
            "maxTokens": MAX_TOKENS,
            "overlapPercentage": OVERLAP_PERCENTAGE
        }
    }

    s3_config = {
        "bucketArn": f"arn:aws:s3:::{s3_bucket}",
        "inclusionPrefixes": [f"{folder}/"]
    }

    # Create a valid data source name
    valid_name = ''.join(c if c.isalnum() or c in '_-' else '_' for c in name)
    if valid_name and not valid_name[0].isalnum():
        valid_name = 'ds' + valid_name

    create_ds_response = bedrock_agent.create_data_source(
        name=valid_name,
        description=f"Data source for {folder} documents",
        knowledgeBaseId=kb_id,
        dataSourceConfiguration={
            "type": "S3",
            "s3Configuration": s3_config
        },
        vectorIngestionConfiguration={
            "chunkingConfiguration": chunking_strategy_config
        }
    )

    return create_ds_response["dataSource"]

def start_ingestion_job(bedrock_agent, kb_id, ds_id):
    """
    Starts and monitors an ingestion job
    
    Args:
        bedrock_agent: Bedrock agent client
        kb_id (str): Knowledge base ID
        ds_id (str): Data source ID
        
    Returns:
        dict: Ingestion job details
    """
    try:
        # Wait for knowledge base to be active before starting ingestion
        max_kb_checks = 10
        for i in range(max_kb_checks):
            try:
                kb_response = bedrock_agent.get_knowledge_base(
                    knowledgeBaseId=kb_id
                )
                kb_status = kb_response["knowledgeBase"]["status"]
                logger.info(f"Knowledge base status: {kb_status}")
                
                if kb_status == "ACTIVE":
                    logger.info(f"Knowledge base {kb_id} is ready for ingestion")
                    break
                elif kb_status in ["FAILED", "DELETING", "DELETED"]:
                    logger.error(f"Knowledge base in invalid state: {kb_status}")
                    raise Exception(f"Knowledge base in invalid state: {kb_status}")
                
                logger.info(f"Knowledge base still {kb_status}, waiting... (attempt {i+1}/{max_kb_checks})")
                time.sleep(KB_STATUS_CHECK_INTERVAL)
            except Exception as e:
                logger.error(f"Error checking knowledge base status: {str(e)}")
                time.sleep(10)
        else:
            logger.warning("Timed out waiting for knowledge base to be ready. Proceeding with caution.")

        # Start the ingestion job
        start_job_response = bedrock_agent.start_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id
        )
        job = start_job_response["ingestionJob"]
        logger.info(f"Ingestion job started with ID: {job['ingestionJobId']}")

        # Monitor job until timeout or completion
        max_checks = 5
        check_count = 0

        while check_count < max_checks and job['status'] != 'COMPLETE':
            get_job_response = bedrock_agent.get_ingestion_job(
                knowledgeBaseId=kb_id,
                dataSourceId=ds_id,
                ingestionJobId=job["ingestionJobId"]
            )
            job = get_job_response["ingestionJob"]
            logger.info(f"Ingestion job status: {job['status']}")
            check_count += 1
            
            if job['status'] in ['COMPLETE', 'FAILED', 'STOPPED']:
                break
                
            time.sleep(INGESTION_JOB_CHECK_INTERVAL)
            
        return job
    except Exception as e:
        logger.error(f"Error in ingestion job: {str(e)}")
        return {
            "ingestionJobId": "error",
            "status": "ERROR",
            "error": str(e)
        }

def handler(event, context):
    """
    Main Lambda handler for knowledge base creation
    
    Args:
        event (dict): Lambda input event
        context (object): Lambda context
        
    Returns:
        dict: Result with created knowledge base details
    """
    request_type = event.get('RequestType')
    
    if request_type == 'Delete':
        logger.info(f"Received DELETE request, returning original PhysicalResourceId: {event.get('PhysicalResourceId')}")
        return {
            'PhysicalResourceId': event.get('PhysicalResourceId'),
            'Status': 'SUCCESS'
        }
    
    # Initialize clients
    bedrock_agent = boto3.client("bedrock-agent")
    
    # Get AWS account and region details
    session = boto3.session.Session()
    region_name = session.region_name
    sts_client = boto3.client("sts")
    account_id = sts_client.get_caller_identity()["Account"]

    # Get environment variables and event properties
    s3_bucket = os.environ.get('S3_BUCKET_NAME')
    uuid_suffix = os.environ.get('UUID_SUFFIX', '')[-5:]
    
    resource_props = event.get('ResourceProperties', {})
    collection_arn = resource_props.get('collection_arn')
    collection_host = resource_props.get('collection_host')
    kb_configs_str = resource_props.get('knowledge_bases')
    bedrock_role_arn = resource_props.get('role_arn') or os.environ.get('BEDROCK_ROLE_ARN')
    
    logger.info(f"Received properties - collection_arn: {collection_arn}, host: {collection_host}")
    
    # Parse KB configs
    kb_configs = []
    if kb_configs_str:
        try:
            kb_configs = json.loads(kb_configs_str)
            logger.info(f"Parsed knowledge base configs: {len(kb_configs)} configs found")
        except Exception as e:
            logger.error(f"Failed to parse knowledge_bases JSON: {str(e)}")
    
    if not collection_arn or not collection_host or not kb_configs:
        error_msg = f"Missing required parameters: collection_arn={collection_arn}, host={collection_host}, kb_configs={len(kb_configs) if kb_configs else 0}"
        logger.error(error_msg)
        return {
            'PhysicalResourceId': f"knowledge-bases-error-{uuid_suffix}",
            'Status': 'FAILED', 
            'Reason': error_msg
        }

    try:
        # Create each knowledge base with its own index
        created_kbs = []
        
        for kb_config in kb_configs:
            try:
                logger.info(f"Processing knowledge base: {kb_config['name']}")
                
                # Step 1: Create vector index for this KB
                index_name = kb_config["index"]
                logger.info(f"Creating vector index: {index_name}")
                create_vector_index(collection_host, index_name, region_name)

                # Step 2: Create knowledge base
                logger.info(f"Creating knowledge base {kb_config['name']}...")
                kb = create_knowledge_base(
                    bedrock_agent,
                    kb_config['name'],
                    kb_config['description'],
                    bedrock_role_arn,
                    collection_arn,
                    index_name,
                    region_name,
                    account_id
                )
                
                # Step 3: Create data source
                logger.info(f"Creating data source for {kb_config['name']}...")
                folder_part = kb_config['folder'].replace('/', '_')
                ds_name = f"ds_{uuid_suffix}_{folder_part}"
                
                ds = create_data_source(
                    bedrock_agent,
                    kb['knowledgeBaseId'],
                    ds_name,
                    s3_bucket,
                    kb_config['folder']
                )
                
                # Step 4: Start ingestion job
                logger.info(f"Starting ingestion job for {kb_config['name']}...")
                job = start_ingestion_job(bedrock_agent, kb['knowledgeBaseId'], ds['dataSourceId'])
                
                created_kbs.append({
                    'name': kb_config['name'],
                    'knowledgeBaseId': kb['knowledgeBaseId'],
                    'dataSourceId': ds['dataSourceId'],
                    'ingestionJobId': job.get('ingestionJobId', 'error'),
                    'collectionArn': collection_arn,
                    'indexName': index_name,
                    'folder': kb_config['folder']
                })
                
            except Exception as e:
                logger.error(f"Error creating knowledge base {kb_config['name']}: {str(e)}")
                # Continue with next KB even if one fails
        
        # Create the KNOWLEDGE_BASES mapping
        knowledge_bases_mapping = {}
        for kb in created_kbs:
            if 'folder' in kb and 'knowledgeBaseId' in kb:
                kb_type = kb['folder'].split('/')[-1]
                if kb_type == 'it_help_desk':
                    kb_type = 'helpdesk'
                knowledge_bases_mapping[kb_type] = kb['knowledgeBaseId']

        # Return success with data
        return {
            'PhysicalResourceId': f"knowledge-bases-{uuid_suffix}",
            'Data': {
                'message': f"Created {len(created_kbs)} knowledge bases",
                'uuid_suffix': uuid_suffix,
                'knowledgeBases': created_kbs,
                'knowledgeBaseIds': [kb['knowledgeBaseId'] for kb in created_kbs if 'knowledgeBaseId' in kb],
                'KNOWLEDGE_BASES': knowledge_bases_mapping,
                'KNOWLEDGE_BASES_JSON': json.dumps(knowledge_bases_mapping)
            }
        }
    except Exception as e:
        logger.error(f"Error in Lambda execution: {str(e)}")
        return {
            'PhysicalResourceId': f"knowledge-bases-error-{uuid_suffix}",
            'Status': 'FAILED',
            'Reason': str(e)
        }