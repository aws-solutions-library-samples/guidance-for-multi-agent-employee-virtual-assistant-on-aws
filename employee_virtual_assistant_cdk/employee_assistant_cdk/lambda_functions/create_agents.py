import boto3
import time
import uuid
import json
import os
import logging
from typing import Dict, List, Any, Optional

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Constants
FOUNDATION_MODEL = "anthropic.claude-3-haiku-20240307-v1:0"
CHECK_INTERVAL = 5  # seconds
PROJECT_TAG = "EVA"
ENVIRONMENT_TAG = "Production"

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main handler for the Lambda function. Creates specialized agents and a supervisor agent.
    
    Args:
        event: Lambda event data
        context: Lambda context
    
    Returns:
        Result with created agent details
    """
    # Initialize default response with required attributes
    response = {
        'PhysicalResourceId': f"agent-creation-{str(uuid.uuid4())[-8:]}",
        'Data': {
            'supervisorAgentId': 'NOT_CREATED',
            'supervisorAgentAliasId': 'NOT_CREATED',
            'KNOWLEDGE_BASES_JSON': '{}',
            'created_agents': '{}'
        }
    }
    
    # Handle DELETE request from CloudFormation
    if event.get('RequestType') == 'Delete':
        logger.info(f"Received DELETE request, returning original PhysicalResourceId: {event.get('PhysicalResourceId')}")
        response['PhysicalResourceId'] = event.get('PhysicalResourceId')
        return response
    
    # Get configuration parameters
    bedrock_role_arn = os.environ.get('BEDROCK_ROLE_ARN', event.get('BEDROCK_ROLE_ARN'))
    uuid_suffix = os.environ.get('UUID_SUFFIX', '')[-5:] or str(uuid.uuid4())[-5:]
    tavily_lambda_name = os.environ.get('TAVILY_LAMBDA_NAME', 'tavily_search')
    
    # Validate required parameters
    if not bedrock_role_arn:
        logger.error("Missing required BEDROCK_ROLE_ARN parameter")
        response['Status'] = 'FAILED'
        response['Reason'] = 'Bedrock Role ARN is required'
        return response
    
    try:
        # Get AWS account and region details
        session = boto3.session.Session()
        region = session.region_name
        sts_client = boto3.client("sts")
        account_id = sts_client.get_caller_identity()["Account"]
        
        # Initialize the Bedrock Agent client
        bedrock_agent_client = boto3.client('bedrock-agent', region_name=region)

        # Parse knowledge base IDs from environment variable
        knowledge_bases = {}
        try:
            kb_json_str = os.environ.get('KNOWLEDGE_BASES', '{}')
            logger.info(f"Raw KNOWLEDGE_BASES: {kb_json_str}")
            knowledge_bases = json.loads(kb_json_str)
            logger.info(f"Parsed knowledge bases: {knowledge_bases}")
        except json.JSONDecodeError:
            logger.error(f"Failed to parse KNOWLEDGE_BASES JSON: {kb_json_str}")
        
        # Create specialized agents
        logger.info("Creating specialized agents...")
        agent_configs = create_agent_configs(uuid_suffix, region, account_id, tavily_lambda_name)
        created_agents = create_specialized_agents(
            bedrock_agent_client, agent_configs, bedrock_role_arn, knowledge_bases
        )
        
        # Create supervisor agent
        logger.info("Creating supervisor agent...")
        supervisor_config = create_supervisor_config(uuid_suffix)
        supervisor_details = create_supervisor_agent(
            bedrock_agent_client, supervisor_config, bedrock_role_arn, 
            created_agents, agent_configs
        )
        
        # Validate supervisor details
        if not supervisor_details.get('agent_id') or not supervisor_details.get('agent_alias_id'):
            error_msg = f"Supervisor agent creation failed: missing required details"
            logger.error(error_msg)
            response['Status'] = 'FAILED'
            response['Reason'] = error_msg
            return response
        
        # Add supervisor to our results
        created_agents[supervisor_config["agent_name"]] = supervisor_details
        
        # Update response with successful values
        response['Data']['supervisorAgentId'] = supervisor_details['agent_id']
        response['Data']['supervisorAgentAliasId'] = supervisor_details['agent_alias_id']
        response['Data']['KNOWLEDGE_BASES_JSON'] = json.dumps(knowledge_bases)
        response['Data']['created_agents'] = json.dumps(created_agents)
        response['PhysicalResourceId'] = f"supervisor-agent-{supervisor_details['agent_id']}"
        
        logger.info(f"Successfully created supervisor agent with ID: {supervisor_details['agent_id']}")
        return response
        
    except Exception as e:
        logger.error(f"Error in Lambda execution: {str(e)}", exc_info=True)
        response['Status'] = 'FAILED'
        response['Reason'] = str(e)
        return response

def create_agent_configs(uuid_suffix: str, region: str, account_id: str, 
                       tavily_lambda_name: str) -> List[Dict[str, Any]]:
    """Create configurations for all specialized agents"""
    return [
        {
            "agent_name": f"eva_hr_{uuid_suffix}",
            "foundation_model": FOUNDATION_MODEL,
            "description": (
                "The HR Agent handles employee queries on leave policies, onboarding, performance reviews, "
                "and workplace concerns, providing accurate guidance and resources for HR-related processes."
            ),
            "instruction": (
                "You handle queries related to HR policies, employee relations, leave policies, onboarding, and career growth.\n\n"
                "Instructions:\n"
                "- Answer employee questions about leave policies, performance reviews, employee relations, and HR processes.\n"
                "- Guide employees on onboarding, company culture, and career progression.\n"
                "- Provide accurate information about policies and direct users to relevant HR resources when needed.\n\n"
                "Example Queries:\n"
                "- 'What is the company's parental leave policy?'\n"
                "- 'How do I escalate a workplace concern?'\n"
                "- 'What are the steps for onboarding as a new hire?'"
            ),
            "action_group_name": None,
            "action_group_executor": None,
            "action_group_function_name": None,
            "parameters": None,
        },
        {
            "agent_name": f"eva_payroll_{uuid_suffix}",
            "foundation_model": FOUNDATION_MODEL,
            "description": (
                "The Payroll Agent handles queries on salaries, deductions, tax forms, pay schedules, and direct deposits, "
                "ensuring employees receive accurate payroll and tax information."
            ),
            "instruction": (
                "You handle payroll-related questions, including salary, deductions, tax forms, and direct deposits.\n\n"
                "Instructions:\n"
                "- Provide details about pay schedules, tax deductions, and salary structures.\n"
                "- Guide employees on updating bank details or retrieving tax documents.\n"
                "- Ensure compliance with payroll policies.\n\n"
                "Example Queries:\n"
                "- 'When is the next payday?'\n"
                "- 'How do I update my direct deposit information?'\n"
                "- 'Where can I find my W-2 tax form?'"
            ),
            "action_group_name": None,
            "action_group_executor": None,
            "action_group_function_name": None,
            "parameters": None,
        },
        {
            "agent_name": f"eva_benefits_{uuid_suffix}",
            "foundation_model": FOUNDATION_MODEL,
            "description": (
                "The Benefits Agent provides information on health insurance, retirement plans, wellness programs, and "
                "enrollment options, helping employees understand and manage their benefits."
            ),
            "instruction": (
                "You assist employees with benefits-related queries, including healthcare, retirement plans, and wellness programs.\n\n"
                "Instructions:\n"
                "- Provide information on health insurance, dental/vision coverage, and retirement plans.\n"
                "- Guide employees on how to enroll in or modify benefits.\n"
                "- Address wellness program inquiries and eligibility requirements.\n\n"
                "Example Queries:\n"
                "- 'What healthcare plans are available to employees?'\n"
                "- 'How do I enroll in the 401(k) plan?'\n"
                "- 'What wellness programs does the company offer?'"
            ),
            "action_group_name": None,
            "action_group_executor": None,
            "action_group_function_name": None,
            "parameters": None,
        },
        {
            "agent_name": f"eva_it_helpdesk_{uuid_suffix}",
            "foundation_model": FOUNDATION_MODEL,
            "description": (
                "The IT Helpdesk Agent assists with tech support, troubleshooting, software access, password resets, and "
                "security policies, ensuring smooth IT operations and user support."
            ),
            "instruction": (
                "You handle queries related to IT support, including account unlock, password resets, software installation, and network connectivity issues.\n\n"
                "Instructions:\n"
                "- Assist employees with account unlock requests and password reset procedures.\n"
                "- Guide users through software installation steps and help troubleshoot installation issues.\n"
                "- Provide support for network connectivity problems and guide users on troubleshooting basic hardware issues.\n"
                "- Offer clear instructions for resolving common IT-related issues and escalate more complex problems to the appropriate team if needed.\n\n"
                "Example Queries:\n"
                "- 'How do I reset my account password?'\n"
                "- 'My account is locked. Can you help me unlock it?'\n"
                "- 'What should I do if I can't connect to the company VPN?'\n"
                "- 'How do I install the latest software update on my computer?'"
            ),
            "action_group_name": None,
            "action_group_executor": None,
            "action_group_function_name": None,
            "parameters": None,
        },
        {
            "agent_name": f"eva_training_{uuid_suffix}",
            "foundation_model": FOUNDATION_MODEL,
            "description": (
                "The Learning Management Agent assists with training programs, course enrollments, certifications, and "
                "professional development, guiding employees on growth opportunities and learning resources."
            ),
            "instruction": (
                "You handle queries related to employee learning and development, including training programs, "
                "skill-building resources, and course enrollment.\n\n"
                "Instructions:\n"
                "- Assist employees with finding and enrolling in relevant training programs and courses.\n"
                "- Provide information on available certifications, development opportunities, and learning paths.\n"
                "- Guide employees on how to track their learning progress and access course materials.\n"
                "- Offer insights into skill-building resources and help employees identify areas for professional growth.\n\n"
                "Example Queries:\n"
                "- 'How can I enroll in the new leadership training program?'\n"
                "- 'What certifications are available for project management skills?'\n"
                "- 'Where can I find resources for improving my coding skills?'\n"
                "- 'How do I track my progress in the online training portal?'"
            ),
            "action_group_name": None,
            "action_group_executor": None,
            "action_group_function_name": None,
            "parameters": None,
        },
        {
            "agent_name": f"eva_search_{uuid_suffix}",
            "foundation_model": FOUNDATION_MODEL,
            "description": (
                "AI agent designed to enhance employee productivity by efficiently retrieving real-time, relevant "
                "information from the web to address various work-related queries."
            ),
            "instruction": (
                "You are responsible for retrieving accurate, relevant, and up-to-date information from trusted "
                "online sources based on work-related queries posed by employees.\n\n"
                "Steps for Task Completion:\n"
                "1. Receive the user's query or request for information.\n"
                "2. Search for the most relevant artifacts on trusted online platforms and return actual URLs.\n"
                "3. If the user doesn't specify the content type (e.g., blog, video, code sample), ask for clarification."
            ),
            "action_group_name": "actions_web_search",
            "action_group_executor": {
                "lambda": f"arn:aws:lambda:{region}:{account_id}:function:{tavily_lambda_name}"
            },
            "action_group_function_name": "tavily_search",
            "parameters": [
                {
                    "name": "search_query",
                    "description": "The query to search the web with"
                }
            ]
        }
    ]


def create_supervisor_config(uuid_suffix: str) -> Dict[str, Any]:
    """Create configuration for the supervisor agent"""
    return {
        "agent_name": f"eva_supervisor_{uuid_suffix}",
        "foundation_model": FOUNDATION_MODEL,
        "description": (
            "The Supervisor Agent orchestrates all other agents, routes employee queries to the right agent, "
            "ensures accurate responses, and provides a seamless, unified support experience."
        ),
        "instruction": (
            "You are the Supervisor Agent, responsible for orchestrating multiple specialized agents (HR, IT Helpdesk, "
            "Payroll, Benefits, Training & Learning, and technical research).\n\n"
            "**Instructions:**\n"
            "- Classify user requests and route them to the appropriate agent(s).\n"
            "- Coordinate responses when multiple agents are needed.\n"
            "- Ensure clarity, accuracy, and consistency in responses.\n"
            "- Escalate appropriately when an agent lacks information.\n"
            "- Maintain a professional, helpful tone.\n"
            "- For unrelated questions, politely inform users that you assist only with employee-related inquiries."
        ),
        "action_group_name": None,
        "action_group_executor": None,
        "action_group_function_name": None,
        "parameters": None
    }

def create_agent_action_group_with_retry(
    bedrock_agent_client: Any,
    agent_id: str,
    action_group_name: str,
    action_group_executor: Dict[str, str],
    action_group_function_name: str,
    parameters: List[Dict[str, str]]
) -> None:
    """Create an action group for an agent with retry logic"""
    logger.info(f"Creating action group '{action_group_name}' for agent ID '{agent_id}'...")
    
    max_retries = 5
    base_delay = 5.0  # seconds
    
    for attempt in range(max_retries):
        try:
            # Build function schema
            function_schema = {
                'functions': [
                    {
                        'description': f"Function to {action_group_function_name}.",
                        'name': action_group_function_name,
                        'parameters': {}
                    }
                ]
            }
            
            # Add parameters to function schema
            if parameters:
                for param in parameters:
                    function_schema['functions'][0]['parameters'][param['name']] = {
                        'description': param['description'],
                        'required': True,
                        'type': 'string'
                    }
            
            # Create the action group
            bedrock_agent_client.create_agent_action_group(
                actionGroupExecutor=action_group_executor,
                actionGroupName=action_group_name,
                actionGroupState='ENABLED',
                agentId=agent_id,
                agentVersion='DRAFT',
                clientToken=str(uuid.uuid4()),
                description=f"Action group for {action_group_name}",
                functionSchema=function_schema
            )
            
            logger.info(f"Action group '{action_group_name}' created successfully.")
            return  # Success, exit function
            
        except Exception as e:
            delay = base_delay * (2 ** attempt)
            if "Agent is in" in str(e) or "ValidationException" in str(e):
                if attempt < max_retries - 1:
                    logger.warning(f"Agent not ready for action group creation. Waiting {delay}s before retry {attempt+1}/{max_retries}")
                    time.sleep(delay)
                else:
                    logger.error(f"Failed to create action group after {max_retries} attempts: {str(e)}")
                    raise
            else:
                logger.error(f"Error creating action group: {str(e)}")
                raise

def create_specialized_agents(
    bedrock_agent_client: Any,
    agent_configs: List[Dict[str, Any]],
    bedrock_role_arn: str,
    knowledge_bases: Dict[str, str]
) -> Dict[str, Dict[str, str]]:
    """Create all specialized agents"""
    created_agents = {}
    
    for agent_config in agent_configs:
        agent_name = agent_config['agent_name']
        logger.info(f"Creating agent: {agent_name}")
        
        # Add knowledge base ID if available for this agent type
        agent_type = get_agent_type(agent_name)
        if agent_type and agent_type in knowledge_bases:
            agent_config['knowledge_base_id'] = knowledge_bases[agent_type]
        
        try:
            # Create and configure the agent
            agent_id = create_agent(bedrock_agent_client, agent_name, agent_config, bedrock_role_arn)
            
            # Wait for agent to be in a valid state before proceeding
            # This is critical! The agent must be ready before creating action groups
            logger.info(f"Waiting for agent {agent_name} to be in a valid state...")
            wait_for_agent_status(bedrock_agent_client, agent_id, ['PREPARED', 'NOT_PREPARED'], 60, 5)
            
            # Create action group if needed
            if agent_config['action_group_name']:
                create_agent_action_group_with_retry(
                    bedrock_agent_client,
                    agent_id,
                    agent_config['action_group_name'],
                    agent_config['action_group_executor'],
                    agent_config['action_group_function_name'],
                    agent_config['parameters']
                )
            
            # Associate knowledge base if provided
            if 'knowledge_base_id' in agent_config:
                associate_knowledge_base(
                    bedrock_agent_client,
                    agent_id,
                    agent_config['knowledge_base_id'],
                    agent_type,
                    agent_name
                )
            
            # Prepare the agent
            prepare_agent(bedrock_agent_client, agent_id)
            wait_for_agent_prepared(bedrock_agent_client, agent_id)
            
            # Create an agent alias
            alias_name = f"{agent_name}_alias"
            agent_alias_id = create_agent_alias(bedrock_agent_client, agent_id, alias_name, f"Alias for {agent_name}")
            
            created_agents[agent_name] = {
                'agent_id': agent_id,
                'agent_alias_id': agent_alias_id
            }
            
        except Exception as e:
            logger.error(f"Error creating agent {agent_name}: {str(e)}")
            # Continue with next agent
    
    return created_agents


def create_supervisor_agent(
    bedrock_agent_client: Any,
    supervisor_config: Dict[str, Any],
    bedrock_role_arn: str,
    created_agents: Dict[str, Dict[str, str]],
    agent_configs: List[Dict[str, Any]]
) -> Dict[str, str]:
    """Create and configure the supervisor agent"""
    agent_name = supervisor_config["agent_name"]
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Creating supervisor agent: {agent_name} (attempt {attempt+1}/{max_retries})")
            
            # Check if agent already exists and delete if needed
            check_and_delete_existing_agent(bedrock_agent_client, agent_name)
            
            # Create the supervisor agent with SUPERVISOR mode
            agent_id = create_agent(
                bedrock_agent_client,
                agent_name,
                supervisor_config,
                bedrock_role_arn,
                'SUPERVISOR'
            )
            
            # Wait for supervisor to be in valid state
            wait_for_agent_status(bedrock_agent_client, agent_id, ['PREPARED', 'NOT_PREPARED'])
            
            # Add collaborators to supervisor
            add_collaborators_to_supervisor(
                bedrock_agent_client,
                agent_id,
                created_agents,
                agent_configs
            )
            
            # Prepare the supervisor agent
            prepare_agent(bedrock_agent_client, agent_id)
            wait_for_agent_prepared(bedrock_agent_client, agent_id)
            
            # Create supervisor alias
            alias_name = f"{agent_name}_alias"
            agent_alias_id = create_agent_alias(
                bedrock_agent_client,
                agent_id,
                alias_name,
                f"Alias for {agent_name}"
            )
            
            logger.info(f"Successfully created supervisor agent {agent_name}")
            return {
                'agent_id': agent_id,
                'agent_alias_id': agent_alias_id
            }
            
        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed: {str(e)}")
            if attempt < max_retries - 1:
                logger.info(f"Waiting before retry #{attempt+2}...")
                time.sleep(10)  # Wait before retrying
            else:
                logger.error(f"All {max_retries} attempts failed")
                raise
    
    # This should not be reached due to the exception in the loop
    raise Exception(f"Failed to create supervisor agent after {max_retries} attempts")


def check_and_delete_existing_agent(bedrock_agent_client: Any, agent_name: str) -> Optional[str]:
    """Check if agent exists and delete it if it does"""
    logger.info(f"Checking if agent '{agent_name}' already exists...")
    list_agents_response = bedrock_agent_client.list_agents(maxResults=100)
    agent_id = None
    
    for existing_agent in list_agents_response.get('agentSummaries', []):
        if existing_agent['agentName'] == agent_name:
            agent_id = existing_agent['agentId']
            logger.info(f"Agent '{agent_name}' already exists with ID '{agent_id}'")
            break
    
    if agent_id:
        logger.info(f"Deleting existing agent '{agent_name}'...")
        bedrock_agent_client.delete_agent(
            agentId=agent_id,
            skipResourceInUseCheck=True
        )
        
        # Wait for deletion
        logger.info(f"Waiting for agent '{agent_name}' deletion...")
        while True:
            time.sleep(CHECK_INTERVAL)
            try:
                bedrock_agent_client.get_agent(agentId=agent_id)
            except bedrock_agent_client.exceptions.ResourceNotFoundException:
                logger.info(f"Agent '{agent_name}' successfully deleted.")
                break
    
    return agent_id


def create_agent(
    bedrock_agent_client: Any,
    agent_name: str,
    agent_config: Dict[str, Any],
    bedrock_role_arn: str,
    agent_collaboration: Optional[str] = None
) -> str:
    """Create a Bedrock agent"""
    logger.info(f"Creating agent '{agent_name}'...")
    create_params = {
        'agentName': agent_name,
        'agentResourceRoleArn': bedrock_role_arn,
        'description': agent_config['description'],
        'foundationModel': agent_config['foundation_model'],
        'instruction': agent_config['instruction'],
        'tags': {
            'Environment': ENVIRONMENT_TAG,
            'Project': PROJECT_TAG
        }
    }
    
    if agent_collaboration:
        create_params['agentCollaboration'] = agent_collaboration
    
    response = bedrock_agent_client.create_agent(**create_params)
    agent_id = response['agent']['agentId']
    logger.info(f"Created agent '{agent_name}' with ID: {agent_id}")
    return agent_id


def create_agent_action_group(
    bedrock_agent_client: Any,
    agent_id: str,
    action_group_name: str,
    action_group_executor: Dict[str, str],
    action_group_function_name: str,
    parameters: List[Dict[str, str]]
) -> None:
    """Create an action group for an agent"""
    logger.info(f"Creating action group '{action_group_name}' for agent ID '{agent_id}'...")
    
    # Build function schema
    function_schema = {
        'functions': [
            {
                'description': f"Function to {action_group_function_name}.",
                'name': action_group_function_name,
                'parameters': {}
            }
        ]
    }
    
    # Add parameters to function schema
    if parameters:
        for param in parameters:
            function_schema['functions'][0]['parameters'][param['name']] = {
                'description': param['description'],
                'required': True,
                'type': 'string'
            }
    
    # Create the action group
    bedrock_agent_client.create_agent_action_group(
        actionGroupExecutor=action_group_executor,
        actionGroupName=action_group_name,
        actionGroupState='ENABLED',
        agentId=agent_id,
        agentVersion='DRAFT',
        clientToken=str(uuid.uuid4()),
        description=f"Action group for {action_group_name}",
        functionSchema=function_schema
    )
    logger.info(f"Action group '{action_group_name}' created successfully.")


def prepare_agent(bedrock_agent_client: Any, agent_id: str) -> str:
    """Prepare a Bedrock agent"""
    logger.info(f"Preparing agent with ID '{agent_id}'...")
    response = bedrock_agent_client.prepare_agent(agentId=agent_id)
    return response['agentStatus']


def create_agent_alias(bedrock_agent_client: Any, agent_id: str, alias_name: str, description: str) -> str:
    """Create an alias for a Bedrock agent"""
    logger.info(f"Creating alias '{alias_name}' for agent ID '{agent_id}'...")
    response = bedrock_agent_client.create_agent_alias(
        agentAliasName=alias_name,
        agentId=agent_id,
        description=description,
        tags={
            'Environment': ENVIRONMENT_TAG,
            'Project': PROJECT_TAG
        }
    )
    alias_id = response['agentAlias']['agentAliasId']
    logger.info(f"Created alias '{alias_name}' with ID: {alias_id}")
    return alias_id


def associate_knowledge_base(
    bedrock_agent_client: Any,
    agent_id: str,
    knowledge_base_id: str,
    agent_type: Optional[str] = None,
    agent_name: Optional[str] = None
) -> Dict[str, Any]:
    """Associate a knowledge base with an agent"""
    if not knowledge_base_id:
        logger.info(f"No knowledge base ID provided for agent with ID '{agent_id}'. Skipping association.")
        return {}

    # Define specific knowledge base descriptions for each agent type
    knowledge_base_descriptions = {
        "hr": "Use this knowledge base to provide accurate HR-related information, including policies, leave, performance reviews, and employee guidelines.",
        "payroll": "Use this knowledge base to provide accurate payroll-related information, including salaries, deductions, tax compliance, and payment schedules.",
        "benefits": "The Benefits Agent should utilize the integrated Knowledge Base to provide detailed information on employee benefits",
        "helpdesk": "Use this knowledge base to provide accurate IT-related information, including account locks, password reset, software installation instructions, network connectivity issues, and hardware support.",
        "training": "Use this knowledge base to provide accurate information on training programs, course enrollment, certifications, and professional development opportunities."
    }
    
    try:
        logger.info(f"Associating knowledge base '{knowledge_base_id}' with agent ID '{agent_id}'...")
        
        # Get the appropriate description based on agent type
        description = knowledge_base_descriptions.get(
            agent_type, 
            f"Knowledge base for {agent_name or 'the agent'}"
        )
        
        # Associate the knowledge base
        response = bedrock_agent_client.associate_agent_knowledge_base(
            agentId=agent_id,
            agentVersion='DRAFT',
            description=description,
            knowledgeBaseId=knowledge_base_id,
            knowledgeBaseState='ENABLED'
        )
        
        logger.info(f"Knowledge base '{knowledge_base_id}' successfully associated with agent ID '{agent_id}'.")
        return response
    except Exception as e:
        logger.error(f"Error associating knowledge base '{knowledge_base_id}' with agent ID '{agent_id}': {str(e)}")
        raise e


def wait_for_agent_status(bedrock_agent_client: Any, agent_id: str, target_statuses: List[str], max_attempts: int = 30, check_interval: int = 5) -> None:
    """Wait for an agent to reach one of the target statuses"""
    logger.info(f"Waiting for agent with ID '{agent_id}' to be in one of these states: {target_statuses}...")
    
    for attempt in range(max_attempts):
        try:
            get_agent_response = bedrock_agent_client.get_agent(agentId=agent_id)
            agent_status = get_agent_response['agent']['agentStatus']
            
            if agent_status in target_statuses:
                logger.info(f"Agent with ID '{agent_id}' is in state '{agent_status}'.")
                return
            elif agent_status == 'FAILED':
                raise Exception(f"Agent with ID '{agent_id}' creation failed.")
            else:
                logger.info(f"Agent with ID '{agent_id}' is still in '{agent_status}' state (attempt {attempt+1}/{max_attempts})...")
                time.sleep(check_interval)
        except Exception as e:
            if "ResourceNotFoundException" in str(e) and attempt < max_attempts - 1:
                # Agent might not be fully registered yet
                logger.info(f"Agent not found yet, waiting... (attempt {attempt+1}/{max_attempts})")
                time.sleep(check_interval)
            else:
                raise
                
    raise Exception(f"Timed out waiting for agent with ID '{agent_id}' to reach one of these states: {target_statuses}")


def wait_for_agent_prepared(bedrock_agent_client: Any, agent_id: str) -> None:
    """Wait for an agent to be fully prepared"""
    logger.info(f"Waiting for agent with ID '{agent_id}' to be fully prepared...")
    while True:
        time.sleep(CHECK_INTERVAL)
        get_agent_response = bedrock_agent_client.get_agent(agentId=agent_id)
        agent_status = get_agent_response['agent']['agentStatus']
        
        if agent_status == 'PREPARED':
            logger.info(f"Agent with ID '{agent_id}' is fully prepared.")
            break
        elif agent_status == 'FAILED':
            raise Exception(f"Agent with ID '{agent_id}' preparation failed.")
        else:
            logger.info(f"Agent with ID '{agent_id}' is still in '{agent_status}' state...")


def get_agent_type(agent_name: str) -> Optional[str]:
    """Determine the agent type from the agent name"""
    if "hr" in agent_name.lower():
        return "hr"
    elif "payroll" in agent_name.lower():
        return "payroll"
    elif "benefits" in agent_name.lower():
        return "benefits"
    elif "helpdesk" in agent_name.lower():
        return "helpdesk"
    elif "training" in agent_name.lower():
        return "training"
    elif "search" in agent_name.lower():
        return "search"
    return None


def create_agent_alias_descriptor(bedrock_agent_client: Any, agent_name: str) -> Optional[Dict[str, str]]:
    """Create an agent alias descriptor for collaboration"""
    logger.info(f"Creating alias descriptor for agent '{agent_name}'...")
    
    # List agents to find the agentId for the given agent name
    list_agents_response = bedrock_agent_client.list_agents(maxResults=100)
    agent_id = None
    for existing_agent in list_agents_response.get('agentSummaries', []):
        if existing_agent['agentName'] == agent_name:
            agent_id = existing_agent['agentId']
            break
    
    if not agent_id:
        logger.warning(f"Could not find agent ID for '{agent_name}'")
        return None
    
    # List agent aliases for the given agentId
    alias_name = f"{agent_name}_alias"
    list_aliases_response = bedrock_agent_client.list_agent_aliases(agentId=agent_id)
    
    # Return the alias ARN if found
    for alias in list_aliases_response.get('agentAliasSummaries', []):
        if alias['agentAliasName'] == alias_name:
            get_agent_alias_response = bedrock_agent_client.get_agent_alias(
                agentAliasId=alias['agentAliasId'], 
                agentId=agent_id
            )
            alias_arn = get_agent_alias_response['agentAlias']['agentAliasArn']
            logger.info(f"Found alias ARN for '{agent_name}': {alias_arn}")
            return {'aliasArn': alias_arn}
    
    logger.warning(f"Could not find alias for '{agent_name}'")
    return None


def add_collaborators_to_supervisor(
    bedrock_agent_client: Any,
    supervisor_id: str,
    created_agents: Dict[str, Dict[str, str]],
    agents: List[Dict[str, Any]]
) -> int:
    """Add collaborators to a supervisor agent"""
    logger.info(f"Adding collaborators to supervisor with ID '{supervisor_id}'...")
    
    # Define specific collaboration instructions for each agent type
    collaboration_instructions = {
        "hr": "The HR Support Specialist assists with employee queries related to HR policies and procedures.",
        "payroll": "The Payroll Support Specialist assists with payroll inquiries and tax information.",
        "benefits": "The Benefits Support Specialist assists with benefits enrollment and plan information.",
        "helpdesk": "The IT Support Specialist assists with account issues and technical troubleshooting.",
        "training": "The Learning Support Specialist assists with training programs and certifications.",
        "search": "The Web Search AI agent retrieves relevant information from trusted online sources."
    }
    
    collaborator_count = 0
    
    for agent in agents:
        agent_name = agent['agent_name']
        if agent_name in created_agents:
            logger.info(f"Adding collaborator '{agent_name}' to supervisor...")
            
            agent_type = get_agent_type(agent_name)
            instruction = collaboration_instructions.get(
                agent_type, 
                f"Use the {agent_name} for specialized tasks in its domain."
            )
            
            # Get descriptor for collaborator
            agent_descriptor = create_agent_alias_descriptor(bedrock_agent_client, agent_name)
            
            if agent_descriptor:
                try:
                    bedrock_agent_client.associate_agent_collaborator(
                        agentDescriptor=agent_descriptor,
                        agentId=supervisor_id,
                        agentVersion='DRAFT',
                        collaborationInstruction=instruction,
                        collaboratorName=agent_name
                    )
                    logger.info(f"Collaborator '{agent_name}' added successfully with custom instructions.")
                    collaborator_count += 1
                except Exception as e:
                    logger.error(f"Error adding collaborator '{agent_name}': {str(e)}")
    
    # Verify that at least one collaborator was added
    if collaborator_count == 0:
        raise Exception("No collaborators were added to the supervisor agent. Cannot proceed with preparation.")
    
    return collaborator_count