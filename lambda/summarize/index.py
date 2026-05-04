"""
Lambda: Read JSON from S3, summarize with Bedrock, publish to SNS.
"""
import json
import os

import boto3


def handler(event, context):
    """Lambda entry point triggered by EventBridge S3 PutObject event."""
    s3 = boto3.client("s3")
    bedrock_runtime = boto3.client("bedrock-runtime")
    sns = boto3.client("sns")

    bucket_name = os.environ["BUCKET_NAME"]
    topic_arn = os.environ["SNS_TOPIC_ARN"]

    # Extract S3 key from EventBridge event
    detail = event.get("detail", {})
    object_key = detail.get("object", {}).get("key", "")

    if not object_key:
        return {"statusCode": 400, "error": "No object key in event"}

    # Read JSON from S3
    response = s3.get_object(Bucket=bucket_name, Key=object_key)
    raw_data = json.loads(response["Body"].read().decode("utf-8"))

    # Build prompt for summarization
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

    # Invoke Bedrock model
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [
            {"role": "user", "content": prompt}
        ],
    })

    bedrock_response = bedrock_runtime.invoke_model(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        contentType="application/json",
        accept="application/json",
        body=body,
    )

    result = json.loads(bedrock_response["body"].read().decode("utf-8"))
    summary = result["content"][0]["text"]

    # Publish summary to SNS
    sns.publish(
        TopicArn=topic_arn,
        Subject="【Trendline】X投稿の要約レポート",
        Message=summary,
    )

    return {"statusCode": 200, "summary_length": len(summary)}
