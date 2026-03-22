# line-log-toolkit

## 概要

LINE のエクスポートテキストを **月別テキストや JSON に整理し、AI で扱いやすい形に変換するためのツール群**です。

巨大な 1 本のトーク履歴をそのまま扱うのではなく、月ごとに分割・構造化することで、検索しやすくし、Google Drive 連携や ChatGPT / API を使った再利用をしやすくします。

整理した履歴をもとに **返信文の作成、意思決定の補助、過去会話の再参照** を可能にするための前処理基盤として設計されています。

## アーキテクチャ

設計方針: **「入力および出力」が「処理」を使う方向**。処理層は I/O 層に依存しません。

```
┌─────────────────────────────────────────────┐
│  入力 / 出力（I/O 層）                       │
│  ┌──────────┐  ┌──────────────┐             │
│  │ cli.py   │  │ bot_server.py│             │
│  │ (CLI)    │  │ (LINE Bot)   │             │
│  └────┬─────┘  └──────┬───────┘             │
│       │               │                     │
│       ▼               ▼                     │
│  ┌──────────────────────────────────────┐   │
│  │  line_log_toolkit/ （処理層パッケージ） │   │
│  │  ├ parser.py        解析・Msg 定義    │   │
│  │  ├ splitter.py      月別分割 + JSON   │   │
│  │  ├ snippets.py      キーワード抽出    │   │
│  │  ├ prompt_builder.py プロンプト作成   │   │
│  │  ├ evidence.py      根拠スコアリング  │   │
│  │  └ ai_client.py     OpenAI API 呼出  │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

## インストール

```bash
# 基本（CLI のみ）
pip install .

# Bot サーバーも使う場合
pip install ".[bot]"
```

## CLI コマンド

すべて `python cli.py <サブコマンド>` で実行します。

### split — 月別テキスト分割 + JSON

```bash
python cli.py split --input "input/[LINE] まつざわけのトーク.txt" --out splitted
```

- `--no-json` : JSON 出力を抑制
- `--json-name` : JSON ファイル名（既定: `messages.json`）

### snippets — キーワードスニペット Pack

```bash
python cli.py snippets --json splitted/messages.json --out out --kw "給湯器,床,外壁,工務店" --window 2
```

### prompt — ChatGPT 向け前提テンプレート

```bash
python cli.py prompt --out out_prompt \
  --gdrive-folder "/家族イベント/LINEトーク履歴/月別" \
  --your-name "松澤晃樹"
```

### reply — OpenAI API による返信案生成

```bash
# 短文返信（auto モード）
python cli.py reply --input-dir splitted --my-name "松澤晃樹" \
  --instruction-file custom_instruction.txt --model gpt-4o-mini --n 2

# 意思決定モード
python cli.py reply --input-dir splitted --my-name "松澤晃樹" \
  --instruction-file custom_instruction.txt --mode decision --n 3
```

オプション:
- `--months` : 読み込む月数（既定: 2）
- `--context-window` : 前文脈メッセージ数（既定: 40）
- `--mode auto|decision` : auto=短文返信、decision=提案＋根拠＋場合分け

## Bot サーバー

LINE Messaging API と連携し、ユーザーからファイルを受け取って AI 返信を返す Flask サーバーです。

```bash
# .env に LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN 等を設定
python bot_server.py
```

ngrok トンネルの自動接続と webhook URL の自動設定に対応しています（`USE_NGROK=1`）。

## 環境変数

| 変数名 | 用途 | 既定値 |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API キー | （必須） |
| `OPENAI_MODEL` | 使用モデル | `gpt-4o-mini` |
| `LINE_CHANNEL_SECRET` | LINE チャネルシークレット | Bot 使用時必須 |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE チャネルアクセストークン | Bot 使用時必須 |
| `MY_NAME` | 自分の表示名 | Bot 使用時必須 |
| `PORT` | Bot サーバーポート | `8000` |
| `USE_NGROK` | ngrok 自動接続 | `1` |

## 出力物

- `splitted/2021-03.txt, 2021-04.txt, ...` — 月別テキスト（生行そのまま）
- `splitted/messages.json` — 構造化 JSON（`{"messages": [...]}`）
- `out/snippet_pack.md` — キーワードヒット前後の文脈
- `out_prompt/chatgpt_prompt_template.md` — ChatGPT にそのまま貼り付け可能
