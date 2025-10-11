# line_log_simple.py (v3) — 月別分割 + 前提テンプレ

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
