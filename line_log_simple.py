#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
line_log_simple.py (v3: 月別分割版) — 共通化版
- CLIの挙動・引数・出力は**従来どおり**
- 解析ロジックは line_core へ委譲（重複排除）
"""
import argparse, os, json
from line_core import split_and_parse  # ← 解析本体を委譲

def make_snippets(json_path: str, out_dir: str, keywords: list, window: int = 2) -> str:
    os.makedirs(out_dir, exist_ok=True)
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    msgs = data.get("messages", [])
    hits = []
    for i, m in enumerate(msgs):
        text = m.get("text", "") or ""
        if any(kw in text for kw in keywords):
            hits.append(i)

    out_md = os.path.join(out_dir, "snippet_pack.md")
    with open(out_md, "w", encoding="utf-8") as w:
        w.write("# Snippet Pack\n\n")
        w.write(f"ヒット行の前後文脈（±{window} メッセージ）。必要部分だけ貼り付けてください。\n\n")
        for idx in hits:
            m = msgs[idx]
            hit_kws = [kw for kw in keywords if kw in (m.get('text') or '')]
            w.write(f"## {m.get('date')} {m.get('time')} 〔hit: {'/'.join(hit_kws)}〕\n\n")
            start = max(0, idx - window)
            end = min(len(msgs) - 1, idx + window)
            for j in range(start, end + 1):
                mj = msgs[j]
                line = (mj.get('text') or '').replace('\r', ' ').replace('\n', ' ⏎ ')
                w.write(f"- {mj.get('date')} {mj.get('time')} {mj.get('sender')}: {line}\n")
            w.write("\n")
    return out_md

def write_prompt_template(out_dir: str, gdrive_folder: str, file_pattern: str, your_name: str, filename: str = "chatgpt_prompt_template.md") -> str:
    os.makedirs(out_dir, exist_ok=True)
    default_pat = (file_pattern or "").strip().lower()
    if default_pat == "yyyy-mm.txt":
        pat_desc = "例: 2018-01.txt, 2018-02.txt, …（4桁の西暦-2桁月 + .txt）"
        regex_hint = r"^20\d{2}-(0[1-9]|1[0-2])\.txt$"
    else:
        pat_desc = f"ファイル名ルール: {file_pattern}"
        regex_hint = "(必要に応じて修正)"

    content = f"""# ChatGPT への最初の指示（テンプレ / 月別ファイル前提）

以下を前提として、対象フォルダ内の LINE トーク履歴（**月別テキスト**）を読み込み、会話の文脈を把握してください。続く【指示】に基づき回答してください。

## 前提
1. Googleドライブ連携は設定済み。
2. 対象フォルダ: `{gdrive_folder}`
3. 月別ファイル名ルール: {pat_desc}
   - 参考正規表現の目安: `{regex_hint}`
4. テキストのフォーマット仕様（このスクリプトの出力物）
   - 見出し行: `YYYY/MM/DD(曜)`
   - メッセージ行: `HH:MM<TAB>送信者<TAB>本文`
   - ダブルクォートで始まる本文は、閉じクォートまで多行にわたり得る（出力は元行そのまま）
5. 会話の登場人物
   - わたし = `{your_name}`（この名前が送信者として現れる）

## タスク
- 上記フォルダ内の該当**月ファイル**を読み取り、必要に応じて期間やキーワードで絞り込み、**文脈を把握**したうえで【指示】に回答してください。
- 回答時は、必要に応じて**日付**を明示し、主張の根拠となる**該当メッセージの抜粋**（要約で可）を添えてください。

## 解析ポリシー（簡易）
- 誤読を避けるため、曖昧な点は「解釈A/解釈B」で**場合分け**して述べる。
- 人物の呼称ゆれ（例: ニックネーム等）は文脈から同一人物かを推定し、断定困難な場合は注記。

## 指示
（ここに、わたしの具体的な依頼を書きます。例）
- わたしになりきって返信文を作成して。
- 〇〇さんの主張の妥当性を検討し、反論と代替案を箇条書きで。
- 今週の家族イベントの合意事項を3行で要約して。
"""
    path = os.path.join(out_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path

def main():
    ap = argparse.ArgumentParser(description="Simple LINE log splitter & helpers (v3: monthly) — core-shared")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_split = sub.add_parser("split", help="月別テキストに分割し、JSONを書き出す")
    p_split.add_argument("--input", required=True)
    p_split.add_argument("--out", default="out")
    p_split.add_argument("--no-json", action="store_true")
    p_split.add_argument("--json-name", default="messages.json")

    p_snip = sub.add_parser("snippets", help="JSON からスニペット Pack を生成")
    p_snip.add_argument("--json", required=True)
    p_snip.add_argument("--out", default="out")
    p_snip.add_argument("--kw", default="床,フローリング,床下,束石,外壁,塗装,屋根,雨漏り,雨樋,シロアリ,白蟻,防蟻,給湯器,給湯,分電盤,ブレーカー,エアコン,門扉,見積,工務店,点検,修理,工事,交換,撤去,畳")
    p_snip.add_argument("--window", type=int, default=2)

    p_prompt = sub.add_parser("prompt", help="別コンテキスト ChatGPT 用の前提テンプレ（**月別**前提）")
    p_prompt.add_argument("--out", default="out")
    p_prompt.add_argument("--gdrive-folder", required=True)
    p_prompt.add_argument("--file-pattern", default="YYYY-MM.txt")
    p_prompt.add_argument("--your-name", default="松澤晃樹")
    p_prompt.add_argument("--filename", default="chatgpt_prompt_template.md")

    args = ap.parse_args()
    if args.cmd == "split":
        json_path = split_and_parse(args.input, args.out, emit_json=not args.no_json, json_name=args.json_name)
        if json_path and not args.no_json:
            print(f"Wrote JSON: {json_path}")
        print(f"Wrote monthly txt files under: {args.out}")
    elif args.cmd == "snippets":
        kws = [s.strip() for s in args.kw.split(",") if s.strip()]
        md = make_snippets(args.json, args.out, kws, window=args.window)
        print(f"Wrote snippets: {md}")
    elif args.cmd == "prompt":
        p = write_prompt_template(args.out, args.gdrive_folder, args.file_pattern, args.your_name, filename=args.filename)
        print(f"Wrote prompt template: {p}")

if __name__ == "__main__":
    main()
