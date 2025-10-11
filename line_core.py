#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
line_core.py — 解析ロジックの共通化
- 月別テキスト(YYYY-MM.txt)のパース
- 巨大1ファイル → 月別分割 + JSON の実装（既存と同じ振る舞い）
- 返信生成用の補助（直近相手メッセ・文脈整形）
"""

import os, re, json
from dataclasses import dataclass
from typing import Optional, Dict, List

# ===== 既存仕様そのままの正規表現・ヘルパ =====
DATE_HDR = re.compile(r'^(?P<y>\d{4})/(?P<m>\d{1,2})/(?P<d>\d{1,2})\([^)]+\)\s*$')
MSG_LINE  = re.compile(r'^(?P<h>\d{1,2}):(?P<min>\d{2})\t(?P<name>[^\t]+)\t(?P<text>.*)$')

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

# ===== メッセージ表現 =====
@dataclass
class Msg:
    date: str   # YYYY-MM-DD
    time: str   # HH:MM
    sender: str
    text: str

# ===== 既存の split_and_parse（挙動は完全同一） =====
def split_and_parse(input_path: str, out_dir: str, emit_json: bool = True, json_name: str = "messages.json") -> str:
    os.makedirs(out_dir, exist_ok=True)
    month_handles: Dict[str, any] = {}

    def get_handle(month: str):
        p = os.path.join(out_dir, f"{month}.txt")  # e.g., 2021-03.txt
        if month not in month_handles:
            month_handles[month] = open(p, "w", encoding="utf-8", newline="\n")
        return month_handles[month]

    json_path = os.path.join(out_dir, json_name)
    jf = open(json_path, "w", encoding="utf-8") if emit_json else None
    first = True if jf else False

    current_date_iso: Optional[str] = None
    current_month: Optional[str] = None
    collecting = False
    cur_msg: Optional[Dict[str, str]] = None

    def flush_msg():
        nonlocal cur_msg, collecting, first
        if cur_msg is None:
            return
        if cur_msg["text"].startswith('"') and cur_msg["text"].count('"') >= 2 and cur_msg["text"].endswith('"'):
            cur_msg["text"] = strip_outer_quotes(cur_msg["text"])
        if jf:
            if not first:
                jf.write(",\n")
            jf.write(json.dumps(cur_msg, ensure_ascii=False))
            first = False
        cur_msg = None
        collecting = False

    with open(input_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\r\n")

            m = DATE_HDR.match(line)
            if m:
                if collecting or cur_msg is not None:
                    flush_msg()
                y, mo, d = m.group("y"), m.group("m"), m.group("d")
                current_date_iso = normalize_date(y, mo, d)
                current_month = ym_key(y, mo)
                get_handle(current_month).write(line + "\n")
                continue

            m = MSG_LINE.match(line)
            if m and current_month is not None and current_date_iso is not None:
                get_handle(current_month).write(line + "\n")
                if collecting or cur_msg is not None:
                    flush_msg()
                hhmm = f"{int(m.group('h')):02d}:{m.group('min')}"
                name = m.group("name")
                text = m.group("text")
                cur_msg = {
                    "date": current_date_iso,
                    "time": hhmm,
                    "sender": name,
                    "text": text
                }
                if is_wrapped_quote_open(text):
                    collecting = True
                else:
                    flush_msg()
                continue

            if current_month is not None:
                get_handle(current_month).write(line + "\n")

            if collecting and cur_msg is not None:
                cur_msg["text"] += "\n" + line
                if cur_msg["text"].count('"') % 2 == 0:
                    flush_msg()

    if collecting or cur_msg is not None:
        flush_msg()
    if jf:
        jf.write("\n]}\n")
        jf.close()
    for h in month_handles.values():
        h.close()
    return json_path if emit_json else ""

# ===== 返信生成向けの共通ユーティリティ =====
def parse_month_file(path: str) -> List[Msg]:
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
    files = [f for f in os.listdir(input_dir) if re.match(r'^\d{4}-(0[1-9]|1[0-2])\.txt$', f)]
    files.sort()               # 古→新
    if months > 0:
        files = files[-months:]
    all_msgs: List[Msg] = []
    for fn in files:
        all_msgs.extend(parse_month_file(os.path.join(input_dir, fn)))
    return all_msgs

def pick_last_incoming(msgs: List[Msg], my_name: str) -> Optional[int]:
    def is_attachment_like(t: str) -> bool:
        t = t.strip()
        return t.startswith("[スタンプ]") or t.startswith("[写真]") or t.startswith("[ファイル]")
    for i in range(len(msgs) - 1, -1, -1):
        m = msgs[i]
        if m.sender != my_name and not is_attachment_like(m.text):
            return i
    return None

def render_context_block(msgs: List[Msg], start: int, end: int) -> str:
    lines = []
    for m in msgs[start:end]:
        text_one = (m.text or "").replace("\r", " ").replace("\n", " ⏎ ")
        lines.append(f"{m.date} {m.time} {m.sender}: {text_one}")
    return "\n".join(lines)
