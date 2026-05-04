"""
Lambda: Fetch posts from X (Twitter) API and store JSON in S3.
"""
import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

import boto3


def get_secret() -> dict:
    """Retrieve X API credentials from Secrets Manager."""
    client = boto3.client("secretsmanager")
    secret_name = os.environ["SECRET_NAME"]
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])


def fetch_posts(bearer_token: str) -> dict:
    """Call X API v2 to search recent posts."""
    url = "https://api.x.com/2/tweets/search/recent"
    params = "?query=lang:ja&max_results=100&tweet.fields=created_at,public_metrics,author_id"
    req = urllib.request.Request(
        url + params,
        headers={
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def handler(event, context):
    """Lambda entry point."""
    secrets = get_secret()
    bearer_token = secrets["bearer_token"]

    # Fetch posts from X API
    data = fetch_posts(bearer_token)

    # Upload JSON to S3
    s3 = boto3.client("s3")
    bucket_name = os.environ["BUCKET_NAME"]
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    key = f"raw/{now.strftime('%Y/%m/%d/%H%M%S')}.json"

    s3.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=json.dumps(data, ensure_ascii=False),
        ContentType="application/json",
    )

    return {"statusCode": 200, "key": key, "count": len(data.get("data", []))}
