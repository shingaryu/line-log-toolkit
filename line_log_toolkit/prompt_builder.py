"""
prompt_builder.py — 生成 AI 向けプロンプトの作成

- ChatGPT に貼り付けるための前提テンプレート生成
- 返信案作成用のユーザープロンプト組み立て
- 意思決定モード用のプロンプト組み立て
"""

import os
from typing import List

from .parser import Msg


def write_prompt_template(
    out_dir: str,
    gdrive_folder: str,
    file_pattern: str,
    your_name: str,
    filename: str = "chatgpt_prompt_template.md",
) -> str:
    """別コンテキスト ChatGPT 用の前提テンプレートを生成する。"""
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


def build_user_prompt(
    context_block: str, last_msg: Msg, custom_instruction: str, my_name: str,
) -> str:
    """短文返信 (auto モード) 用のユーザープロンプトを組み立てる。"""
    return (
        "以下は家族LINEの直近のやり取りです。最後の相手メッセージに対する返信案を作ってください。\n\n"
        "【会話コンテキスト（古→新）】\n"
        f"{context_block}\n\n"
        "【今回の返信ターゲット】\n"
        f"{last_msg.date} {last_msg.time} {last_msg.sender}: {last_msg.text.replace(chr(10), ' ⏎ ')}\n\n"
        "【カスタム指示】\n"
        f"{custom_instruction}\n\n"
        "【出力要件】\n"
        f"- 送信者は「{my_name}」の口調で、日本語、LINEの会話らしい簡潔さ。\n"
        "- まず本命の返信案を1つ。その後に『別案』として2案まで箇条書き（任意）。\n"
        "- 相手の感情配慮／誤解を避ける言い回しを優先。不要な機密は書かない。\n"
        "- スタンプ提案が自然なら、末尾に《スタンプ案: …》を1つ（任意）。"
    )


def build_decision_prompt(
    context_block: str,
    last_msg: Msg,
    my_name: str,
    snippets: List[str],
    custom_instruction: str,
) -> str:
    """意思決定モード (decision) 用のユーザープロンプトを組み立てる。"""
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
        f"{last_msg.date} {last_msg.time} {last_msg.sender}: {(last_msg.text or '').replace(chr(10), ' ⏎ ')}\n\n"
        "【根拠候補スニペット】\n"
        f"{evidence}\n\n"
        f"【補助指示】\n{custom_instruction or '（特になし）'}\n"
    )
