import json
import boto3
import os
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    Lambda handler to process S3 uploads and trigger knowledge base ingestion
    
    Args:
        event (dict): S3 event notification
        context (object): Lambda context
        
    Returns:
        dict: Processing result
    """
    logger.info("Processing S3 upload event")
    
    # Initialize clients
    s3_client = boto3.client('s3')
    bedrock_agent = boto3.client('bedrock-agent')
    
    # Process each S3 event
    for record in event['Records']:
        try:
            # Extract bucket and key information
            bucket = record['s3']['bucket']['name']
            key = record['s3']['object']['key']
            
            logger.info(f"Processing uploaded file: s3://{bucket}/{key}")
            
            # Determine the folder from the key path
            path_parts = key.split('/')
            if len(path_parts) < 2:
                logger.warning(f"Invalid path structure: {key}")
                continue
            
            folder = path_parts[0].lower()
            
            # Map folder to knowledge base ID
            knowledge_bases_str = os.environ.get('KNOWLEDGE_BASES', '{}')
            knowledge_bases = json.loads(knowledge_bases_str)
            
            # Handle the IT Helpdesk special case
            if folder == 'it_helpdesk':
                folder = 'helpdesk'
                
            kb_id = knowledge_bases.get(folder)
            if not kb_id:
                logger.warning(f"No knowledge base found for folder: {folder}")
                continue
            
            logger.info(f"Found knowledge base {kb_id} for folder {folder}")
            
            # Get the data source ID for this knowledge base
            data_sources = bedrock_agent.list_data_sources(
                knowledgeBaseId=kb_id
            )
            
            if not data_sources.get('dataSourceSummaries'):
                logger.warning(f"No data sources found for knowledge base: {kb_id}")
                continue
            
            ds_id = data_sources['dataSourceSummaries'][0]['dataSourceId']
            
            # Trigger an ingestion job
            logger.info(f"Starting ingestion job for knowledge base {kb_id} with data source {ds_id}")
            ingestion_job = bedrock_agent.start_ingestion_job(
                knowledgeBaseId=kb_id,
                dataSourceId=ds_id
            )
            
            logger.info(f"Started ingestion job: {ingestion_job['ingestionJob']['ingestionJobId']}")
            
        except Exception as e:
            logger.error(f"Error processing upload: {str(e)}", exc_info=True)
            continue
    
    return {
        'statusCode': 200,
        'body': json.dumps('Processing complete')
    }