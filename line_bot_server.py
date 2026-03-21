from __future__ import annotations
import os, io
from datetime import datetime
import shutil
from pathlib import Path
from flask import Flask, request
from dotenv import load_dotenv
from linebot import WebhookHandler, LineBotApi
from linebot.models import MessageEvent, FileMessage, TextMessage, TextSendMessage
from linebot.exceptions import InvalidSignatureError
from openai import OpenAI

from water_server_be.services.ngrok_service import connect_http_tunnel, current_ngrok_public_url
from water_server_be.services.set_webhook_url import set_webhook_url

from line_core import split_and_parse, load_recent_messages, pick_last_incoming, render_context_block
from line_reply import (
    collect_evidence_snippets_generic,
    build_user_prompt,
    call_with_retries,
    safe_response_text,
)

load_dotenv()
app = Flask(__name__)
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
if not channel_access_token:
    raise SystemExit("LINE_CHANNEL_ACCESS_TOKEN is not set")
line_bot_api = LineBotApi(channel_access_token)

STATE = {}  # user_id -> {"input_dir": Path, "my_name": str, "custom_instruction": str}
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_INSTRUCTION = Path("custom_instruction.txt").read_text(encoding="utf-8", errors="ignore") if Path("custom_instruction.txt").exists() else ""
MY_NAME = os.getenv("MY_NAME")  # 自分の表示名（ログ内の自分と一致させる）
SYSTEM_INSTRUCTIONS = "あなたはLINEの返信案を作るアシスタントです。家族・友人向けに簡潔で誤解を避ける日本語の返信を返してください。"


def generate_reply_text(state: dict, custom_instruction: str) -> str:
    msgs = load_recent_messages(str(state["input_dir"]), months=2)
    if not msgs:
        return "ログが見つかりませんでした。"

    idx = pick_last_incoming(msgs, my_name=state["my_name"])
    if idx is None:
        return "相手からの直近メッセージが見つかりませんでした。"

    context_block = render_context_block(msgs, max(0, idx - 40), idx + 1)
    last_msg = msgs[idx]
    user_prompt = build_user_prompt(context_block, last_msg, custom_instruction, state["my_name"])

    client = OpenAI()
    resp = call_with_retries(client, model=MODEL, instructions=SYSTEM_INSTRUCTIONS, user_prompt=user_prompt)
    return safe_response_text(resp)

@app.post("/callback")
def callback():
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, request.headers["X-Line-Signature"])
    except InvalidSignatureError:
        return "invalid signature", 400
    return "OK"

@handler.add(MessageEvent, message=FileMessage)
def handle_file(event: MessageEvent):
    user_id = event.source.user_id
    content_resp = line_bot_api.get_message_content(event.message.id)
    data = io.BytesIO()
    for chunk in content_resp.iter_content():
        data.write(chunk)
    data.seek(0)

    # 保存先と分割先
    raw_dir = Path("input") / user_id
    if raw_dir.exists():
        shutil.rmtree(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{datetime.now():%Y%m%d_%H%M%S}_{event.message.file_name}"
    raw_path.write_bytes(data.read())

    split_dir = Path("splitted") / user_id
    if split_dir.exists():
        shutil.rmtree(split_dir)
    split_dir.mkdir(parents=True, exist_ok=True)
    split_and_parse(str(raw_path), str(split_dir), emit_json=True)

    profile = line_bot_api.get_profile(user_id)
    STATE[user_id] = {
        "input_dir": split_dir,
        "my_name": MY_NAME or profile.display_name,
        "custom_instruction": DEFAULT_INSTRUCTION,
    }

    reply_text = generate_reply_text(STATE[user_id], DEFAULT_INSTRUCTION)
    line_bot_api.reply_message(
        event.reply_token,
        [
            TextSendMessage(text="トーク履歴を受け取りました。準備ができました。"),
            TextSendMessage(text=reply_text),
        ],
    )

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event: MessageEvent):
    user_id = event.source.user_id
    state = STATE.get(user_id)
    if not state:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="先にトーク履歴のテキストを送ってください。"))
        return

    custom_instruction = event.message.text  # ユーザーからのメッセージをそのままカスタム指示として使用
    text = generate_reply_text(state, custom_instruction)
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=text))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    if os.getenv("USE_NGROK", "1") == "1":
        public_url = connect_http_tunnel(port)
        set_webhook_url(public_url)
    app.run(host="0.0.0.0", port=port)
