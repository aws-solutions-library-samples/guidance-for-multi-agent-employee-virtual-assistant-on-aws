import json
import boto3
import base64
import os
import uuid
import mimetypes
import re
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    Lambda handler to process file uploads
    
    Args:
        event (dict): Lambda input event
        context (object): Lambda context
        
    Returns:
        dict: API Gateway response with upload results
    """
    logger.info("Processing file upload request")
    
    # Check for API Gateway proxy integration format
    if 'body' not in event:
        logger.error("Missing 'body' in event. Not properly formatted from API Gateway")
        return error_response("Malformed request from API Gateway")
        
    # Initialize S3 client
    s3_client = boto3.client('s3')
    s3_bucket = os.environ.get('S3_BUCKET_NAME')
    
    logger.info(f"Using S3 bucket: {s3_bucket}")
    
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        folder = body.get('folder', '').lower().replace(' ', '_')
        files = body.get('files', [])
        
        # Basic validation
        if not folder:
            return error_response('Folder name is required')
        
        # Allowed folders
        allowed_folders = ['hr', 'it_helpdesk', 'benefits', 'payroll', 'training']
        if folder not in allowed_folders:
            return error_response('Invalid folder name')
            
        if not files or len(files) == 0:
            return error_response('No files provided')
        
        # Process each file
        uploaded_files = []
        for file_data in files:
            try:
                # Get file info
                file_name = file_data.get('name', '')
                file_content_b64 = file_data.get('content', '').split('base64,')[-1]
                file_type = file_data.get('type', '')
                
                # Validate file name and type
                if not file_name or not re.match(r'^[\w\-. ]+\.(pdf|doc|docx)$', file_name, re.IGNORECASE):
                    logger.warning(f"Invalid file name or type: {file_name}")
                    continue  # Skip invalid files
                
                # Decode base64 content
                file_content = base64.b64decode(file_content_b64)
                
                # Determine content type if not provided
                if not file_type:
                    file_type, _ = mimetypes.guess_type(file_name)
                
                # Upload to S3
                key = f"{folder}/{file_name}"
                s3_client.put_object(
                    Bucket=s3_bucket,
                    Key=key,
                    Body=file_content,
                    ContentType=file_type
                )
                
                uploaded_files.append(file_name)
                logger.info(f"Uploaded file: {file_name} to {folder} folder")
                
            except Exception as e:
                logger.error(f"Error processing file {file_data.get('name', 'unknown')}: {str(e)}")
                continue
        
        if not uploaded_files:
            return error_response('No valid files were uploaded')
        
        # Return success response
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'message': f'Successfully uploaded {len(uploaded_files)} files to {folder}',
                'files': uploaded_files,
                'folder': folder
            })
        }
        
    except Exception as e:
        logger.error(f"Error handling upload request: {str(e)}", exc_info=True)
        return error_response(f'Upload failed: {str(e)}')

def error_response(message):
    """
    Create a standardized error response
    
    Args:
        message (str): Error message
        
    Returns:
        dict: API Gateway error response
    """
    return {
        'statusCode': 400,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'success': False,
            'message': message
        })
    }