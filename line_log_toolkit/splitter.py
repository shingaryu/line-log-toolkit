"""
splitter.py — LINE トーク履歴の巨大テキストを月別ファイル + JSON に分割する
"""

import json
import os
from typing import Dict, Optional

from .parser import (
    DATE_HDR,
    MSG_LINE,
    is_wrapped_quote_open,
    normalize_date,
    strip_outer_quotes,
    ym_key,
)


def split_and_parse(
    input_path: str,
    out_dir: str,
    emit_json: bool = True,
    json_name: str = "messages.json",
) -> str:
    """
    入力ファイルを月別テキスト (YYYY-MM.txt) に分割し、
    オプションで messages.json を書き出す。

    Returns:
        JSON ファイルのパス（emit_json=False の場合は空文字列）。
    """
    os.makedirs(out_dir, exist_ok=True)
    month_handles: Dict[str, object] = {}

    def get_handle(month: str):
        if month not in month_handles:
            p = os.path.join(out_dir, f"{month}.txt")
            month_handles[month] = open(p, "w", encoding="utf-8", newline="\n")
        return month_handles[month]

    json_path = os.path.join(out_dir, json_name)
    jf = open(json_path, "w", encoding="utf-8") if emit_json else None
    first = True

    if jf:
        jf.write('{"messages": [\n')

    current_date_iso: Optional[str] = None
    current_month: Optional[str] = None
    collecting = False
    cur_msg: Optional[Dict[str, str]] = None

    def flush_msg():
        nonlocal cur_msg, collecting, first
        if cur_msg is None:
            return
        if (cur_msg["text"].startswith('"')
                and cur_msg["text"].count('"') >= 2
                and cur_msg["text"].endswith('"')):
            cur_msg["text"] = strip_outer_quotes(cur_msg["text"])
        if jf:
            if not first:
                jf.write(",\n")
            jf.write(json.dumps(cur_msg, ensure_ascii=False))
            first = False
        cur_msg = None
        collecting = False

    try:
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
                        "text": text,
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
    finally:
        if jf:
            jf.write("\n]}\n")
            jf.close()
        for h in month_handles.values():
            h.close()

    return json_path if emit_json else ""
