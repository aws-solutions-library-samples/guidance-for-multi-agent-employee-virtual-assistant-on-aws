import boto3
import uuid
import json
import time
# import random
import os
import base64
from datetime import datetime, timezone
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    Lambda handler to invoke Bedrock agent and store conversation in DynamoDB
    
    Args:
        event (dict): Lambda input event
        context (object): Lambda context
        
    Returns:
        dict: API Gateway response with agent response
    """
    # Parse input
    body = json.loads(event.get('body', '{}'))
    input_text = body.get('message')
    session_id = body.get('sessionId', str(uuid.uuid4()))
    user_details = extract_user_details(event)
    
    logger.info(f"Processing request - user: {user_details['username']}, session: {session_id}")
    
    # Input validation
    if not input_text:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Message is required'})
        }
    
    # Initialize Bedrock Agent client
    session = boto3.session.Session()
    region_name = session.region_name
    client = boto3.client('bedrock-agent-runtime', region_name=region_name)
    
    # Get agent IDs from environment
    agent_id = os.environ.get('AGENT_ID')
    agent_alias_id = os.environ.get('AGENT_ALIAS_ID')
    
    # Retry configuration
    max_retries = 5
    base_delay = 1  # seconds
    
    full_response = ""
    thinking_steps = []
    attempt = 0
    
    while attempt < max_retries:
        try:
            # Make API call to Bedrock Agent
            response = client.invoke_agent(
                inputText=input_text,
                agentId=agent_id,
                agentAliasId=agent_alias_id,
                sessionId=session_id,
                enableTrace=True
            )
            
            # Process response stream
            for event_data in response['completion']:
                # Handle output chunks
                if 'chunk' in event_data:
                    chunk_data = event_data['chunk']['bytes'].decode('utf8')
                    full_response += chunk_data
                
                # Handle trace events (thinking steps)
                if 'trace' in event_data:
                    if 'trace' in event_data['trace']:
                        if 'orchestrationTrace' in event_data['trace']['trace']:
                            orch = event_data['trace']['trace']['orchestrationTrace']
                            if 'rationale' in orch:
                                step_text = orch['rationale']['text']
                                thinking_steps.append(step_text)
            
            # Save the conversation to DynamoDB
            save_conversation(user_details, session_id, input_text, full_response, thinking_steps)
            
            # Successful completion, break the retry loop
            break
            
        except Exception as e:
            logger.error(f"Error invoking agent: {str(e)}")
            attempt += 1
            error_message = str(e)
            
            # If we've exhausted our retries, return the error
            if attempt >= max_retries:
                return {
                    'statusCode': 500,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'error': f"Failed after {max_retries} attempts: {error_message}"
                    })
                }
            
            # Apply exponential backoff before retry
            time.sleep(base_delay * (2 ** (attempt - 1))) # + random.uniform(0, 1))
    
    logger.info("Returning response to client")
    
    # Return successful response
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'response': full_response,
            'thinkingSteps': thinking_steps,
            'sessionId': session_id
        })
    }

def extract_user_details(event):
    """
    Extract user details from the Cognito JWT token
    
    Args:
        event (dict): Lambda input event
        
    Returns:
        dict: User details
    """
    try:
        logger.info("Extracting user details from event")
        
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
            
            logger.info(f"Extracted user details - userId: {user_id}, username: {username}")
            
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

def save_conversation(user_details, session_id, user_query, response, thinking_steps):
    """
    Save the conversation to DynamoDB
    
    Args:
        user_details (dict): User information
        session_id (str): Session ID
        user_query (str): User's input
        response (str): AI response
        thinking_steps (list): Thinking steps from the AI
    """
    try:
        # Initialize DynamoDB client
        dynamodb = boto3.resource('dynamodb')
        conversation_table_name = os.environ.get('CONVERSATION_TABLE')
        
        if not conversation_table_name:
            logger.warning("No CONVERSATION_TABLE environment variable set")
            return
            
        conversation_table = dynamodb.Table(conversation_table_name)
        
        # Generate a unique message ID
        message_id = str(uuid.uuid4())
        
        # Format the timestamp as YYYY-MM-DD HH:MM:SS
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        
        # Save the conversation
        conversation_table.put_item(
            Item={
                'userId': user_details['userId'],
                'timestamp': timestamp,
                'messageId': message_id,
                'sessionId': session_id,
                'username': user_details['username'],
                'email': user_details['email'],
                'userQuery': user_query,
                'response': response,
                'thinkingSteps': thinking_steps if thinking_steps else []
            }
        )
        logger.info(f"Conversation saved with messageId: {message_id}")
        
    except Exception as e:
        logger.error(f"Error saving conversation to DynamoDB: {str(e)}")