"""
ai_client.py — OpenAI API ラッパー（リトライ制御・レスポンス抽出）
"""

import random
import time
from typing import List

from openai import APIConnectionError, OpenAI, RateLimitError, Timeout


def call_with_retries(
    client: OpenAI,
    model: str,
    instructions: str,
    user_prompt: str,
    max_output_tokens: int | None = None,
    max_retries: int = 6,
    base: float = 0.8,
    cap: float = 8.0,
):
    """
    OpenAI Responses API 呼び出し + 指数バックオフリトライ。

    - insufficient_quota は即座に中断（リトライ無意味）
    - 一時的な 429 / ネットワーク系はバックオフ再試行
    """
    tries = 0
    while True:
        try:
            kwargs = {
                "model": model,
                "instructions": instructions,
                "input": user_prompt,
            }
            if max_output_tokens is not None:
                kwargs["max_output_tokens"] = max_output_tokens
            return client.responses.create(**kwargs)
        except RateLimitError as e:
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

            if code == "insufficient_quota" or "insufficient_quota" in (msg or ""):
                raise SystemExit(
                    "OpenAI: APIの利用枠が尽きています（insufficient_quota）。"
                    "ダッシュボードで課金設定・月次予算・所属組織を確認してください。"
                )

            if tries >= max_retries:
                raise
            delay = min(cap, base * (2 ** tries)) + random.uniform(0, 0.25)
            time.sleep(delay)
            tries += 1

        except (APIConnectionError, Timeout):
            if tries >= max_retries:
                raise
            delay = min(cap, base * (2 ** tries)) + random.uniform(0, 0.25)
            time.sleep(delay)
            tries += 1


def safe_response_text(resp) -> str:
    """
    SDK バージョン差異に耐えるテキスト抽出。

    1. response.output_text（あれば）
    2. response.output 構造を辿って text を連結
    3. to_dict() 経由で best-effort
    """
    txt = getattr(resp, "output_text", None)
    if isinstance(txt, str) and txt.strip():
        return txt.strip()

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
        for path in [("output_text",), ("content",)]:
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
