import boto3
import json
import os
import base64
from datetime import datetime
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    Lambda handler to retrieve conversation history for a user
    
    Args:
        event (dict): Lambda input event
        context (object): Lambda context
        
    Returns:
        dict: API Gateway response with conversation history
    """
    try:
        logger.info("Processing conversation history request")
        
        # Extract user details from the token
        user_details = extract_user_details(event)
        logger.info(f"User ID: {user_details['userId']}")
        
        # Initialize DynamoDB client
        dynamodb_client = boto3.client('dynamodb')
        conversation_table_name = os.environ.get('CONVERSATION_TABLE')
        
        if not conversation_table_name:
            logger.error("CONVERSATION_TABLE environment variable not set")
            return response(500, {'error': 'Conversation table not configured'})
            
        logger.info(f"Querying table: {conversation_table_name}")
        
        # Query the table for user's conversations
        query_result = dynamodb_client.query(
            TableName=conversation_table_name,
            KeyConditionExpression='userId = :userId',
            ExpressionAttributeValues={
                ':userId': {'S': user_details['userId']}
            },
            ScanIndexForward=False,  # Sort descending by timestamp
            Limit=100  # Limit to 100 items
        )
        
        logger.info(f"Query returned {len(query_result.get('Items', []))} items")
        
        # Process results to get unique sessions with their latest message
        sessions = {}
        for item in query_result.get('Items', []):
            session_id = item.get('sessionId', {}).get('S', '')
            timestamp = item.get('timestamp', {}).get('S', '')
            
            # If we haven't seen this session or this message is newer
            if session_id not in sessions or timestamp > sessions[session_id]['timestamp']:
                sessions[session_id] = {
                    'sessionId': session_id,
                    'timestamp': timestamp,
                    'latestMessage': item.get('userQuery', {}).get('S', ''),
                    'username': item.get('username', {}).get('S', 'anonymous'),
                }
        
        # Convert to list and sort by timestamp (most recent first)
        conversation_history = list(sessions.values())
        
        # Fix date format to handle potential future dates
        for session in conversation_history:
            try:
                dt = datetime.strptime(session['timestamp'], '%Y-%m-%d %H:%M:%S')
                # Format is already correct
            except ValueError:
                # If date is invalid, use current timestamp
                session['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Sort by timestamp and limit results
        conversation_history.sort(key=lambda x: x['timestamp'], reverse=True)
        conversation_history = conversation_history[:20]  # Limit to 20 sessions
        
        logger.info(f"Returning {len(conversation_history)} unique conversations")
        
        return response(200, {
            'conversations': conversation_history
        })
    
    except Exception as e:
        logger.error(f"Error retrieving conversation history: {str(e)}", exc_info=True)
        return response(500, {'error': f'Failed to retrieve conversation history: {str(e)}'})

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