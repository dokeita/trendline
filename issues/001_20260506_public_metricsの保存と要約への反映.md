# public_metrics の保存と要約への反映

## 概要

fetch_x Lambda で取得している `public_metrics`（いいね数・RT数・リプライ数）を JSON に保存し、summarize Lambda のプロンプトに含めることで、話題になっている投稿を重み付けして要約できるようにする。

## 現状

- `tweet_fields=["public_metrics"]` を API に渡しているが、保存時にデータを捨てている
- 要約はテキストのみで行われており、エンゲージメントの高低が区別できない

## 対応内容

- [x] `fetch_x/index.py`: ポスト保存時に `public_metrics`（`like_count`, `retweet_count`, `reply_count`, `impression_count`）を含める
- [x] `summarize/index.py`: プロンプトにエンゲージメント指標を付記し、注目度の高い投稿を優先的に要約するよう指示を追加

## 期待効果

- バズっている投稿とそうでない投稿を区別した要約が可能になる
- ユーザーにとって重要度の高い情報が上位に来る
