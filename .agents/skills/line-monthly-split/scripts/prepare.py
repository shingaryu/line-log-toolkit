"""Drive から落とした LINE トーク履歴を月別分割し、Drive へ上げるべきファイルを判定する。"""

import argparse
import base64
import binascii
import json
import re
import subprocess
import sys
import unicodedata
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[4]
MONTH_FILE = re.compile(r"\d{4}-\d{2}\.txt")
SAVED_AT = re.compile(r"保存日時：(\d{4})/(\d{2})/(\d{2}) (\d{2}:\d{2})")
MSG_LINE = re.compile(r"^\d{1,2}:\d{2}\t", re.M)


def fail(msg: str) -> None:
    print(f"[NG] {msg}")
    sys.exit(1)


def load_export(json_path: Path) -> bytes:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    content = data["content"]
    try:
        return base64.b64decode(re.sub(r"\s+", "", content), validate=True)
    except (binascii.Error, ValueError):
        return content.encode("utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--download-json", required=True, type=Path,
                    help="download_file_content の結果が保存された JSON ファイル")
    ap.add_argument("--existing", required=True, type=Path,
                    help="「月別分割 最新」の既存ファイル名一覧（1行1件）")
    ap.add_argument("--date", type=date.fromisoformat, default=date.today(),
                    help="実行日 YYYY-MM-DD（既定: 今日）。最新月の _DD に使う")
    ap.add_argument("--out", type=Path, default=None,
                    help="分割出力先（既定: <repo>/splitted_matsuzawake_<実行日>）")
    args = ap.parse_args()
    run_date: date = args.date

    raw = load_export(args.download_json)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        fail("入力が UTF-8 として読めません。Drive 上のファイルを確認してください")

    saved = SAVED_AT.search(text[:500])
    if not saved or not MSG_LINE.search(text):
        fail("スマホ版エクスポート形式（保存日時ヘッダ + タブ区切り）ではありません。"
             "PC版の可能性があります。スマホから出し直してもらってください")
    saved_date = date(int(saved[1]), int(saved[2]), int(saved[3]))

    input_path = REPO / "input" / f"matsuzawake_{saved_date:%Y%m%d}.txt"
    input_path.parent.mkdir(exist_ok=True)
    input_path.write_bytes(raw)
    print(f"[OK] 入力: {input_path} (保存日時 {saved[1]}/{saved[2]}/{saved[3]} {saved[4]})")

    out_dir = args.out or REPO / f"splitted_matsuzawake_{run_date:%Y%m%d}"
    if out_dir.exists() and any(out_dir.iterdir()):
        fail(f"出力先が既に存在し空ではありません: {out_dir} （--out で別の場所を指定）")

    venv_py = REPO / ".venv" / "Scripts" / "python.exe"
    r = subprocess.run(
        [str(venv_py), str(REPO / "cli.py"), "split",
         "--input", str(input_path), "--out", str(out_dir)],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        fail("split が失敗しました")

    months = sorted(p for p in out_dir.iterdir() if MONTH_FILE.fullmatch(p.name))
    if not months:
        fail("月別ファイルが1つも生成されませんでした（形式不一致の可能性）")
    print(f"[OK] 分割: {len(months)} か月分 ({months[0].stem} - {months[-1].stem})")

    latest = months[-1]
    dated = latest.with_name(f"{latest.stem}_{run_date:%d}.txt")
    latest.rename(dated)
    months[-1] = dated
    print(f"[OK] 最新月: {latest.name} -> {dated.name}")

    if saved_date != run_date:
        print(f"[警告] 保存日時 {saved_date} と実行日 {run_date} が異なります。"
              "最新のエクスポートがまだ Drive に上がっていない可能性があります")
    if latest.stem != f"{run_date:%Y-%m}":
        print(f"[警告] 最新月 {latest.stem} が実行月 {run_date:%Y-%m} と異なります。"
              f"{dated.name} という名前でよいかユーザーに確認してください")

    existing = {
        unicodedata.normalize("NFC", line.strip())
        for line in args.existing.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    }
    uploads = [p for p in months if p.name not in existing]
    skipped = len(months) - len(uploads)

    print(f"[OK] Drive に同名ありでスキップ: {skipped} 件")
    if not uploads:
        print("[OK] アップロード対象なし")
    for p in uploads:
        print(f"UPLOAD\t{p.name}\t{p.stat().st_size}\t{p}")


if __name__ == "__main__":
    main()
