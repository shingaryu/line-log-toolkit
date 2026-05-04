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

起動時に **Bot 固有のリッチメニュー**（「LINE Log Toolkit」と表示される緑色の画像）を自動で作成・設定します。他の Bot プログラムが設定したリッチメニューが残る誤操作を防ぎます。画像は Pillow で動的に生成されるため、別途画像ファイルを用意する必要はありません。

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

## プライバシー保護パイプライン

`privacy` コマンドは、セキュアAPIとローカル辞書を使ってステップ2〜6を一括実行します。

1. 生テキストをセキュアAPIへ送り、固有名詞・連絡先などを抽出する
2. ローカルJSONの仮名化辞書を生成・更新する
3. 辞書に基づいて生テキストを一貫した仮名へ置換する
4. 仮名化済みテキストだけを分析用APIへ送る
5. 分析結果内の仮名をローカル辞書で復元する

```bash
python cli.py privacy --input input/raw_log.txt --out out/privacy \
  --map .pseudonym_map.json --instruction-file custom_instruction.txt
```

段階実行:

```bash
# ステップ1〜3: 抽出、辞書更新、仮名化まで
python cli.py privacy --input input/2026-02.txt --out out/privacy-test \
  --map .pseudonym_map.test.json --until pseudonymize

# ステップ1〜5: 抽出から復元済み分析まで一括
python cli.py privacy --input input/2026-02.txt --out out/privacy-test \
  --map .pseudonym_map.test.json --instruction-file custom_instruction.txt --until restore

# 既存辞書を流用して今回の辞書へ統合する
python cli.py privacy --input input/2026-02.txt --out out/privacy-test \
  --map .pseudonym_map.current.json --merge-map .pseudonym_map.previous.json \
  --instruction-file custom_instruction.txt --until restore
```

分析工程では `reply` と同じインターフェースで
`--instruction-file custom_instruction.txt` を指定できます。
仮名化辞書の各 entry には `surfaces` と `restore_as` が保存されます。
表記揺れは `surfaces` に同じ仮名として並べて保存され、復元時の代表表記は
`restore_as` をユーザーが編集して調整できます。
`--merge-map` を指定すると、ユーザーが流用可能と判断した既存辞書を読み込み、
既存の仮名を維持したまま今回AIが抽出したエンティティと統合します。
一致する表記や `surfaces` は同一エンティティとして扱われるため、複数ファイルを
仮名化したあと分析APIへ渡しても、同じ人物・場所を同じ仮名で接続しやすくなります。

生成ファイル:

- `.pseudonym_map.json`: 元語と仮名を対応づけるローカル専用辞書
- `out/privacy/extracted_entities.json`: 抽出された機密情報候補
- `out/privacy/pseudonymized.txt`: 分析APIへ送る仮名化済みテキスト
- `out/privacy/analysis_pseudonymized.md`: 仮名を含む分析結果
- `out/privacy/analysis_restored.md`: 仮名を復元した最終出力

`.pseudonym_map*.json` は復元可能な辞書を含むため Git 管理対象外です。

## todo:
- extract_entities_with_ai で表記揺れを配列にして返してくれる想定だが大抵1つしかふくまれていない
  - gpt5.5なら期待通りだが古いモデルでも動くように安定化させたい
- CLIインターフェースでMAPファイルとmerge mapファイルを両方指定する必要があるか不明、作成ロジックの想定は下記
  - 今回の入力ファイルに対する抽出entities...(a)
    - 保存時のファイル名は、デフォルト値はあっていいが必須ではない
  - entitiesに施した仮名を記述した辞書(map)ファイル...(b)
    - 復号化するときに使用
  - (a)は、ユーザーの指定によらず入力ファイルに対するAPIレスポンスによってきまる
  - (b)は、ユーザーの指定によって：
    - 指定なし：今回の抽出結果(a)に新たに仮名を当てはめて作成
    - 既存のmapをユーザーが指定したとき(マージ処理)：今回の抽出結果(a)に仮名を当てはめるが、既存のmapに同じ意味のentityがあれば同じ仮名を利用する。
- mapファイルのマージでコンフリクトが起きた場合の対処(手動含む)