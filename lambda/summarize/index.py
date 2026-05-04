"""
Lambda: Read JSON from S3, invoke Bedrock Agent for summarization, publish to SNS.
"""
import json
import os
import uuid

import boto3


def handler(event, context):
    """Lambda entry point triggered by EventBridge S3 PutObject event."""
    s3 = boto3.client("s3")
    bedrock_agent_runtime = boto3.client("bedrock-agent-runtime")
    sns = boto3.client("sns")

    bucket_name = os.environ["BUCKET_NAME"]
    topic_arn = os.environ["SNS_TOPIC_ARN"]
    agent_id = os.environ["BEDROCK_AGENT_ID"]
    agent_alias_id = os.environ["BEDROCK_AGENT_ALIAS_ID"]

    # Extract S3 key from EventBridge event
    detail = event.get("detail", {})
    object_key = detail.get("object", {}).get("key", "")

    if not object_key:
        return {"statusCode": 400, "error": "No object key in event"}

    # Read JSON from S3
    response = s3.get_object(Bucket=bucket_name, Key=object_key)
    raw_data = json.loads(response["Body"].read().decode("utf-8"))

    # Build prompt for the agent
    tweets = raw_data.get("data", [])
    if not tweets:
        return {"statusCode": 200, "message": "No tweets to summarize"}

    tweet_texts = "\n".join(
        [f"- {t.get('text', '')}" for t in tweets[:50]]
    )

    prompt = (
        "以下はX (Twitter) から取得した最新の投稿一覧です。\n"
        "主要なトレンドや注目すべきトピックを日本語で簡潔に要約してください。\n\n"
        f"{tweet_texts}"
    )

    # Invoke Bedrock Agent
    agent_response = bedrock_agent_runtime.invoke_agent(
        agentId=agent_id,
        agentAliasId=agent_alias_id,
        sessionId=str(uuid.uuid4()),
        inputText=prompt,
    )

    # Collect streamed response chunks
    summary_parts = []
    for event_chunk in agent_response["completion"]:
        if "chunk" in event_chunk:
            chunk_bytes = event_chunk["chunk"].get("bytes", b"")
            summary_parts.append(chunk_bytes.decode("utf-8"))

    summary = "".join(summary_parts)

    if not summary:
        return {"statusCode": 500, "error": "Agent returned empty response"}

    # Publish summary to SNS
    sns.publish(
        TopicArn=topic_arn,
        Subject="【Trendline】X投稿の要約レポート",
        Message=summary,
    )

    return {"statusCode": 200, "summary_length": len(summary)}
