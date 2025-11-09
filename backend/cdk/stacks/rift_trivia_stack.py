"""
Main CDK Stack for Rift Trivia Backend Infrastructure
"""
import os
from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    RemovalPolicy,
    aws_lambda as _lambda,
    aws_s3 as s3,
    aws_iam as iam,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_apigatewayv2 as apigwv2,
    aws_glue as glue,
    aws_ssm as ssm,
    aws_bedrock as bedrock,
    custom_resources as cr,
)
from constructs import Construct


class RiftTriviaStack(Stack):
    """Main infrastructure stack for Rift Trivia backend"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ========================================
        # Parameters (must be provided via context)
        # ========================================
        bucket_name = self.node.try_get_context("bucket_name")
        if not bucket_name:
            raise ValueError("bucket_name must be provided in cdk.context.json or via -c bucket_name=...")
        
        riot_api_key_param_name = self.node.try_get_context("riot_api_key_param")
        if not riot_api_key_param_name:
            raise ValueError("riot_api_key_param must be provided in cdk.context.json or via -c riot_api_key_param=...")
        
        # Bedrock model ID with sensible default
        bedrock_model_id = self.node.try_get_context("bedrock_model_id") or "anthropic.claude-3-5-sonnet-20241022-v2:0"

        # ========================================
        # S3 Bucket for Match Data
        # ========================================
        self.data_bucket = s3.Bucket(
            self,
            "DataBucket",
            bucket_name=bucket_name,
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,  # Protect data on stack deletion
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="ArchiveOldMatches",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INTELLIGENT_TIERING,
                            transition_after=Duration.days(90),
                        )
                    ],
                )
            ],
        )

        # ========================================
        # Bedrock Knowledge Base using S3 Vectors
        # ========================================

        # IAM role for Bedrock Knowledge Base
        bedrock_kb_role = iam.Role(
            self,
            "BedrockKBRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="Role for Bedrock Knowledge Base to access S3 for data and vector storage",
        )

        # Grant S3 read to data source and read/write to vectors prefix
        self.data_bucket.grant_read(bedrock_kb_role, "summary/*")
        self.data_bucket.grant_read_write(bedrock_kb_role, "kb-vectors/*")

        # Grant Bedrock model access
        bedrock_kb_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                ],
                resources=[f"arn:aws:bedrock:{self.region}::foundation-model/*"],
            )
        )

        # Create Knowledge Base via Custom Resource to target S3 Vectors (CloudFormation/CDK may not yet expose this)
        kb_create = cr.AwsCustomResource(
            self,
            "CreateS3VectorsKnowledgeBase",
            on_create=cr.AwsSdkCall(
                service="Bedrock",
                action="CreateKnowledgeBase",
                parameters={
                    "Name": "rift-trivia-kb",
                    "Description": "Knowledge base for Rift Trivia quiz generation from player summaries",
                    "RoleArn": bedrock_kb_role.role_arn,
                    "KnowledgeBaseConfiguration": {
                        "Type": "VECTOR",
                        "VectorKnowledgeBaseConfiguration": {
                            "EmbeddingModelArn": f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-text-v2:0",
                        },
                    },
                    "StorageConfiguration": {
                        "Type": "S3",
                        "S3Configuration": {
                            "BucketArn": self.data_bucket.bucket_arn,
                            # Optionally specify a prefix for vector files written by Bedrock
                            # "ObjectKeyPrefix": "kb-vectors/",
                        },
                    },
                },
                physical_resource_id=cr.PhysicalResourceId.from_response("knowledgeBase.KnowledgeBaseId"),
            ),
            on_delete=cr.AwsSdkCall(
                service="Bedrock",
                action="DeleteKnowledgeBase",
                parameters={
                    "KnowledgeBaseId": cr.PhysicalResourceIdReference(),
                },
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=[
                        "bedrock:CreateKnowledgeBase",
                        "bedrock:DeleteKnowledgeBase",
                        "bedrock:TagResource",
                        "bedrock:UntagResource",
                        "bedrock:UpdateKnowledgeBase",
                    ],
                    resources=["*"],
                )
            ]),
        )

        kb_id = kb_create.get_response_field("knowledgeBase.KnowledgeBaseId")

        # Create Data Source via Custom Resource as well
        ds_create = cr.AwsCustomResource(
            self,
            "CreateKnowledgeBaseDataSource",
            on_create=cr.AwsSdkCall(
                service="Bedrock",
                action="CreateDataSource",
                parameters={
                    "KnowledgeBaseId": kb_id,
                    "Name": "rift-trivia-s3-summaries",
                    "Description": "S3 data source for player summaries",
                    "DataSourceConfiguration": {
                        "Type": "S3",
                        "S3Configuration": {
                            "BucketArn": self.data_bucket.bucket_arn,
                            "InclusionPrefixes": ["summary/"],
                        },
                    },
                    "VectorIngestionConfiguration": {
                        "ChunkingConfiguration": {
                            "ChunkingStrategy": "FIXED_SIZE",
                            "FixedSizeChunkingConfiguration": {
                                "MaxTokens": 300,
                                "OverlapPercentage": 20,
                            },
                        }
                    },
                },
                physical_resource_id=cr.PhysicalResourceId.from_response("dataSource.DataSourceId"),
            ),
            on_delete=cr.AwsSdkCall(
                service="Bedrock",
                action="DeleteDataSource",
                parameters={
                    "KnowledgeBaseId": kb_id,
                    "DataSourceId": cr.PhysicalResourceIdReference(),
                },
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=[
                        "bedrock:CreateDataSource",
                        "bedrock:DeleteDataSource",
                        "bedrock:UpdateDataSource",
                        "bedrock:TagResource",
                        "bedrock:UntagResource",
                    ],
                    resources=["*"],
                )
            ]),
        )

        ds_id = ds_create.get_response_field("dataSource.DataSourceId")

        # ========================================
        # WebSocket API Gateway
        # ========================================
        self.websocket_api = apigwv2.CfnApi(
            self,
            "WebSocketApi",
            name="RiftTriviaWebSocket",
            protocol_type="WEBSOCKET",
            route_selection_expression="$request.body.action",
        )

        self.websocket_stage = apigwv2.CfnStage(
            self,
            "WebSocketStage",
            api_id=self.websocket_api.ref,
            stage_name="production",
            auto_deploy=True,
        )

        websocket_endpoint = f"https://{self.websocket_api.ref}.execute-api.{self.region}.amazonaws.com/production"

        # ========================================
        # IAM Roles
        # ========================================
        
        # Lambda execution role with broad permissions
        lambda_role = iam.Role(
            self,
            "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
            ],
        )

        # Grant S3 access
        self.data_bucket.grant_read_write(lambda_role)

        # Grant SSM parameter access
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[f"arn:aws:ssm:{self.region}:{self.account}:parameter{riot_api_key_param_name}"],
            )
        )

        # Grant WebSocket API access
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["execute-api:ManageConnections"],
                resources=[f"arn:aws:execute-api:{self.region}:{self.account}:{self.websocket_api.ref}/*"],
            )
        )

        # Grant Bedrock access
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel", "bedrock:Retrieve", "bedrock:RetrieveAndGenerate"],
                resources=["*"],  # Bedrock doesn't support resource-level permissions yet
            )
        )

        # ========================================
        # Lambda Functions
        # ========================================

        # Common environment variables
        common_env = {
            "S3_BUCKET": self.data_bucket.bucket_name,
            "RIOT_API_KEY_SSM_PARAM": riot_api_key_param_name,
            "API_GATEWAY_ENDPOINT": websocket_endpoint,
            "AWS_REGION": self.region,
        }

        # 1. Riot API Function
        self.call_riot_api = _lambda.Function(
            self,
            "CallRiotApi",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="call_riot_api.lambda_handler",
            code=_lambda.Code.from_asset("../lambda"),
            role=lambda_role,
            timeout=Duration.seconds(60),
            memory_size=256,
            environment=common_env,
            description="Fetches summoner data from Riot API and checks S3 for existing data",
        )

        # Public Lambda Function URL (used by frontend as VITE_API_BASE)
        self.riot_api_function_url = self.call_riot_api.add_function_url(
            auth_type=_lambda.FunctionUrlAuthType.NONE,
            cors=_lambda.FunctionUrlCorsOptions(
                allowed_origins=["*"],
                allowed_methods=[_lambda.HttpMethod.POST, _lambda.HttpMethod.OPTIONS],
                allowed_headers=["content-type"],
            ),
        )

        # 2. Retrieve Match Data Function
        self.retrieve_match = _lambda.Function(
            self,
            "RetrieveMatchDataFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="retrieve_match_data.lambda_handler",
            code=_lambda.Code.from_asset("../lambda"),
            role=lambda_role,
            timeout=Duration.seconds(300),  # 5 minutes for API-heavy operations
            memory_size=512,
            environment=common_env,
            description="Retrieves match history from Riot API and stores in S3",
        )

        # 3. Generate Facts Function
        self.generate_facts = _lambda.Function(
            self,
            "GenerateFactsFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="generate_facts.lambda_handler",
            code=_lambda.Code.from_asset("../lambda"),
            role=lambda_role,
            timeout=Duration.seconds(300),
            memory_size=1024,  # More memory for Bedrock operations
            environment={
                **common_env,
                "BEDROCK_KB_ID": kb_id,
                "BEDROCK_MODEL_ID": bedrock_model_id,
            },
            description="Generates quiz facts using AWS Bedrock and RAG",
        )

        # 4. Send Fail Message Function
        self.send_fail_message = _lambda.Function(
            self,
            "SendFailMessageFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="send_fail_message.lambda_handler",
            code=_lambda.Code.from_asset("../lambda"),
            role=lambda_role,
            timeout=Duration.seconds(30),
            memory_size=128,
            environment={"API_GATEWAY_ENDPOINT": websocket_endpoint},
            description="Sends failure notifications via WebSocket",
        )

        # ========================================
        # AWS Glue Job
        # ========================================

        # Glue execution role
        glue_role = iam.Role(
            self,
            "GlueExecutionRole",
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSGlueServiceRole"),
            ],
        )

        self.data_bucket.grant_read_write(glue_role)

        # Upload Glue script to S3
        from aws_cdk import aws_s3_deployment as s3deploy

        glue_scripts_deployment = s3deploy.BucketDeployment(
            self,
            "GlueScriptsDeployment",
            sources=[s3deploy.Source.asset("../glue")],
            destination_bucket=self.data_bucket,
            destination_key_prefix="glue-scripts",
        )

        # Create Glue job
        self.glue_job = glue.CfnJob(
            self,
            "MatchSummaryJob",
            name="match-summary",
            role=glue_role.role_arn,
            command=glue.CfnJob.JobCommandProperty(
                name="glueetl",
                python_version="3",
                script_location=f"s3://{self.data_bucket.bucket_name}/glue-scripts/match-summary.py",
            ),
            default_arguments={
                "--job-language": "python",
                "--S3_BUCKET": self.data_bucket.bucket_name,
                "--enable-metrics": "true",
                "--enable-continuous-cloudwatch-log": "true",
                "--enable-spark-ui": "true",
                "--spark-event-logs-path": f"s3://{self.data_bucket.bucket_name}/spark-logs/",
            },
            glue_version="4.0",
            max_capacity=2.0,
            timeout=60,  # 60 minutes
            description="PySpark ETL job to aggregate match data into summaries",
        )

        # ========================================
        # Step Functions State Machine
        # ========================================

        # Trigger Step Function (needs state machine ARN, will be set after creation)
        self.trigger_step = _lambda.Function(
            self,
            "TriggerStepFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="trigger_step.lambda_handler",
            code=_lambda.Code.from_asset("../lambda"),
            role=lambda_role,
            timeout=Duration.seconds(60),
            memory_size=256,
            environment={
                "API_GATEWAY_ENDPOINT": websocket_endpoint,
                "STATE_MACHINE_ARN": "PLACEHOLDER",  # Will be updated after state machine creation
            },
            description="Triggers Step Functions execution and checks for duplicates",
        )

        # State machine tasks
        assign_var_task = sfn.Pass(
            self,
            "AssignVar",
            parameters={
                "puuid": sfn.JsonPath.string_at("$.puuid"),
                "year": sfn.JsonPath.string_at("$.year"),
                "final_exists": sfn.JsonPath.string_at("$.final_exists"),
                "summary_exists": sfn.JsonPath.string_at("$.summary_exists"),
                "routing_value": sfn.JsonPath.string_at("$.routing_value"),
                "connection_id": sfn.JsonPath.string_at("$.connection_id"),
            },
            result_path="$.vars",
        )

        # Check if final exists
        final_exists_choice = sfn.Choice(self, "FinalExists?")

        # Check if summary exists
        summary_exists_choice = sfn.Choice(self, "SummaryExists?")

        # Retrieve match data task
        retrieve_match_task = tasks.LambdaInvoke(
            self,
            "RetrieveMatchData",
            lambda_function=self.retrieve_match,
            payload=sfn.TaskInput.from_object({
                "puuid": sfn.JsonPath.string_at("$.vars.puuid"),
                "year": sfn.JsonPath.string_at("$.vars.year"),
                "routing_value": sfn.JsonPath.string_at("$.vars.routing_value"),
                "connection_id": sfn.JsonPath.string_at("$.vars.connection_id"),
            }),
            result_path="$.retrieve_result",
        )

        # Glue job task
        glue_job_task = tasks.GlueStartJobRun(
            self,
            "RunGlueETL",
            glue_job_name=self.glue_job.name,
            arguments=sfn.TaskInput.from_object({
                "--puuid": sfn.JsonPath.string_at("$.vars.puuid"),
                "--year": sfn.JsonPath.string_at("$.vars.year"),
            }),
            integration_pattern=sfn.IntegrationPattern.RUN_JOB,  # Wait for completion
            result_path="$.glue_result",
        )

        # Note: Bedrock ingestion would require custom Lambda or Step Functions integration
        # For simplicity, we'll handle this in the generate_facts Lambda
        bedrock_ingestion_note = sfn.Pass(
            self,
            "BedrockIngestionNote",
            comment="Bedrock ingestion is handled automatically by the Knowledge Base data source sync",
            result_path=sfn.JsonPath.DISCARD,
        )

        # Generate facts task
        generate_facts_task = tasks.LambdaInvoke(
            self,
            "GenerateFacts",
            lambda_function=self.generate_facts,
            payload=sfn.TaskInput.from_object({
                "puuid": sfn.JsonPath.string_at("$.vars.puuid"),
                "year": sfn.JsonPath.string_at("$.vars.year"),
                "connection_id": sfn.JsonPath.string_at("$.vars.connection_id"),
            }),
            result_path="$.generate_result",
        )

        # Success state
        success_state = sfn.Succeed(self, "Success")

        # Fail handler
        fail_handler = tasks.LambdaInvoke(
            self,
            "SendFailMessage",
            lambda_function=self.send_fail_message,
            payload=sfn.TaskInput.from_object({
                "connection_id": sfn.JsonPath.string_at("$.vars.connection_id"),
                "error": sfn.JsonPath.string_at("$.error"),
            }),
        )

        fail_state = sfn.Fail(self, "Failed", cause="Workflow failed", error="WorkflowError")

        # Build the workflow
        definition = (
            assign_var_task
            .next(final_exists_choice
                .when(sfn.Condition.boolean_equals("$.vars.final_exists", True), generate_facts_task)
                .otherwise(summary_exists_choice
                    .when(sfn.Condition.boolean_equals("$.vars.summary_exists", True), bedrock_ingestion_note)
                    .otherwise(retrieve_match_task.next(glue_job_task).next(bedrock_ingestion_note))
                )
            )
        )

        # Connect all paths to generate_facts -> success
        bedrock_ingestion_note.next(generate_facts_task)
        generate_facts_task.next(success_state)

        # Add error handling
        retrieve_match_task.add_catch(fail_handler, result_path="$.error")
        glue_job_task.add_catch(fail_handler, result_path="$.error")
        generate_facts_task.add_catch(fail_handler, result_path="$.error")
        fail_handler.next(fail_state)

        # Create state machine
        self.state_machine = sfn.StateMachine(
            self,
            "RiftTriviaStateMachine",
            state_machine_name="rift-rewind",
            definition=definition,
            timeout=Duration.minutes(30),
        )

        # Grant state machine permissions
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "states:StartExecution",
                    "states:ListExecutions",
                    "states:DescribeExecution",
                ],
                resources=[self.state_machine.state_machine_arn],
            )
        )

        # Update trigger function with actual state machine ARN
        self.trigger_step.add_environment("STATE_MACHINE_ARN", self.state_machine.state_machine_arn)

        # ========================================
        # WebSocket API Integrations
        # ========================================

        # Lambda permission for API Gateway
        self.trigger_step.grant_invoke(iam.ServicePrincipal("apigateway.amazonaws.com"))

        # Integration
        integration = apigwv2.CfnIntegration(
            self,
            "TriggerStepIntegration",
            api_id=self.websocket_api.ref,
            integration_type="AWS_PROXY",
            integration_uri=f"arn:aws:apigateway:{self.region}:lambda:path/2015-03-31/functions/{self.trigger_step.function_arn}/invocations",
        )

        # Default route
        default_route = apigwv2.CfnRoute(
            self,
            "DefaultRoute",
            api_id=self.websocket_api.ref,
            route_key="$default",
            target=f"integrations/{integration.ref}",
        )

        # Connect/Disconnect routes (no integration needed)
        connect_route = apigwv2.CfnRoute(
            self,
            "ConnectRoute",
            api_id=self.websocket_api.ref,
            route_key="$connect",
        )

        disconnect_route = apigwv2.CfnRoute(
            self,
            "DisconnectRoute",
            api_id=self.websocket_api.ref,
            route_key="$disconnect",
        )

        # ========================================
        # Outputs
        # ========================================
        CfnOutput(
            self,
            "S3BucketName",
            value=self.data_bucket.bucket_name,
            description="S3 bucket for match data storage",
            export_name="RiftTrivia-S3Bucket",
        )

        CfnOutput(
            self,
            "WebSocketURL",
            value=f"wss://{self.websocket_api.ref}.execute-api.{self.region}.amazonaws.com/production",
            description="WebSocket API endpoint",
            export_name="RiftTrivia-WebSocketURL",
        )
        CfnOutput(
            self,
            "RiotApiFunctionUrl",
            value=self.riot_api_function_url.url,
            description="Lambda Function URL for riot-api-function (use as VITE_API_BASE)",
            export_name="RiftTrivia-RiotApiFunctionUrl",
        )

        CfnOutput(
            self,
            "StateMachineArn",
            value=self.state_machine.state_machine_arn,
            description="Step Functions state machine ARN",
            export_name="RiftTrivia-StateMachineArn",
        )

        CfnOutput(
            self,
            "CallRiotApiArn",
            value=self.call_riot_api.function_arn,
            description="Call Riot API Lambda function ARN",
            export_name="RiftTrivia-CallRiotApi",
        )

        CfnOutput(
            self,
            "GlueJobName",
            value=self.glue_job.name,
            description="Glue ETL job name",
            export_name="RiftTrivia-GlueJob",
        )

        CfnOutput(
            self,
            "KnowledgeBaseId",
            value=kb_id,
            description="Bedrock Knowledge Base ID",
            export_name="RiftTrivia-KnowledgeBaseId",
        )

        CfnOutput(
            self,
            "DataSourceId",
            value=ds_id,
            description="Bedrock Knowledge Base Data Source ID",
            export_name="RiftTrivia-DataSourceId",
        )

        CfnOutput(
            self,
            "BedrockModelId",
            value=bedrock_model_id,
            description="Bedrock model ID used for generation",
            export_name="RiftTrivia-BedrockModelId",
        )
