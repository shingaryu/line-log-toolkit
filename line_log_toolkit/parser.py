"""
parser.py — LINE トーク履歴テキストの解析ロジック

- 日付見出し行・メッセージ行の正規表現定義
- Msg データクラス（1メッセージを表す構造体）
- 月別テキスト (.txt) のパース
- 直近メッセージの検索、コンテキスト整形
"""

import os
import re
from dataclasses import dataclass
from typing import List, Optional

# ===== LINE エクスポート形式の正規表現 =====
DATE_HDR = re.compile(r'^(?P<y>\d{4})/(?P<m>\d{1,2})/(?P<d>\d{1,2})\([^)]+\)\s*$')
MSG_LINE = re.compile(r'^(?P<h>\d{1,2}):(?P<min>\d{2})\t(?P<name>[^\t]+)\t(?P<text>.*)$')


def normalize_date(y: str, m: str, d: str) -> str:
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def ym_key(y: str, m: str) -> str:
    return f"{int(y):04d}-{int(m):02d}"


def is_wrapped_quote_open(text: str) -> bool:
    return text.startswith('"') and (text.count('"') % 2 == 1)


def strip_outer_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


@dataclass
class Msg:
    """1件のメッセージを表す。"""
    date: str   # YYYY-MM-DD
    time: str   # HH:MM
    sender: str
    text: str


def parse_month_file(path: str) -> List[Msg]:
    """月別テキストファイルを読み込み、Msg のリストを返す。"""
    msgs: List[Msg] = []
    cur_date: Optional[str] = None
    collecting = False
    cur_msg: Optional[Msg] = None

    def flush():
        nonlocal cur_msg, collecting
        if cur_msg is not None:
            t = cur_msg.text.strip()
            if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
                cur_msg.text = t[1:-1]
            msgs.append(cur_msg)
            cur_msg = None
            collecting = False

    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\r\n")

            m = DATE_HDR.match(line)
            if m:
                if collecting or cur_msg is not None:
                    flush()
                cur_date = normalize_date(m.group("y"), m.group("m"), m.group("d"))
                continue

            m = MSG_LINE.match(line)
            if m and cur_date is not None:
                if collecting or cur_msg is not None:
                    flush()
                hhmm = f"{int(m.group('h')):02d}:{m.group('min')}"
                cur_msg = Msg(date=cur_date, time=hhmm, sender=m.group("name"), text=m.group("text"))
                if is_wrapped_quote_open(cur_msg.text):
                    collecting = True
                else:
                    flush()
                continue

            if collecting and cur_msg is not None:
                cur_msg.text += "\n" + line
                if cur_msg.text.count('"') % 2 == 0:
                    flush()

    if collecting or cur_msg is not None:
        flush()
    return msgs


def load_recent_messages(input_dir: str, months: int) -> List[Msg]:
    """input_dir 内の月別テキストから直近 months 分を読み込む。"""
    files = [f for f in os.listdir(input_dir)
             if re.match(r'^\d{4}-(0[1-9]|1[0-2])\.txt$', f)]
    files.sort()
    if months > 0:
        files = files[-months:]
    all_msgs: List[Msg] = []
    for fn in files:
        all_msgs.extend(parse_month_file(os.path.join(input_dir, fn)))
    return all_msgs


def pick_last_incoming(msgs: List[Msg], my_name: str) -> Optional[int]:
    """自分以外の直近テキストメッセージのインデックスを返す。"""
    def is_attachment_like(t: str) -> bool:
        t = t.strip()
        return t.startswith("[スタンプ]") or t.startswith("[写真]") or t.startswith("[ファイル]")

    for i in range(len(msgs) - 1, -1, -1):
        m = msgs[i]
        if m.sender != my_name and not is_attachment_like(m.text):
            return i
    return None


def render_context_block(msgs: List[Msg], start: int, end: int) -> str:
    """msgs[start:end] を1行1メッセージのテキストブロックに整形する。"""
    lines = []
    for m in msgs[start:end]:
        text_one = (m.text or "").replace("\r", " ").replace("\n", " ⏎ ")
        lines.append(f"{m.date} {m.time} {m.sender}: {text_one}")
    return "\n".join(lines)
