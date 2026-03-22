"""
snippets.py — messages.json からキーワードヒット前後のスニペットを Markdown で出力する
"""

import json
import os
from typing import List


def make_snippets(json_path: str, out_dir: str, keywords: List[str], window: int = 2) -> str:
    """
    JSON からキーワードにマッチするメッセージ前後を抽出し、
    snippet_pack.md として書き出す。

    Returns:
        出力ファイルのパス。
    """
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
            hit_kws = [kw for kw in keywords if kw in (m.get("text") or "")]
            w.write(f"## {m.get('date')} {m.get('time')} 〔hit: {'/'.join(hit_kws)}〕\n\n")
            start = max(0, idx - window)
            end = min(len(msgs) - 1, idx + window)
            for j in range(start, end + 1):
                mj = msgs[j]
                line = (mj.get("text") or "").replace("\r", " ").replace("\n", " ⏎ ")
                w.write(f"- {mj.get('date')} {mj.get('time')} {mj.get('sender')}: {line}\n")
            w.write("\n")
    return out_md
