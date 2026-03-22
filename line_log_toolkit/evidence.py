"""
evidence.py — メッセージの重要度スコアリングと根拠スニペット収集

OpenAI に渡す文脈として「重要そうなメッセージ」を自動選別する。
"""

import re
from typing import List

from .parser import Msg

NUM_PAT  = re.compile(r"\d{1,3}(,\d{3})+|\d+")
YEN_PAT  = re.compile(r"(¥|円)")
DATE_PAT = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)|(\d{1,2})月|(\d{4})[/-](\d{1,2})[/-](\d{1,2})")
URL_PAT  = re.compile(r"https?://")
KATA_PAT = re.compile(r"[ァ-ヶー]{3,}")
Q_PAT    = re.compile(r"[?？]|(どう|どこ|なに|何|いつ|なぜ|どれ|だれ)")
IMP_PAT  = re.compile(r"(連絡|確認|決め|調整|予約|依頼|返信|対応|相談|検討|提出|手配)")


def score_message_text(t: str) -> int:
    """テキストの「重要度」をヒューリスティックにスコアリングする。"""
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


def collect_evidence_snippets(msgs: List[Msg], limit: int = 12, window: int = 1) -> List[str]:
    """
    スコアの高いメッセージ前後を抽出して文字列スニペットのリストを返す。
    重複を避けるため、すでに採用済みの近傍は除外する。
    """
    scored = [(i, score_message_text(m.text)) for i, m in enumerate(msgs)]
    scored = [p for p in scored if p[1] > 0]
    scored.sort(key=lambda x: (-x[1], x[0]))

    picked: List[int] = []
    used: set = set()
    for i, _ in scored:
        if any(abs(i - j) <= window for j in used):
            continue
        picked.append(i)
        for j in range(i - window, i + window + 1):
            used.add(j)
        if len(picked) >= limit:
            break

    out: List[str] = []
    for i in picked:
        start = max(0, i - window)
        end = min(len(msgs) - 1, i + window)
        block = []
        for j in range(start, end + 1):
            mj = msgs[j]
            line = (mj.text or "").replace("\r", " ").replace("\n", " ⏎ ")
            block.append(f"- {mj.date} {mj.time} {mj.sender}: {line}")
        out.append("\n".join(block))
    return out
