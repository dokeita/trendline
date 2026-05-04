# Trendline

X (Twitter) の投稿を毎朝自動で取得・要約し、メールで通知する AWS サーバーレスパイプラインです。

## アーキテクチャ

```
EventBridge (cron 6:00 JST)
  → Lambda (fetch_x) → X API から投稿を取得 → S3 に JSON 保存
      → EventBridge (S3 PutObject)
          → Lambda (summarize) → Bedrock (Claude) で要約 → SNS → メール通知
```

### 使用サービス

| サービス | 用途 |
|---|---|
| EventBridge Rule | 定時実行 (JST 6:00) / S3 イベント検知 |
| Lambda | X API 呼び出し / Bedrock 要約処理 |
| S3 | 取得した JSON の保存 |
| Bedrock (Claude 3 Haiku) | 投稿内容の要約 |
| SNS | メール通知 |
| Secrets Manager | X API の Bearer Token 管理 |

## 前提条件

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- [AWS CDK CLI](https://docs.aws.amazon.com/cdk/v2/guide/cli.html)
- AWS アカウントと認証情報の設定済み環境
- Secrets Manager に X API の Bearer Token を登録済み

### Secrets Manager の設定

マネジメントコンソールから以下の形式でシークレットを作成してください。

- シークレット名: `trendline/x-api-keys` (デフォルト、変更可)
- 値:

```json
{
  "bearer_token": "YOUR_X_API_BEARER_TOKEN"
}
```

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

シークレット名をデフォルトから変更する場合:

```bash
uv run cdk deploy \
  --parameters NotificationEmail=your-email@example.com \
  --parameters SecretName=your/custom-secret-name
```

デプロイ後、SNS から確認メールが届くので承認してください。

## プロジェクト構成

```
.
├── app.py                     # CDK アプリケーションのエントリポイント
├── stacks/
│   └── trendline_stack.py     # メインスタック定義
├── lambda/
│   ├── fetch_x/
│   │   └── index.py           # X API 取得 Lambda
│   └── summarize/
│       └── index.py           # Bedrock 要約 Lambda
├── pyproject.toml
├── cdk.json
└── aws-architecture.drawio    # 構成図
```

## 主なコマンド

```bash
uv run cdk synth    # CloudFormation テンプレートの生成
uv run cdk diff     # デプロイ済みスタックとの差分確認
uv run cdk deploy   # デプロイ
uv run cdk destroy  # スタックの削除
```
