"""
Lambda: Fetch timeline posts from X (Twitter) API using the official XDK
with OAuth 1.0a authentication, and store JSON in S3.
"""
import json
import os
from datetime import datetime, timezone, timedelta

import boto3
from xdk import Client
from xdk.oauth1_auth import OAuth1


def get_secret() -> dict:
    """Retrieve X API credentials from Secrets Manager."""
    client = boto3.client("secretsmanager")
    secret_name = os.environ["SECRET_NAME"]
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])


def build_client(secrets: dict) -> Client:
    """Build an XDK Client with OAuth 1.0a authentication."""
    oauth1 = OAuth1(
        api_key=secrets["x_api_key"],
        api_secret=secrets["x_api_secret"],
        callback="http://localhost:8080/callback",
        access_token=secrets["x_access_token"],
        access_token_secret=secrets["x_access_token_secret"],
    )
    return Client(auth=oauth1)


def fetch_timeline(client: Client) -> list[dict]:
    """Fetch the authenticated user's reverse-chronological timeline for the previous day (JST)."""
    # Calculate previous day (JST) time range
    jst = timezone(timedelta(hours=9))
    now_jst = datetime.now(jst)
    yesterday_jst = now_jst - timedelta(days=1)
    start_of_day = yesterday_jst.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = yesterday_jst.replace(hour=23, minute=59, second=59, microsecond=0)

    # Convert to UTC ISO 8601 format for the API
    start_time = start_of_day.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_time = end_of_day.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Get the authenticated user's ID
    me = client.users.get_me()
    user_id = me.data["id"]

    posts = []
    for page in client.users.get_timeline(
        id=user_id,
        max_results=100,
        tweet_fields=["created_at", "public_metrics", "author_id", "lang"],
        start_time=start_time,
        end_time=end_time,
    ):
        if page.data:
            for post in page.data:
                metrics = post.get("public_metrics", {})
                posts.append({
                    "id": post.get("id", None),
                    "text": post.get("text", None),
                    "created_at": str(post.get("created_at", None)),
                    "author_id": post.get("author_id", None),
                    "lang": post.get("lang", None),
                    "like_count": metrics.get("like_count", 0),
                    "retweet_count": metrics.get("retweet_count", 0),
                    "reply_count": metrics.get("reply_count", 0),
                    "impression_count": metrics.get("impression_count", 0),
                })
        # Stop after collecting 500 posts
        if len(posts) >= 500:
            break

    return posts[:500]


def handler(event, context):
    """Lambda entry point."""
    secrets = get_secret()
    client = build_client(secrets)

    # Fetch timeline posts
    posts = fetch_timeline(client)

    # Upload JSON to S3
    s3 = boto3.client("s3")
    bucket_name = os.environ["BUCKET_NAME"]
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    key = f"raw/{now.strftime('%Y/%m/%d/%H%M%S')}.json"

    data = {"data": posts}
    s3.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=json.dumps(data, ensure_ascii=False),
        ContentType="application/json",
    )

    return {"statusCode": 200, "key": key, "count": len(posts)}
