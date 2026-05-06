"""
Lambda: Read JSON from S3, summarize with Bedrock Converse API, publish to SNS.
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
    model_id = os.environ.get("MODEL_ID", "us.amazon.nova-micro-v1:0")


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
        [
            f"- [♥{t.get('like_count', 0)} RT{t.get('retweet_count', 0)} "
            f"💬{t.get('reply_count', 0)} 👁{t.get('impression_count', 0)}] "
            f"{t.get('text', '')}"
            for t in tweets
        ]
    )

    prompt = (
        "以下はX (Twitter) から取得した最新の投稿一覧です。\n"
        "各投稿には [♥いいね数 RTリツイート数 💬リプライ数 👁インプレッション数] のエンゲージメント指標が付いています。\n\n"
        "以下のルールに従って日本語で要約してください:\n"
        "- エンゲージメント（いいね・RT・インプレッション）が高い投稿ほど重要度が高いと判断する\n"
        "- 主要なトレンドや注目すべきトピックを箇条書きで整理する\n"
        "- 重要度の高い話題から順に記載する\n"
        "- 各トピックにどの程度注目されているか（エンゲージメントの規模感）を簡潔に付記する\n\n"
        f"{tweet_texts}"
    )

    # Invoke Bedrock Converse API
    converse_response = bedrock_runtime.converse(
        modelId=model_id,
        messages=[
            {
                "role": "user",
                "content": [{"text": prompt}],
            }
        ],
        inferenceConfig={
            "maxTokens": 2048,
            "temperature": 0.3,
        },
    )

    # Extract response text
    output_message = converse_response["output"]["message"]
    summary = "".join(
        block["text"] for block in output_message["content"] if "text" in block
    )

    if not summary:
        return {"statusCode": 500, "error": "Model returned empty response"}

    # Publish summary to SNS
    sns.publish(
        TopicArn=topic_arn,
        Subject="【Trendline】X投稿の要約レポート",
        Message=summary,
    )

    return {"statusCode": 200, "summary_length": len(summary)}
