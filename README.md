# lone_log_simple.py

## 概要

line_log_toolkit は、LINE のエクスポートテキストを **月別テキストや JSON に整理し、AI で扱いやすい形に変換するためのツール群**です。

巨大な 1 本のトーク履歴をそのまま扱うのではなく、月ごとに分割・構造化することで、検索しやすくし、Google Drive 連携や ChatGPT / API を使った再利用をしやすくします。

このツールは単なる変換器ではなく、整理した履歴をもとに **返信文の作成、意思決定の補助、過去会話の再参照** を可能にするための前処理基盤として設計されています。

## このツールが必要な理由

LINE のエクスポート履歴は通常、巨大な 1 ファイルとして出力されます。
そのままでは次の問題があります。

* ファイルが大きすぎて AI が一度に扱いにくい
* 特定期間や特定話題の抽出がしづらい
* Google Drive や別コンテキストの ChatGPT に再投入する際に扱いにくい
* 返信作成や意思決定支援に必要な「文脈の再利用」がしにくい

このツールは、その問題を解決するために存在します。


## 想定ユースケース

主な用途は 2 つあります。

1. **履歴の整理と保管**
   巨大な LINE トーク履歴を月別テキストファイルや JSON に分割し、再検索しやすくする。

2. **AI による活用**
   整理済みの履歴をもとに、ChatGPT や OpenAI API を使って以下を行う。

   * 自分になりきった返信文の作成
   * 相手の発言内容の妥当性検討
   * 家族や関係者との意思決定のたたき台作成
   * 過去会話を踏まえた文脈付き回答

## 機能
- **split**: 巨大テキスト → **月別** `YYYY-MM.txt` + `messages.json`
- **snippets**: `messages.json` → ヒット前後 ±N の Markdown パック
- **prompt**: 別コンテキストの ChatGPT に貼るための **前提テンプレ** を自動生成（**月別ファイル前提**）

## 使い方
```bash
# 1) 分割 + JSON
python line_log_simple.py split --input line_family_messaging_history.txt --out out

# 2) スニペット Pack
python line_log_simple.py snippets --json out/messages.json --out out --kw "給湯器,床,外壁,工務店" --window 2

# 3) 前提テンプレ（ChatGPT にコピペして、最後の【指示】だけ追記）
python line_log_simple.py prompt --out out \
  --gdrive-folder "/家族イベント/LINE/月別" \
  --file-pattern "YYYY-MM.txt" \
  --your-name "松澤晃樹"
# → out/chatgpt_prompt_template.md
```

## 出力物
- `out/2021-03.txt, out/2021-04.txt, ...` （生行そのまま）
- `out/messages.json` （通常 JSON / 配列）
- `out/snippet_pack.md` （ヒット行の前後文脈）
- `out/chatgpt_prompt_template.md` （そのまま ChatGPT へ貼り付け可能）
