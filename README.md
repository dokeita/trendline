# Trendline

X (Twitter) のタイムライン投稿を毎朝自動で取得・要約し、メールで通知する AWS サーバーレスパイプラインです。

## アーキテクチャ

```
EventBridge (cron 6:00 JST)
  → Lambda (fetch_x) + Layer (X SDK)
      → X API (OAuth 1.0a) からタイムラインを取得 → S3 に JSON 保存
          → EventBridge (S3 PutObject)
              → Lambda (summarize) → Bedrock Converse API で要約 → SNS → メール通知
```

### 使用サービス

| サービス | 用途 |
|---|---|
| EventBridge Rule | 定時実行 (JST 6:00) / S3 イベント検知 |
| Lambda | X API 呼び出し / Bedrock 要約処理 |
| Lambda Layer | X 公式 Python SDK (xdk) |
| S3 | 取得した JSON の保存 |
| Bedrock (Converse API) | 投稿内容の要約 |
| SNS | メール通知 |
| Secrets Manager | X API の OAuth 1.0a クレデンシャル管理 |

## 前提条件

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- [AWS CDK CLI](https://docs.aws.amazon.com/cdk/v2/guide/cli.html)
- Docker (Lambda Layer のビルドに必要)
- AWS アカウントと認証情報の設定済み環境
- Bedrock でモデルアクセスを有効化済み (デフォルト: Claude Haiku 4.5)
- Secrets Manager に X API の OAuth 1.0a クレデンシャルを登録済み

### Secrets Manager の設定

マネジメントコンソールから以下の形式でシークレットを作成してください。

- シークレット名: `trendline/x-api-keys` (デフォルト、変更可)
- 値:

```json
{
  "x_api_key": "YOUR_API_KEY",
  "x_api_secret": "YOUR_API_SECRET",
  "x_access_token": "YOUR_ACCESS_TOKEN",
  "x_access_token_secret": "YOUR_ACCESS_TOKEN_SECRET"
}
```

X Developer Console でアプリを作成し、OAuth 1.0a の User Token を取得してください。

## セットアップ

```bash
# 依存パッケージのインストール
uv sync

# CDK Bootstrap (初回のみ)
uv run cdk bootstrap
```

## デプロイ

```bash
uv run cdk deploy \
  --parameters NotificationEmail=your-email@example.com
```

シークレット名やモデルを変更する場合:

```bash
uv run cdk deploy \
  --parameters NotificationEmail=your-email@example.com \
  --parameters SecretName=your/custom-secret-name \
  --parameters ModelId=us.anthropic.claude-sonnet-4-20250514-v1:0
```

### パラメータ一覧

| パラメータ | デフォルト値 | 説明 |
|---|---|---|
| `NotificationEmail` | (必須) | 要約レポートの送信先メールアドレス |
| `SecretName` | `trendline/x-api-keys` | Secrets Manager のシークレット名 |
| `ModelId` | `jp.anthropic.claude-haiku-4-5-20251001-v1:0` | Bedrock 推論プロファイル ID |

デプロイ後、SNS から確認メールが届くので承認してください。

## プロジェクト構成

```
.
├── app.py                        # CDK アプリケーションのエントリポイント
├── stacks/
│   └── trendline_stack.py        # メインスタック定義
├── lambda/
│   ├── fetch_x/
│   │   └── index.py              # X API タイムライン取得 Lambda
│   ├── summarize/
│   │   └── index.py              # Bedrock 要約 Lambda
│   └── layers/
│       └── x_sdk/
│           └── requirements.txt  # Lambda Layer 用依存パッケージ
├── pyproject.toml
├── cdk.json
└── aws-architecture.drawio       # 構成図
```

