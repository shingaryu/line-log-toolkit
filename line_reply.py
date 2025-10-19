#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
line_reply.py — LINEの返信案をOpenAI APIで生成（解析は line_core を再利用）
"""
import argparse, os
import time, random
import re

from typing import List

from line_core import (
    load_recent_messages, pick_last_incoming, render_context_block, Msg
)
from openai import RateLimitError, APIError, APIConnectionError, Timeout

# OpenAI 公式SDK（Responses API）
# pip install openai
from openai import OpenAI   # 環境変数 OPENAI_API_KEY を使用  :contentReference[oaicite:1]{index=1}

NUM_PAT   = re.compile(r"\d{1,3}(,\d{3})+|\d+")
YEN_PAT   = re.compile(r"(¥|円)")
DATE_PAT  = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)|(\d{1,2})月|(\d{4})[/-](\d{1,2})[/-](\d{1,2})")
URL_PAT   = re.compile(r"https?://")
KATA_PAT  = re.compile(r"[ァ-ヶー]{3,}")
Q_PAT     = re.compile(r"[?？]|(どう|どこ|なに|何|いつ|なぜ|どれ|だれ)")
IMP_PAT   = re.compile(r"(連絡|確認|決め|調整|予約|依頼|返信|対応|相談|検討|提出|手配)")

def _score_message_text(t: str) -> int:
    t = t or ""
    s = 0
    if NUM_PAT.search(t):  s += 1
    if YEN_PAT.search(t):  s += 2
    if DATE_PAT.search(t): s += 1
    if URL_PAT.search(t):  s += 2
    if KATA_PAT.search(t): s += 1
    if Q_PAT.search(t):    s += 1
    if IMP_PAT.search(t):  s += 1
    if len(t) >= 20:       s += 1
    return s

def collect_evidence_snippets_generic(msgs: List, limit: int = 12, window: int = 1) -> List[str]:
    scored = [(i, _score_message_text(m.text)) for i, m in enumerate(msgs)]
    scored = [p for p in scored if p[1] > 0]
    scored.sort(key=lambda x: (-x[1], x[0]))
    picked, used = [], set()
    for i, _ in scored:
        if any(abs(i - j) <= window for j in used):
            continue
        picked.append(i)
        for j in range(i - window, i + window + 1):
            used.add(j)
        if len(picked) >= limit:
            break
    out = []
    for i in picked:
        start = max(0, i - window)
        end   = min(len(msgs) - 1, i + window)
        block = []
        for j in range(start, end + 1):
            mj = msgs[j]
            line = (mj.text or "").replace("\r"," ").replace("\n"," ⏎ ")
            block.append(f"- {mj.date} {mj.time} {mj.sender}: {line}")
        out.append("\n".join(block))
    return out



def call_with_retries(client, model, instructions, user_prompt,
                      max_retries=6, base=0.8, cap=8.0):
    """
    429 のうち:
      - code == 'insufficient_quota' -> すぐに中断（課金/月次予算の問題）
      - それ以外(一時的なレート制限/過負荷) -> 指数バックオフで再試行
    ネットワーク類(APIConnectionError/Timeout)も再試行対象
    """
    tries = 0
    while True:
        try:
            return client.responses.create(
                model=model,
                instructions=instructions,
                input=user_prompt,
                # max_output_tokens=args.max_output_tokens,
            )
        except RateLimitError as e:
            # エラーペイロードを解析
            msg = str(e)
            code = None
            try:
                payload = getattr(e, "response", None)
                if payload is not None:
                    j = payload.json()
                    code = j.get("error", {}).get("code")
                    msg = j.get("error", {}).get("message", msg)
            except Exception:
                pass

            # クレジット/月次予算切れは即終了（リトライ無意味）
            if code == "insufficient_quota" or "insufficient_quota" in (msg or ""):
                raise SystemExit(
                    "OpenAI: APIの利用枠が尽きています（insufficient_quota）。"
                    "ダッシュボードで課金設定・月次予算・所属組織を確認してください。"
                )

            # 一時的な429はバックオフ再試行
            if tries >= max_retries:
                raise
            delay = min(cap, base * (2 ** tries)) + random.uniform(0, 0.25)
            time.sleep(delay)
            tries += 1

        except (APIConnectionError, Timeout) as e:
            if tries >= max_retries:
                raise
            delay = min(cap, base * (2 ** tries)) + random.uniform(0, 0.25)
            time.sleep(delay)
            tries += 1

def safe_response_text(resp) -> str:
    """
    SDKのバージョン差異に耐えるテキスト抽出。
    - まず response.output_text（あれば）を使う
    - なければ response.output の構造を辿って text を連結
    - それも無理なら to_dict() 経由でbest-effort
    参考: READMEの使用例と、output_textの互換性に関する議論。:contentReference[oaicite:2]{index=2}
    """
    txt = getattr(resp, "output_text", None)
    if isinstance(txt, str) and txt.strip():
        return txt.strip()

    # フィールドをたどる（将来のスキーマ変化にbest-effortで追従）
    try:
        parts: List[str] = []
        out = getattr(resp, "output", None) or []
        for item in out:
            t = getattr(item, "type", None)
            if t == "message":
                for c in getattr(item, "content", []) or []:
                    if getattr(c, "type", None) in ("output_text", "text"):
                        parts.append(getattr(c, "text", "") or "")
            elif t == "text":
                parts.append(getattr(item, "text", "") or "")
        joined = "\n".join([p for p in parts if p.strip()])
        if joined.strip():
            return joined.strip()
    except Exception:
        pass

    try:
        d = resp.to_dict()
        # 代表的な形を手当て
        for path in [
            ("output_text",),
            ("content",),
        ]:
            node = d
            ok = True
            for k in path:
                if isinstance(node, dict) and k in node:
                    node = node[k]
                else:
                    ok = False
                    break
            if ok and isinstance(node, str) and node.strip():
                return node.strip()
        return str(d)
    except Exception:
        return str(resp)

def build_user_prompt(context_block: str, last_msg: Msg, custom_instruction: str, my_name: str) -> str:
    return (
        "以下は家族LINEの直近のやり取りです。最後の相手メッセージに対する返信案を作ってください。\n\n"
        "【会話コンテキスト（古→新）】\n"
        f"{context_block}\n\n"
        "【今回の返信ターゲット】\n"
        f"{last_msg.date} {last_msg.time} {last_msg.sender}: {last_msg.text.replace(chr(10),' ⏎ ')}\n\n"
        "【カスタム指示】\n"
        f"{custom_instruction}\n\n"
        "【出力要件】\n"
        f"- 送信者は「{my_name}」の口調で、日本語、LINEの会話らしい簡潔さ。\n"
        "- まず本命の返信案を1つ。その後に『別案』として2案まで箇条書き（任意）。\n"
        "- 相手の感情配慮／誤解を避ける言い回しを優先。不要な機密は書かない。\n"
        "- スタンプ提案が自然なら、末尾に《スタンプ案: …》を1つ（任意）。"
    )

def build_decision_prompt(context_block: str, last_msg, my_name: str, snippets: List[str], custom_instruction: str) -> str:
    evidence = "\n\n".join(snippets) if snippets else "（根拠候補は少なめ）"
    return (
        "家族LINEの直近のやり取りを踏まえて、意見・判断を提示してください。\n"
        "以下の要件で出力します。\n\n"
        "【出力フォーマット】\n"
        "1) 送信案（そのままコピペ可）：\n"
        "   - 冒頭に結論（依頼先/次アクション）\n"
        "   - 次に具体アクション（誰が何をいつ）\n"
        f"   - 口調は「{my_name}」として自然な日本語、家族向けに簡潔\n"
        "2) 根拠メモ（箇条書き）：\n"
        "   - 決定理由の要旨＋日付（要約可）\n"
        "3) 迷いどころ（場合分け）：\n"
        "   - 想定反論や不確定要素への代替案\n\n"
        "【会話コンテキスト（古→新）】\n"
        f"{context_block}\n\n"
        "【今回の返信ターゲット】\n"
        f"{last_msg.date} {last_msg.time} {last_msg.sender}: {(last_msg.text or '').replace(chr(10),' ⏎ ')}\n\n"
        "【根拠候補スニペット】\n"
        f"{evidence}\n\n"
        f"【補助指示】\n{custom_instruction or '（特になし）'}\n"
    )


def main():
    ap = argparse.ArgumentParser(description="LINE返信メーカー（OpenAI API / line_core共通化）")
    ap.add_argument("--input-dir", required=True, help="月別ログ(YYYY-MM.txt)のディレクトリ")
    ap.add_argument("--my-name", required=True, help="自分の表示名（ログ内の送信者名と一致）")
    ap.add_argument("--months", type=int, default=2, help="直近何か月分を読むか（既定: 2）")
    ap.add_argument("--instruction-file", required=True, help="カスタム指示のテキストファイル")
    ap.add_argument("--model", default="gpt-4o-mini", help="使用モデル（例: gpt-4o-mini）")
    ap.add_argument("--n", type=int, default=2, help="返信候補の個数（既定: 2）")
    ap.add_argument("--context-window", type=int, default=40, help="前文脈として含めるメッセージ数（既定: 40）")
    ap.add_argument("--mode", choices=["auto", "decision"], default="auto",
                    help="auto=短文返信（従来）。decision=提案＋根拠＋場合分け。")
    ap.add_argument("--max-output-tokens", type=int, default=600,
                    help="出力トークン上限（暴走対策）。既定: 600")
    args = ap.parse_args()

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
        snippets = collect_evidence_snippets_generic(msgs, limit=12, window=1)
        user_prompt = build_decision_prompt(context_block, last_msg, args.my_name, snippets, custom_instruction)
        system_instructions = (
            "あなたは家族グループに対して、実務的な意思決定を分かりやすく提示する補佐です。"
            "出力は『送信案→根拠メモ→迷いどころ（場合分け）』の順に簡潔・具体。"
            "日付や数量は可能な範囲で具体化し、断定が難しい点は場合分けで明示してください。"
        )
    else:  # auto = 短文返信のみ
        user_prompt = build_user_prompt(context_block, last_msg, custom_instruction, args.my_name)
        system_instructions = (
            "あなたはLINEの返信文を作るアシスタントです。"
            "丁寧すぎず素っ気なくもない、家族向けの自然な日本語で短く返してください。"
            "誤解を避け、相手の感情を先に受け止めてから要件を伝えます。"
            "出力は本文のみ。前置きや思考過程は書かないでください。"
        )

    client = OpenAI()  # OPENAI_API_KEY を自動使用  :contentReference[oaicite:3]{index=3}

    print("====== 返信候補 ======")
    for i in range(max(1, args.n)):
        resp = call_with_retries(
            client=client,
            model=args.model,
            instructions=system_instructions,
            user_prompt=user_prompt,
        )        
        text = safe_response_text(resp)
        print(f"\n[{i+1}] {text}\n")

if __name__ == "__main__":
    main()
