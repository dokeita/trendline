# referenced_tweets による会話文脈の取得

## 概要

`tweet_fields` に `referenced_tweets` を追加し、投稿が引用RTなのかリプライなのかを判別できるようにする。会話の流れや議論の構造を要約に反映する。

## 現状

- 各ポストが独立した情報として扱われている
- 引用RTやリプライチェーンの文脈が失われている

## 対応内容

- [ ] `fetch_x/index.py`: `tweet_fields` に `referenced_tweets` を追加
- [ ] `fetch_x/index.py`: 保存データに `referenced_tweets`（type: replied_to / quoted / retweeted と参照先 ID）を含める
- [ ] `summarize/index.py`: 引用・リプライ関係をプロンプトに反映し、議論の構造を要約に含める

## 期待効果

- 単発の投稿と議論の一部を区別できる
- 話題になっている議論のスレッドを構造的に要約できる

## 備考

- API レスポンスのデータ量が増えるため、S3 保存コストへの影響は軽微だが留意する
