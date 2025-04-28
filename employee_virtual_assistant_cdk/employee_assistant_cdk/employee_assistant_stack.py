from aws_cdk import (
    Stack, Duration, RemovalPolicy, CfnOutput, CustomResource,
    aws_s3 as s3,
    aws_kms as kms,
    aws_ec2 as ec2,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_apigateway as apigw,
    aws_cognito as cognito,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_s3_deployment as s3deploy,
    aws_iam as iam,
    aws_logs as logs,
    aws_s3_notifications as s3n,
    custom_resources as cr,
    Aws
)
from constructs import Construct

class EmployeeAssistantStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, uuid_value: str, tavily_api_key: str, **kwargs) -> None:
        """
        Initialize the Employee Assistant Stack
        
        Args:
            scope: CDK construct scope
            construct_id: Stack ID
            uuid_value: Unique ID for resource naming
            tavily_api_key: API key for Tavily search service
        """
        super().__init__(scope, construct_id, **kwargs)

        # Use the last 5 characters of the UUID for resource naming
        uuid_suffix = uuid_value[-5:]

        # Define resource names with UUID suffix to ensure uniqueness
        # bedrock_role_name = f"emp-virtual-assistant-bedrock-role-{uuid_suffix}"
        # conversation_table_name = f"emp-virtual-assistant-conversations-{uuid_suffix}"
        data_assets_bucket_name = f"{Aws.ACCOUNT_ID}-{Aws.REGION}-emp-virtual-assistant-data-{uuid_suffix}"
        website_assets_bucket_name = f"{Aws.ACCOUNT_ID}-{Aws.REGION}-emp-virtual-assistant-website-{uuid_suffix}"
        create_oss_lambda_name = f"emp-virtual-assistant-oss-{uuid_suffix}"
        create_bedrock_kb_lambda_name = f"emp-virtual-assistant-bedrock-create-kb-{uuid_suffix}"
        create_bedrock_agent_lambda_name = f"emp-virtual-assistant-bedrock-create-agent-{uuid_suffix}"
        invoke_bedrock_agent_lambda_name = f"emp-virtual-assistant-bedrock-invoke-agent-{uuid_suffix}"
        get_conversation_history_lambda_name = f"emp-virtual-assistant-get-conversation-history-{uuid_suffix}"
        get_conversation_message_lambda_name = f"emp-virtual-assistant-get-conversation-message-{uuid_suffix}"
        tavily_search_lambda_name = f"emp-virtual-assistant-tavily-search-{uuid_suffix}"
        upload_files_lambda_name = f"emp-virtual-assistant-upload-files-{uuid_suffix}"
        process_upload_lambda_name = f"emp-virtual-assistant-process-upload-{uuid_suffix}"
        rest_api_name = f"emp-virtual-assistant-api-{uuid_suffix}"
        cognito_user_pool_name = f"emp-virtual-assistant-user-pool-{uuid_suffix}"
        cognito_user_pool_client_name = f"emp-virtual-assistant-user-pool-client-{uuid_suffix}"
        cloud_front_distribution_name = f"emp-virtual-assistant-website-{uuid_suffix}"

        #######################
        # NETWORKING RESOURCES
        #######################
        
        # Create a VPC for Lambda functions
        lambda_vpc = ec2.Vpc(
            self, "LambdaVpc",
            max_azs=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                    map_public_ip_on_launch=False
                )
            ]
        )

        # Create security group for Lambda functions
        lambda_sg = ec2.SecurityGroup(
            self, "LambdaSecurityGroup",
            vpc=lambda_vpc,
            description="Security group for Lambda functions",
            allow_all_outbound=True
        )

        # Create log group for VPC flow logs:
        vpc_flow_logs_group = logs.LogGroup(
            self, "VPCFlowLogsGroup",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Create and attach VPC flow logs:
        lambda_vpc.add_flow_log(
            "FlowLogs",
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(vpc_flow_logs_group),
            traffic_type=ec2.FlowLogTrafficType.ALL
        )
        
        #######################
        # IAM RESOURCES
        #######################
        
        # IAM role for Bedrock with necessary permissions
        bedrock_role = iam.Role(
            self, "BedrockRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonBedrockFullAccess"),
            ],
            inline_policies={
                "BedrockPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "bedrock:CreateModelInvocationJob",
                                "bedrock:GetModelInvocationJob",
                                "bedrock:ListFoundationModels",
                                "bedrock:GetFoundationModel", 
                                "bedrock:InvokeModel",
                                "bedrock:CreateAgent",
                                "bedrock:GetAgent", 
                                "bedrock:UpdateAgent",
                                "bedrock:DeleteAgent",
                                "bedrock:ListAgents",
                                "bedrock:PrepareAgent",
                                "bedrock:CreateAgentAlias",
                                "bedrock:GetAgentAlias",
                                "bedrock:CreateKnowledgeBase",
                                "bedrock:GetKnowledgeBase", 
                                "bedrock:AssociateAgentKnowledgeBase",
                                "bedrock:InvokeAgent",
                                "bedrock:InvokeModel"
                            ],
                            resources=[
                                f"arn:aws:bedrock:{Aws.REGION}:{Aws.ACCOUNT_ID}:foundation-model/*",
                                f"arn:aws:bedrock:{Aws.REGION}:{Aws.ACCOUNT_ID}:agent/*",
                                f"arn:aws:bedrock:{Aws.REGION}:{Aws.ACCOUNT_ID}:knowledge-base/*"
                            ],
                        )
                    ]
                )
            }
        )

        #######################
        # STORAGE RESOURCES
        #######################

        # S3 bucket for PDF documents and knowledge base data
        pdf_bucket = s3.Bucket(
            self, "PDFBucket",
            bucket_name=data_assets_bucket_name,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(365)  # Auto-delete files after 1 year
                )
            ]
        )

        # Configure CORS for S3 bucket to allow browser uploads
        pdf_bucket.add_cors_rule(
            allowed_methods=[s3.HttpMethods.PUT, s3.HttpMethods.POST, s3.HttpMethods.GET],
            allowed_origins=["*"],
            allowed_headers=["*"],
            max_age=3000
        )

        # Deploy initial PDF files to S3
        s3deploy.BucketDeployment(
            self, "DeployPDFs",
            sources=[s3deploy.Source.asset("employee_assistant_cdk/assets")],
            destination_bucket=pdf_bucket,
        )

        # S3 bucket for hosting the React app
        website_bucket = s3.Bucket(
            self, "WebsiteBucket",
            bucket_name=website_assets_bucket_name,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(365)  # Auto-delete old files after 1 year
                )
            ]
        )

        # S3 bucket for CloudFront logs
        cloudfront_logs_bucket_name = f"{Aws.ACCOUNT_ID}-{Aws.REGION}-emp-virtual-assistant-logs-{uuid_suffix}"
        cloudfront_logs_bucket = s3.Bucket(
            self, "CloudFrontLogsBucket",
            bucket_name=cloudfront_logs_bucket_name,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_PREFERRED,  # Required for CloudFront logs
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(90)  # Auto-delete logs after 90 days
                )
            ]
        )

        # Grant CloudFront permission to write logs to the bucket
        cloudfront_logs_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowCloudFrontLogDelivery",
                principals=[iam.ServicePrincipal("delivery.logs.amazonaws.com")],
                actions=["s3:PutObject"],
                resources=[f"{cloudfront_logs_bucket.bucket_arn}/*"]
            )
        )

        # Required for CloudFront logs
        cloudfront_logs_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowCloudFrontServicePrincipalToWrite",
                principals=[iam.ServicePrincipal("cloudfront.amazonaws.com")],
                actions=["s3:GetBucketAcl", "s3:PutBucketAcl"],
                resources=[cloudfront_logs_bucket.bucket_arn]
            )
        )

        # KMS key for DynamoDB encryption
        dynamodb_kms_key = kms.Key(
            self, "ConversationTableKey",
            description="KMS key for DynamoDB conversation table",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.DESTROY
        )

        # DynamoDB table for conversation history
        conversation_table = dynamodb.Table(
            self, "ConversationHistoryTable",
            partition_key=dynamodb.Attribute(
                name="userId",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp", 
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True,
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=dynamodb_kms_key
        )

        # Add GSI for querying by sessionId
        conversation_table.add_global_secondary_index(
            index_name="sessionId-timestamp-index",
            partition_key=dynamodb.Attribute(
                name="sessionId", 
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        #######################
        # LAMBDA RESOURCES
        #######################
        
        # Lambda layer with dependencies
        requests_layer = lambda_.LayerVersion(
            self, "RequestsLayer",
            code=lambda_.Code.from_asset("layer"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="Layer containing the requests and other required libraries",
        )

        # Lambda for Tavily search integration
        tavily_lambda = lambda_.Function(
            self, "TavilyAPILambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset("employee_assistant_cdk/lambda_functions"),
            handler="tavily_api.handler",
            timeout=Duration.minutes(15),
            layers=[requests_layer],
            environment={
                "TAVILY_API_KEY": tavily_api_key
            },
            function_name=tavily_search_lambda_name,
            vpc=lambda_vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[lambda_sg],
            reserved_concurrent_executions=10 
        )
        tavily_lambda.apply_removal_policy(RemovalPolicy.DESTROY)

        # Add permission for Bedrock to invoke the Tavily Lambda
        tavily_lambda.add_permission(
            "AllowBedrockInvoke",
            principal=iam.ServicePrincipal("bedrock.amazonaws.com"),
            action="lambda:InvokeFunction"
        )

        # Grant logging permissions to Tavily Lambda
        tavily_lambda.add_to_role_policy(
            self.create_restricted_logs_policy(tavily_search_lambda_name)
        )

        # Lambda for OpenSearch Serverless policy and collection setup
        create_policy_collection_lambda = lambda_.Function(
            self, "CreatePolicyCollectionLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset("employee_assistant_cdk/lambda_functions"),
            handler="create_oss.handler",
            timeout=Duration.minutes(15),
            layers=[requests_layer],
            environment={
                "S3_BUCKET_NAME": pdf_bucket.bucket_name,
                "UUID_SUFFIX": uuid_value,
                "BEDROCK_ROLE_ARN": bedrock_role.role_arn,
            },
            function_name=create_oss_lambda_name,
            vpc=lambda_vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[lambda_sg],
            reserved_concurrent_executions=10 
        )
        create_policy_collection_lambda.apply_removal_policy(RemovalPolicy.DESTROY)

        # Grant permissions to OpenSearch Lambda
        pdf_bucket.grant_read(create_policy_collection_lambda)
        create_policy_collection_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "iam:GetRole",
                    "iam:UpdateAssumeRolePolicy",
                    "iam:PutRolePolicy",
                    "iam:GetRolePolicy",
                    "iam:CreateServiceLinkedRole",
                ],
                resources=[
                    f"arn:aws:iam::{Aws.ACCOUNT_ID}:role/*"
                ]
            )
        )

        # Second policy statement for AOSS actions
        create_policy_collection_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "aoss:CreateCollection",
                    "aoss:CreateSecurityPolicy",
                    "aoss:ListCollections",
                    "aoss:BatchGetCollection",
                    "aoss:CreateAccessPolicy",
                    "aoss:GetAccessPolicy",
                    "aoss:GetSecurityPolicy",
                    "aoss:APIAccessAll"
                ],
                resources=["*"]
            )
        )
        # Policy statement with restricted resource for PassRole
        create_policy_collection_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[bedrock_role.role_arn]
            )
        )
        # Grant logging permissions to Lambda
        create_policy_collection_lambda.add_to_role_policy(
            self.create_restricted_logs_policy(create_oss_lambda_name)
        )

        # Custom resource provider for OpenSearch setup
        policy_collection_provider = cr.Provider(
            self, "PolicyCollectionProvider",
            on_event_handler=create_policy_collection_lambda,
            vpc=lambda_vpc,
            security_groups=[lambda_sg]
        )

        # Custom resource for OpenSearch policy and collection creation
        policy_collection_resource = CustomResource(
            self, "PolicyCollectionResource",
            service_token=policy_collection_provider.service_token,
            properties={
                "timestamp": construct_id,
            }
        )
        policy_collection_resource.apply_removal_policy(RemovalPolicy.DESTROY)

        # Lambda for creating Bedrock knowledge bases
        create_kb_lambda = lambda_.Function(
            self, "CreateKnowledgeBasesLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset("employee_assistant_cdk/lambda_functions"),
            handler="create_knowledge_bases.handler",
            timeout=Duration.minutes(15),
            layers=[requests_layer],
            environment={
                "S3_BUCKET_NAME": pdf_bucket.bucket_name,
                "UUID_SUFFIX": uuid_value,
                "BEDROCK_ROLE_ARN": bedrock_role.role_arn,
            },
            function_name=create_bedrock_kb_lambda_name,
            vpc=lambda_vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[lambda_sg],
            reserved_concurrent_executions=10 
        )
        create_kb_lambda.apply_removal_policy(RemovalPolicy.DESTROY)
        
        # Grant permissions to knowledge base Lambda
        pdf_bucket.grant_read(create_kb_lambda)
        create_kb_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:GetFoundationModel",
                    "bedrock:InvokeModel",
                    "bedrock:CreateKnowledgeBase",
                    "bedrock:GetKnowledgeBase",
                    "bedrock:CreateDataSource",
                    "bedrock:GetDataSource", 
                    "bedrock:StartIngestionJob",
                    "bedrock:GetIngestionJob",
                    "bedrock:TagResource",
                    "aoss:CreateCollection",
                    "aoss:ListCollections", 
                    "aoss:BatchGetCollection",
                    "aoss:GetAccessPolicy", 
                    "aoss:GetSecurityPolicy",
                    "aoss:APIAccessAll",
                    "iam:GetRole",
                    "iam:UpdateAssumeRolePolicy",
                    "iam:PutRolePolicy",
                    "iam:GetRolePolicy",
                    "iam:CreateServiceLinkedRole"
                ],
                resources=[
                    f"arn:aws:bedrock:{Aws.REGION}:{Aws.ACCOUNT_ID}:foundation-model/*",
                    f"arn:aws:bedrock:{Aws.REGION}:{Aws.ACCOUNT_ID}:knowledge-base/*",
                    f"arn:aws:bedrock:{Aws.REGION}:{Aws.ACCOUNT_ID}:data-source/*",
                    f"arn:aws:bedrock:{Aws.REGION}:{Aws.ACCOUNT_ID}:ingestion-job/*",
                    f"arn:aws:bedrock:{Aws.REGION}:{Aws.ACCOUNT_ID}:agent/*",
                    f"arn:aws:aoss:{Aws.REGION}:{Aws.ACCOUNT_ID}:collection/*",
                    f"arn:aws:aoss:{Aws.REGION}:{Aws.ACCOUNT_ID}:accesspolicy/*",
                    f"arn:aws:aoss:{Aws.REGION}:{Aws.ACCOUNT_ID}:securitypolicy/*",
                    f"arn:aws:iam::{Aws.ACCOUNT_ID}:role/*"
                ]
            )
        )
        create_kb_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[bedrock_role.role_arn]
            )
        )
        # Grant logging permissions to Lambda
        create_kb_lambda.add_to_role_policy(
            self.create_restricted_logs_policy(create_bedrock_kb_lambda_name)
        )

        # Custom resource provider for knowledge base creation
        create_kb_provider = cr.Provider(
            self, "CreateKBProvider",
            on_event_handler=create_kb_lambda,
            vpc=lambda_vpc,
            security_groups=[lambda_sg]
        )

        # Custom resource for knowledge base creation
        create_kb_resource = CustomResource(
            self, "CreateKBResource",
            service_token=create_kb_provider.service_token,
            properties={
                "timestamp": construct_id,
                "collection_arn": policy_collection_resource.get_att("collection_arn"),
                "collection_host": policy_collection_resource.get_att("collection_host"),
                "role_arn": policy_collection_resource.get_att("role_arn"),
                "knowledge_bases": policy_collection_resource.get_att("knowledge_bases")
            }
        )
        create_kb_resource.apply_removal_policy(RemovalPolicy.DESTROY)
        create_kb_resource.node.add_dependency(policy_collection_resource)

        # Lambda for creating Bedrock agents
        create_agents_lambda = lambda_.Function(
            self, "CreateAgentsLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset("employee_assistant_cdk/lambda_functions"),
            handler="create_agents.handler",
            timeout=Duration.minutes(15),
            environment={
                "BEDROCK_ROLE_ARN": bedrock_role.role_arn,
                "UUID_SUFFIX": uuid_value,
                "KNOWLEDGE_BASES": create_kb_resource.get_att_string("KNOWLEDGE_BASES_JSON"),
                "TAVILY_LAMBDA_NAME": tavily_lambda.function_name
            },
            function_name=create_bedrock_agent_lambda_name,
            vpc=lambda_vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[lambda_sg],
            reserved_concurrent_executions=10 
        )
        create_agents_lambda.apply_removal_policy(RemovalPolicy.DESTROY)
        create_agents_lambda.node.add_dependency(create_kb_resource)
        
        # Grant permissions to agent creation Lambda
        create_agents_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:CreateAgent",
                    "bedrock:GetAgent",
                    "bedrock:ListAgents", 
                    "bedrock:CreateAgentActionGroup",
                    "bedrock:DeleteAgent",
                    "bedrock:PrepareAgent",
                    "bedrock:CreateAgentAlias",
                    "bedrock:AssociateAgentKnowledgeBase",
                    "bedrock:AssociateAgentCollaborator",
                    "bedrock:TagResource",
                    "bedrock:ListAgentAliases",
                    "bedrock:GetAgentAlias",
                    "iam:GetRole",
                    "iam:UpdateAssumeRolePolicy",
                    "iam:PutRolePolicy",
                    "iam:GetRolePolicy"
                ],
                resources=[
                    f"arn:aws:bedrock:{Aws.REGION}:{Aws.ACCOUNT_ID}:model/*",
                    f"arn:aws:bedrock:{Aws.REGION}:{Aws.ACCOUNT_ID}:agent/*",
                    f"arn:aws:bedrock:{Aws.REGION}:{Aws.ACCOUNT_ID}:agent-alias/*",
                    f"arn:aws:bedrock:{Aws.REGION}:{Aws.ACCOUNT_ID}:knowledge-base/*"
                ],
            )
        )
        create_agents_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[bedrock_role.role_arn]
            )
        )
        # Grant logging permissions to Lambda
        create_agents_lambda.add_to_role_policy(
            self.create_restricted_logs_policy(create_bedrock_agent_lambda_name)
        )
        
        # Custom resource provider for agent creation
        create_agents_provider = cr.Provider(
            self, "CreateAgentsProvider",
            on_event_handler=create_agents_lambda
        )

        # Custom resource for agent creation
        create_agents_resource = CustomResource(
            self, "CreateAgentsResource",
            service_token=create_agents_provider.service_token,
            properties={
                "timestamp": construct_id,
                "knowledgeBaseIds": create_kb_resource.get_att_string("knowledgeBaseIds"),
            }
        )
        create_agents_resource.apply_removal_policy(RemovalPolicy.DESTROY)

        # Lambda for agent invocation
        invoke_agent_lambda = lambda_.Function(
            self, "InvokeAgentLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset("employee_assistant_cdk/lambda_functions"),
            handler="invoke_agent.handler",
            timeout=Duration.minutes(15),
            function_name=invoke_bedrock_agent_lambda_name,
            vpc=lambda_vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[lambda_sg],
            reserved_concurrent_executions=10 
        )
        invoke_agent_lambda.apply_removal_policy(RemovalPolicy.DESTROY) 
        
        # Grant permissions to invoke Lambda
        invoke_agent_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:GetAgent",
                    "bedrock:ListAgents",
                    "bedrock:InvokeAgent",
                    "iam:GetRole",
                    "iam:UpdateAssumeRolePolicy",
                    "iam:PutRolePolicy",
                    "iam:GetRolePolicy"
                ],
                resources=[
                    f"arn:aws:iam::{self.account}:role/*",
                    f"arn:aws:bedrock:{Aws.REGION}:{Aws.ACCOUNT_ID}:agent/*",
                    f"arn:aws:bedrock:{Aws.REGION}:{Aws.ACCOUNT_ID}:agent-action-group/*",
                    f"arn:aws:bedrock:{Aws.REGION}:{Aws.ACCOUNT_ID}:agent-alias/*",
                ]
            )
        )
        invoke_agent_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[bedrock_role.role_arn]
            )
        )
        # Grant logging permissions to Lambda
        invoke_agent_lambda.add_to_role_policy(
            self.create_restricted_logs_policy(invoke_bedrock_agent_lambda_name)
        )

        # Grant permissions to invoke_agent_lambda for DynamoDB
        conversation_table.grant_read_write_data(invoke_agent_lambda)
        invoke_agent_lambda.add_environment("CONVERSATION_TABLE", conversation_table.table_name)

        # Lambda for retrieving conversation history
        get_history_lambda = lambda_.Function(
            self, "GetHistoryLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset("employee_assistant_cdk/lambda_functions"),
            handler="get_conversation_history.handler",
            timeout=Duration.minutes(5),
            environment={
                "CONVERSATION_TABLE": conversation_table.table_name,
            },
            function_name=get_conversation_history_lambda_name,
            vpc=lambda_vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[lambda_sg],
            reserved_concurrent_executions=10 
        )
        get_history_lambda.add_to_role_policy(
            self.create_restricted_logs_policy(get_conversation_history_lambda_name)
        )

        # Lambda for retrieving conversation messages
        get_messages_lambda = lambda_.Function(
            self, "GetMessagesLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset("employee_assistant_cdk/lambda_functions"),
            handler="get_conversation_messages.handler", 
            timeout=Duration.minutes(5),
            environment={
                "CONVERSATION_TABLE": conversation_table.table_name,
            },
            function_name=get_conversation_message_lambda_name,
            vpc=lambda_vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[lambda_sg],
            reserved_concurrent_executions=10 
        )
        get_messages_lambda.add_to_role_policy(
            self.create_restricted_logs_policy(get_conversation_message_lambda_name)
        )

        # Grant DynamoDB read permissions to the Lambda functions
        conversation_table.grant_read_data(get_history_lambda)
        conversation_table.grant_read_data(get_messages_lambda)

        # Lambda for file uploads
        upload_files_lambda = lambda_.Function(
            self, "UploadFilesLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset("employee_assistant_cdk/lambda_functions"),
            handler="upload_files.handler",
            timeout=Duration.minutes(5),
            environment={
                "S3_BUCKET_NAME": pdf_bucket.bucket_name,
            },
            function_name=upload_files_lambda_name,
            vpc=lambda_vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[lambda_sg],
            reserved_concurrent_executions=10 
        )
        upload_files_lambda.add_to_role_policy(
            self.create_restricted_logs_policy(upload_files_lambda_name)
        )

        # Grant S3 permissions to the upload Lambda function
        pdf_bucket.grant_put(upload_files_lambda)
        pdf_bucket.grant_read(upload_files_lambda)

        # Lambda function to process uploads and trigger ingestion
        process_upload_lambda = lambda_.Function(
            self, "ProcessUploadLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset("employee_assistant_cdk/lambda_functions"),
            handler="process_upload.handler",
            timeout=Duration.minutes(5),
            environment={
                "KNOWLEDGE_BASES": create_kb_resource.get_att_string("KNOWLEDGE_BASES_JSON"),
            },
            function_name=process_upload_lambda_name,
            vpc=lambda_vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[lambda_sg],
            reserved_concurrent_executions=10 
        )
        process_upload_lambda.add_to_role_policy(
            self.create_restricted_logs_policy(process_upload_lambda_name)
        )

        # Grant permissions to the process upload Lambda function
        pdf_bucket.grant_read(process_upload_lambda)
        process_upload_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:GetKnowledgeBase",
                    "bedrock:ListKnowledgeBases", 
                    "bedrock:ListDataSources",
                    "bedrock:StartIngestionJob",
                    "bedrock:GetIngestionJob",
                    "bedrock:GetDataSource"
                ],
                resources=[
                    f"arn:aws:bedrock:{Aws.REGION}:{Aws.ACCOUNT_ID}:knowledge-base/*"
                ]
            )
        )

        # Add S3 event notification to trigger Lambda when files are uploaded
        pdf_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED, 
            s3n.LambdaDestination(process_upload_lambda)
        )

        #######################
        # API & AUTHENTICATION RESOURCES
        #######################
        
        # Create Cognito User Pool for authentication
        user_pool = cognito.UserPool(
            self, "EmployeeAssistantUserPool",
            user_pool_name=cognito_user_pool_name,
            self_sign_up_enabled=True,
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            removal_policy=RemovalPolicy.DESTROY,
        )
        
        # Add auto verification for email using CfnUserPool
        cfn_user_pool = user_pool.node.default_child
        cfn_user_pool.auto_verify_attributes = ["email"]
        
        # Create User Pool Client
        user_pool_client = cognito.UserPoolClient(
            self, "EmployeeAssistantClient",
            user_pool_client_name=cognito_user_pool_client_name,
            user_pool=user_pool,
            generate_secret=False,
        )

        # Create log group for API access logs
        api_log_group = logs.LogGroup(
            self, "ApiGatewayLogs",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY
        )

        # API Gateway with access logging
        api = apigw.RestApi(
            self, "EmployeeAssistantAPI",
            rest_api_name=rest_api_name,
            description="API for the Employee Virtual Assistant",
            deploy_options=apigw.StageOptions(
                stage_name="prod",
                access_log_destination=apigw.LogGroupLogDestination(api_log_group),
                access_log_format=apigw.AccessLogFormat.custom(
                    '\\$context.identity.sourceIp - \\$context.identity.caller [\\$context.requestTime] "\\$context.httpMethod \\$context.resourcePath \\$context.protocol" ' +
                    '\\$context.status \\$context.responseLength \\$context.requestId \\$context.apiId'
                ),
                logging_level=apigw.MethodLoggingLevel.INFO
            ),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=["POST", "OPTIONS", "GET"],
                allow_headers=["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key", "X-Amz-Security-Token"],
            )
        )

        # Create usage plan for API rate limiting
        usage_plan = apigw.UsagePlan(
            self, "EmployeeAssistantUsagePlan",
            name=f"employee-assistant-usage-plan-{uuid_suffix}",
            description="Usage plan for the Employee Assistant API",
            throttle=apigw.ThrottleSettings(
                rate_limit=20,  # requests per second
                burst_limit=50  # maximum concurrent requests
            ),
            quota=apigw.QuotaSettings(
                limit=10000,  # maximum requests
                period=apigw.Period.MONTH
            )
        )

        # Associate the stage with the usage plan
        usage_plan.add_api_stage(
            api=api,
            stage=api.deployment_stage
        )

        # Create a Cognito authorizer for API Gateway
        authorizer = apigw.CognitoUserPoolsAuthorizer(
            self, "EmployeeAssistantAuthorizer",
            cognito_user_pools=[user_pool],
            identity_source="method.request.header.Authorization"
        )

        # API Gateway resources and Lambda integrations
        invoke_integration = apigw.LambdaIntegration(invoke_agent_lambda)
        invoke_resource = api.root.add_resource("invoke")

        upload_integration = apigw.LambdaIntegration(upload_files_lambda)
        upload_resource = api.root.add_resource("upload")

        history_integration = apigw.LambdaIntegration(get_history_lambda)
        history_resource = api.root.add_resource("history")

        messages_integration = apigw.LambdaIntegration(get_messages_lambda)
        messages_resource = api.root.add_resource("messages")
        messages_param_resource = messages_resource.add_resource("{sessionId}")

        # Add methods to resources with Cognito authorization
        invoke_resource.add_method(
            "POST", 
            invoke_integration,
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO
        )

        upload_resource.add_method(
            "POST", 
            upload_integration,
            authorizer=authorizer, 
            authorization_type=apigw.AuthorizationType.COGNITO
        )

        history_resource.add_method(
            "GET", 
            history_integration,
            authorizer=authorizer, 
            authorization_type=apigw.AuthorizationType.COGNITO
        )

        messages_param_resource.add_method(
            "GET", 
            messages_integration,
            authorizer=authorizer, 
            authorization_type=apigw.AuthorizationType.COGNITO
        )

        #######################
        # WEBSITE AND CONTENT DELIVERY
        #######################
        
        # Create CloudFront Origin Access Identity for S3 access
        origin_access_identity = cloudfront.OriginAccessIdentity(
            self, "OriginAccessIdentity",
            comment="Allow CloudFront to access S3 website content"
        )

        # Grant read permissions to CloudFront
        website_bucket.grant_read(origin_access_identity)

        # Create CloudFront distribution for website hosting
        distribution = cloudfront.Distribution(
            self, cloud_front_distribution_name,
            enable_logging=True,
            log_bucket=cloudfront_logs_bucket,
            log_file_prefix="cloudfront-logs/",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(
                    website_bucket,
                    origin_access_identity=origin_access_identity
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
            ),
            default_root_object="index.html",
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                ),
            ],
        )

        #######################
        # FINAL CONFIGURATION
        #######################
        
        # Extract supervisor agent details
        supervisor_agent_id = create_agents_resource.get_att_string("supervisorAgentId")
        supervisor_agent_alias_id = create_agents_resource.get_att_string("supervisorAgentAliasId")
        
        # Update agent invocation Lambda environment variables
        invoke_agent_lambda.add_environment("AGENT_ID", supervisor_agent_id)
        invoke_agent_lambda.add_environment("AGENT_ALIAS_ID", supervisor_agent_alias_id)
        
        # Output values for use in the frontend and deployment scripts
        CfnOutput(self, f"CognitoRegion-{uuid_suffix}", value=self.region, export_name=f"CognitoRegion-{uuid_suffix}")
        CfnOutput(self, f"CognitoUserPoolId-{uuid_suffix}", value=user_pool.user_pool_id, export_name=f"CognitoUserPoolId-{uuid_suffix}")
        CfnOutput(self, f"CognitoClientId-{uuid_suffix}", value=user_pool_client.user_pool_client_id, export_name=f"CognitoClientId-{uuid_suffix}")
        CfnOutput(self, f"ApiGatewayEndpoint-{uuid_suffix}", value=f"{api.url}invoke", export_name=f"ApiGatewayEndpoint-{uuid_suffix}")
        CfnOutput(self, f"FileUploadEndpoint-{uuid_suffix}", value=f"{api.url}upload", export_name=f"FileUploadEndpoint-{uuid_suffix}")
        CfnOutput(self, f"SupervisorAgentId-{uuid_suffix}", value=supervisor_agent_id, export_name=f"SupervisorAgentId-{uuid_suffix}")
        CfnOutput(self, f"SupervisorAgentAliasId-{uuid_suffix}", value=supervisor_agent_alias_id, export_name=f"SupervisorAgentAliasId-{uuid_suffix}")
        CfnOutput(self, f"WebsiteBucketName-{uuid_suffix}", value=website_bucket.bucket_name, export_name=f"WebsiteBucketName-{uuid_suffix}")
        CfnOutput(self, f"DataBucketName-{uuid_suffix}", value=pdf_bucket.bucket_name, export_name=f"DataBucketName-{uuid_suffix}")
        CfnOutput(self, f"CloudFrontDistributionId-{uuid_suffix}", value=distribution.distribution_id, export_name=f"CloudFrontDistributionId-{uuid_suffix}")
        CfnOutput(self, f"CloudFrontURL-{uuid_suffix}", value=f"https://{distribution.distribution_domain_name}", export_name=f"CloudFrontURL-{uuid_suffix}")
        CfnOutput(self, "UUID", value=uuid_value, export_name="UUID")
        CfnOutput(self, f"HistoryEndpoint-{uuid_suffix}", value=f"{api.url}history", export_name=f"HistoryEndpoint-{uuid_suffix}")
        CfnOutput(self, f"MessagesEndpoint-{uuid_suffix}", value=f"{api.url}messages", export_name=f"MessagesEndpoint-{uuid_suffix}")

    def create_restricted_logs_policy(self, function_name):
        """Create CloudWatch Logs policy with restricted resources"""
        return iam.PolicyStatement(
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            resources=[
                f"arn:aws:logs:{Aws.REGION}:{Aws.ACCOUNT_ID}:log-group:/aws/lambda/{function_name}",
                f"arn:aws:logs:{Aws.REGION}:{Aws.ACCOUNT_ID}:log-group:/aws/lambda/{function_name}:*"
            ]
        )