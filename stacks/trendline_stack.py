from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_lambda as _lambda,
    aws_s3 as s3,
    aws_events as events,
    aws_events_targets as targets,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
    aws_bedrock as bedrock,
    CfnParameter,
)
from constructs import Construct


class TrendlineStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ----- Parameters -----
        secret_name = CfnParameter(
            self, "SecretName",
            type="String",
            default="trendline/x-api-keys",
            description="Name of the Secrets Manager secret containing X API keys",
        )

        notification_email = CfnParameter(
            self, "NotificationEmail",
            type="String",
            description="Email address to receive summary notifications",
        )

        # ----- S3 Bucket (JSON storage) -----
        bucket = s3.Bucket(
            self, "TrendlineBucket",
            event_bridge_enabled=True,
            removal_policy=RemovalPolicy.RETAIN,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        # ----- SNS Topic (email notification) -----
        topic = sns.Topic(
            self, "TrendlineTopic",
            display_name="Trendline X Summary Notification",
        )
        topic.add_subscription(
            subscriptions.EmailSubscription(notification_email.value_as_string)
        )

        # ----- Secrets Manager reference (created via console) -----
        secret = secretsmanager.Secret.from_secret_name_v2(
            self, "XApiSecret",
            secret_name=secret_name.value_as_string,
        )

        # ----- Lambda Layer (X SDK) -----
        x_sdk_layer = _lambda.LayerVersion(
            self, "XSdkLayer",
            code=_lambda.Code.from_asset(
                "lambda/layers/x_sdk",
                bundling={
                    "image": _lambda.Runtime.PYTHON_3_13.bundling_image,
                    "command": [
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output/python",
                    ],
                },
            ),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_13],
            description="X (Twitter) official Python SDK (xdk)",
        )

        # ----- Lambda Function (fetch X API → store JSON to S3) -----
        fetch_function = _lambda.Function(
            self, "FetchXFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=_lambda.Code.from_asset("lambda/fetch_x"),
            timeout=Duration.seconds(60),
            memory_size=256,
            layers=[x_sdk_layer],
            environment={
                "BUCKET_NAME": bucket.bucket_name,
                "SECRET_NAME": secret_name.value_as_string,
            },
        )

        # Grant Lambda permissions
        bucket.grant_write(fetch_function)
        secret.grant_read(fetch_function)

        # ----- EventBridge Rule: Cron 6:00 JST (= 21:00 UTC previous day) -----
        cron_rule = events.Rule(
            self, "DailyFetchRule",
            schedule=events.Schedule.cron(minute="0", hour="21"),
            description="Trigger Lambda at 6:00 JST daily (21:00 UTC)",
        )
        cron_rule.add_target(targets.LambdaFunction(fetch_function))

        # ----- Bedrock Agent -----
        agent_role = iam.Role(
            self, "BedrockAgentRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="Role for Bedrock Agent to read S3 and publish to SNS",
        )
        bucket.grant_read(agent_role)
        topic.grant_publish(agent_role)

        agent = bedrock.CfnAgent(
            self, "SummaryAgent",
            agent_name="trendline-summary-agent",
            agent_resource_role_arn=agent_role.role_arn,
            foundation_model="anthropic.claude-3-haiku-20240307-v1:0",
            instruction=(
                "You are a summarization assistant. "
                "Read the JSON file from the S3 bucket and create a concise Japanese summary "
                "of the X (Twitter) posts. Focus on key trends and notable topics. "
                "After summarizing, publish the result to the SNS topic."
            ),
            idle_session_ttl_in_seconds=600,
        )

        # ----- Lambda Function (invoke Bedrock Agent and publish to SNS) -----
        summarize_function = _lambda.Function(
            self, "SummarizeFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=_lambda.Code.from_asset("lambda/summarize"),
            timeout=Duration.seconds(120),
            memory_size=256,
            environment={
                "BUCKET_NAME": bucket.bucket_name,
                "SNS_TOPIC_ARN": topic.topic_arn,
                "BEDROCK_AGENT_ID": agent.attr_agent_id,
                "BEDROCK_AGENT_ALIAS_ID": "TSTALIASID",
            },
        )

        # Grant permissions to summarize function
        bucket.grant_read(summarize_function)
        topic.grant_publish(summarize_function)
        summarize_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeAgent",
                    "bedrock:InvokeModel",
                ],
                resources=["*"],
            )
        )

        # ----- EventBridge Rule: S3 PutObject → Summarize -----
        s3_put_rule = events.Rule(
            self, "S3PutObjectRule",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created"],
                detail={
                    "bucket": {"name": [bucket.bucket_name]},
                },
            ),
            description="Trigger summarization when a new JSON is uploaded to S3",
        )
        s3_put_rule.add_target(targets.LambdaFunction(summarize_function))
