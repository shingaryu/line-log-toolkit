#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cli.py — LINE トーク履歴ツールキットの CLI エントリポイント

サブコマンド:
  split     巨大テキスト → 月別 YYYY-MM.txt + messages.json
  snippets  JSON からキーワードスニペット Pack を生成
  prompt    ChatGPT 向けの前提テンプレートを生成
  reply     OpenAI API で返信案 / 意思決定案を生成
  privacy   機密情報抽出、仮名化、分析、復元を一括実行
"""

import argparse

from dotenv import load_dotenv
from openai import OpenAI

from line_log_toolkit import (
    build_decision_prompt,
    build_user_prompt,
    call_with_retries,
    collect_evidence_snippets,
    load_recent_messages,
    make_snippets,
    PRIVACY_UNTIL_CHOICES,
    pick_last_incoming,
    render_context_block,
    run_privacy_pipeline,
    safe_response_text,
    split_and_parse,
    write_prompt_template,
)


def cmd_split(args):
    json_path = split_and_parse(
        args.input, args.out,
        emit_json=not args.no_json,
        json_name=args.json_name,
    )
    if json_path and not args.no_json:
        print(f"Wrote JSON: {json_path}")
    print(f"Wrote monthly txt files under: {args.out}")


def cmd_snippets(args):
    kws = [s.strip() for s in args.kw.split(",") if s.strip()]
    md = make_snippets(args.json, args.out, kws, window=args.window)
    print(f"Wrote snippets: {md}")


def cmd_prompt(args):
    p = write_prompt_template(
        args.out, args.gdrive_folder, args.file_pattern,
        args.your_name, filename=args.filename,
    )
    print(f"Wrote prompt template: {p}")


def cmd_reply(args):
    msgs = load_recent_messages(args.input_dir, months=args.months)
    if not msgs:
        raise SystemExit("ログが見つかりません")

    idx = pick_last_incoming(msgs, my_name=args.my_name)
    if idx is None:
        raise SystemExit("直近に相手からのテキストメッセージが見つかりませんでした")

    start = max(0, idx - args.context_window)
    context_block = render_context_block(msgs, start, idx + 1)
    last_msg = msgs[idx]

    with open(args.instruction_file, "r", encoding="utf-8") as f:
        custom_instruction = f.read().strip()

    if args.mode == "decision":
        snippets = collect_evidence_snippets(msgs, limit=12, window=1)
        user_prompt = build_decision_prompt(
            context_block, last_msg, args.my_name, snippets, custom_instruction,
        )
        system_instructions = (
            "あなたは家族グループに対して、実務的な意思決定を分かりやすく提示する補佐です。"
            "出力は『送信案→根拠メモ→迷いどころ（場合分け）』の順に簡潔・具体。"
            "日付や数量は可能な範囲で具体化し、断定が難しい点は場合分けで明示してください。"
        )
    else:
        user_prompt = build_user_prompt(
            context_block, last_msg, custom_instruction, args.my_name,
        )
        system_instructions = (
            "あなたはLINEの返信文を作るアシスタントです。"
            "丁寧すぎず素っ気なくもない、家族向けの自然な日本語で短く返してください。"
            "誤解を避け、相手の感情を先に受け止めてから要件を伝えます。"
            "出力は本文のみ。前置きや思考過程は書かないでください。"
        )

    client = OpenAI()

    print("====== 返信候補 ======")
    for i in range(max(1, args.n)):
        resp = call_with_retries(
            client=client,
            model=args.model,
            instructions=system_instructions,
            user_prompt=user_prompt,
            max_output_tokens=args.max_output_tokens,
        )
        text = safe_response_text(resp)
        print(f"\n[{i+1}] {text}\n")


def cmd_privacy(args):
    custom_instruction = None
    if args.instruction_file:
        with open(args.instruction_file, "r", encoding="utf-8") as f:
            custom_instruction = f.read().strip()

    client = OpenAI()
    result = run_privacy_pipeline(
        input_path=args.input,
        out_dir=args.out,
        map_path=args.map,
        client=client,
        merge_map_path=args.merge_map,
        extract_model=args.extract_model,
        analysis_model=args.analysis_model,
        custom_instruction=custom_instruction,
        extract_max_output_tokens=args.extract_max_output_tokens,
        analysis_max_output_tokens=args.analysis_max_output_tokens,
        allow_short_entities=args.allow_short_entities,
        until=args.until,
    )

    print(f"Completed until: {result.completed_until}")
    print(f"Extracted entities: {result.entity_count} ({result.new_entity_count} new)")
    print(
        "Merged map entries: "
        f"{result.reused_entry_count} imported, "
        f"{result.merged_entry_count} merged, "
        f"{result.merge_conflict_count} pseudonym conflicts"
    )
    print(f"Local map: {result.map_path}")
    print(f"Extracted entities JSON: {result.extracted_entities_path}")
    if result.pseudonymized_text_path is not None:
        print(f"Pseudonymized text: {result.pseudonymized_text_path}")
    if result.analysis_pseudonymized_path is not None:
        print(f"Pseudonymized analysis: {result.analysis_pseudonymized_path}")
    if result.analysis_restored_path is not None:
        print(f"Restored analysis: {result.analysis_restored_path}")


def main():
    load_dotenv()
    ap = argparse.ArgumentParser(
        prog="line-log-toolkit",
        description="LINE トーク履歴の分割・整理・AI 活用ツールキット",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    # --- split ---
    p_split = sub.add_parser("split", help="月別テキストに分割し、JSON を書き出す")
    p_split.add_argument("--input", required=True, help="入力ファイル（LINE エクスポートテキスト）")
    p_split.add_argument("--out", default="out", help="出力ディレクトリ（既定: out）")
    p_split.add_argument("--no-json", action="store_true", help="JSON 出力を抑制")
    p_split.add_argument("--json-name", default="messages.json", help="JSON ファイル名（既定: messages.json）")
    p_split.set_defaults(func=cmd_split)

    # --- snippets ---
    p_snip = sub.add_parser("snippets", help="JSON からスニペット Pack を生成")
    p_snip.add_argument("--json", required=True, help="messages.json のパス")
    p_snip.add_argument("--out", default="out", help="出力ディレクトリ")
    p_snip.add_argument(
        "--kw",
        default="床,フローリング,床下,束石,外壁,塗装,屋根,雨漏り,雨樋,シロアリ,白蟻,防蟻,"
                "給湯器,給湯,分電盤,ブレーカー,エアコン,門扉,見積,工務店,点検,修理,工事,交換,撤去,畳",
        help="カンマ区切りのキーワード一覧",
    )
    p_snip.add_argument("--window", type=int, default=2, help="前後何メッセージを含めるか（既定: 2）")
    p_snip.set_defaults(func=cmd_snippets)

    # --- prompt ---
    p_prompt = sub.add_parser("prompt", help="ChatGPT 用の前提テンプレートを生成（月別前提）")
    p_prompt.add_argument("--out", default="out", help="出力ディレクトリ")
    p_prompt.add_argument("--gdrive-folder", required=True, help="Google Drive 上のフォルダパス")
    p_prompt.add_argument("--file-pattern", default="YYYY-MM.txt", help="ファイル名パターン")
    p_prompt.add_argument("--your-name", default="松澤晃樹", help="自分の表示名")
    p_prompt.add_argument("--filename", default="chatgpt_prompt_template.md", help="出力ファイル名")
    p_prompt.set_defaults(func=cmd_prompt)

    # --- reply ---
    p_reply = sub.add_parser("reply", help="OpenAI API で返信案 / 意思決定案を生成")
    p_reply.add_argument("--input-dir", required=True, help="月別ログ (YYYY-MM.txt) のディレクトリ")
    p_reply.add_argument("--my-name", required=True, help="自分の表示名（ログ内の送信者名と一致）")
    p_reply.add_argument("--months", type=int, default=2, help="直近何か月分を読むか（既定: 2）")
    p_reply.add_argument("--instruction-file", required=True, help="カスタム指示のテキストファイル")
    p_reply.add_argument("--model", default="gpt-4o-mini", help="使用モデル（既定: gpt-4o-mini）")
    p_reply.add_argument("--n", type=int, default=2, help="返信候補の個数（既定: 2）")
    p_reply.add_argument("--context-window", type=int, default=40, help="前文脈メッセージ数（既定: 40）")
    p_reply.add_argument(
        "--mode", choices=["auto", "decision"], default="auto",
        help="auto=短文返信。decision=提案＋根拠＋場合分け。",
    )
    p_reply.add_argument("--max-output-tokens", type=int, default=600, help="出力トークン上限（既定: 600）")
    p_reply.set_defaults(func=cmd_reply)

    # --- privacy ---
    p_privacy = sub.add_parser(
        "privacy",
        help="機密情報抽出、仮名化、分析、復元を一括実行",
    )
    p_privacy.add_argument("--input", required=True, help="処理対象の生テキストファイル")
    p_privacy.add_argument("--out", default="out/privacy", help="出力ディレクトリ")
    p_privacy.add_argument(
        "--map",
        default=".pseudonym_map.json",
        help="ローカル仮名化辞書 JSON",
    )
    p_privacy.add_argument(
        "--merge-map",
        default=None,
        help="流用する既存の仮名化辞書 JSON。指定時は今回の辞書へ統合",
    )
    p_privacy.add_argument(
        "--extract-model",
        default=None,
        help="抽出用モデル。未指定時は OPENAI_MODEL または gpt-4o-mini",
    )
    p_privacy.add_argument(
        "--analysis-model",
        default=None,
        help="分析用モデル。未指定時は OPENAI_MODEL または gpt-4o-mini",
    )
    p_privacy.add_argument(
        "--instruction-file",
        default=None,
        help="任意の追加分析指示ファイル",
    )
    p_privacy.add_argument(
        "--extract-max-output-tokens",
        type=int,
        default=2000,
        help="抽出API応答の出力トークン上限",
    )
    p_privacy.add_argument(
        "--analysis-max-output-tokens",
        type=int,
        default=1800,
        help="分析API応答の出力トークン上限",
    )
    p_privacy.add_argument(
        "--until",
        choices=PRIVACY_UNTIL_CHOICES,
        default="restore",
        help="停止位置: map, pseudonymize, analysis, restore",
    )
    p_privacy.add_argument(
        "--allow-short-entities",
        action="store_true",
        help="1文字の抽出候補も許可する。短い名前に有効だが過剰置換に注意",
    )
    p_privacy.set_defaults(func=cmd_privacy)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
