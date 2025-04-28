import json
import boto3
import base64
import os
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    Lambda handler to retrieve messages for a specific conversation
    
    Args:
        event (dict): Lambda input event
        context (object): Lambda context
        
    Returns:
        dict: API Gateway response with conversation messages
    """
    try:
        logger.info("Processing conversation messages request")
        
        # Extract user details from the token
        user_details = extract_user_details(event)
        logger.info(f"User ID: {user_details['userId']}")
        
        # Get the sessionId from the path parameters
        path_params = event.get('pathParameters', {}) or {}
        session_id = path_params.get('sessionId')
        logger.info(f"Requesting messages for session: {session_id}")
        
        if not session_id:
            return response(400, {'error': 'Session ID is required'})
        
        # Initialize DynamoDB client
        dynamodb = boto3.resource('dynamodb')
        conversation_table_name = os.environ.get('CONVERSATION_TABLE')
        logger.info(f"Using DynamoDB table: {conversation_table_name}")
        
        if not conversation_table_name:
            return response(500, {'error': 'Conversation table not configured'})
        
        conversation_table = dynamodb.Table(conversation_table_name)
        
        # Try querying both ways - first with GSI, then with scan as fallback
        try:
            # First try the GSI
            logger.info(f"Querying with GSI for sessionId: {session_id}")
            result = conversation_table.query(
                IndexName='sessionId-timestamp-index',
                KeyConditionExpression='sessionId = :sessionId',
                ExpressionAttributeValues={
                    ':sessionId': session_id
                },
                ScanIndexForward=True  # Sort ascending by timestamp
            )
            items = result.get('Items', [])
            logger.info(f"GSI query returned {len(items)} items")
            
            if not items:
                # If GSI returns no results, try a scan as fallback
                logger.info(f"No results from GSI, trying scan for sessionId: {session_id}")
                scan_result = conversation_table.scan(
                    FilterExpression='sessionId = :sessionId',
                    ExpressionAttributeValues={
                        ':sessionId': session_id
                    }
                )
                items = scan_result.get('Items', [])
                logger.info(f"Scan returned {len(items)} items")
        except Exception as e:
            logger.error(f"Error querying conversation data: {str(e)}")
            return response(500, {'error': f'Query failed: {str(e)}'})
        
        # Process the messages for the frontend
        messages = []
        for item in items:
            # Skip messages from other users
            if item.get('userId') != user_details['userId']:
                logger.info(f"Skipping message from different user: {item.get('userId')} vs {user_details['userId']}")
                continue
                
            # Format the message for the frontend
            messages.append({
                'timestamp': item.get('timestamp', ''),
                'userQuery': item.get('userQuery', ''),
                'response': item.get('response', ''),
                'thinkingSteps': item.get('thinkingSteps', []),
            })
        
        logger.info(f"Returning {len(messages)} messages")
        return response(200, {
            'messages': messages,
            'sessionId': session_id
        })
    
    except Exception as e:
        logger.error(f"Error retrieving conversation messages: {str(e)}", exc_info=True)
        return response(500, {'error': f'Failed to retrieve conversation messages: {str(e)}'})

def extract_user_details(event):
    """
    Extract user details from the Cognito JWT token
    
    Args:
        event (dict): Lambda input event
        
    Returns:
        dict: User details
    """
    try:
        # Get the Authorization header from the request
        headers = event.get('headers', {})
        auth_header = headers.get('Authorization') or headers.get('authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            logger.info("No valid Authorization header found")
            return {
                'userId': 'anonymous',
                'username': 'anonymous',
                'email': 'anonymous'
            }
        
        # Extract the JWT token
        token = auth_header.split(' ')[1]
        
        # Extract details from token
        try:
            # Split token and get payload section
            token_parts = token.split('.')
            if len(token_parts) != 3:
                logger.warning("Invalid token format")
                return {
                    'userId': 'anonymous',
                    'username': 'anonymous',
                    'email': 'anonymous'
                }
                
            payload = token_parts[1]
            
            # Add padding if needed
            padding = 4 - (len(payload) % 4)
            if padding != 4:
                payload += '=' * padding
            
            # Decode the payload
            decoded = json.loads(base64.b64decode(payload).decode('utf-8'))
            
            # Extract user ID, username, and email
            user_id = decoded.get('sub', 'anonymous')
            username = decoded.get('cognito:username', 'anonymous')
            email = decoded.get('email', 'anonymous')
            
            return {
                'userId': user_id,
                'username': username,
                'email': email
            }
                
        except Exception as e:
            logger.error(f"Error processing token: {str(e)}")
            return {
                'userId': 'anonymous',
                'username': 'anonymous',
                'email': 'anonymous'
            }
            
    except Exception as e:
        logger.error(f"Error extracting user details: {str(e)}")
        return {
            'userId': 'anonymous',
            'username': 'anonymous',
            'email': 'anonymous'
        }

def response(status_code, body):
    """
    Create a standardized API Gateway response
    
    Args:
        status_code (int): HTTP status code
        body (dict): Response body
        
    Returns:
        dict: API Gateway response
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(body)
    }