---
name: line-monthly-split
description: Google ドライブの「スマホから出力」フォルダにある最新の LINE トーク履歴（まつざわけ）を cli.py split で月別に分割し、隣の「月別分割 最新」フォルダへ未アップロード分だけを上げる。「トーク履歴を分割して」「月別分割を更新して」「NotebookLM 用に split して Drive に上げて」などの依頼で使う。
---

# LINE トーク履歴の月別分割 → Google ドライブ差分アップロード

## 守るルール

- **Drive 上の既存ファイルは上書き・削除・更新しない。** Drive は同名ファイルを重複作成できるので、「同名がなければ作成」を必ず守る。`update_file` / `trash_file` は使わない。
- 一番新しい月のファイルだけ、末尾に**実行日の日**を付ける（例: 9/13 実行 → `2026-08.txt`, `2026-09_13.txt`）。月途中の出力を区別するため。
- 匿名化はしない（ユーザーが求めた場合のみ別途）。
- ローカルの出力（`input/`, `splitted_matsuzawake_*`）は git commit しない。

## Drive の場所

両フォルダは同じ親フォルダ（`1WwWVA--weANdh5IQ55CyPSg3RgqFabzQ`）の下に並んでいる。ID は 2026-10 時点の値。見つからなければ `search_files` で `title = 'スマホから出力'` / `title = '月別分割 最新'` を検索し直す。

| フォルダ | ID |
|---|---|
| スマホから出力（入力） | `1K1ObKCdl53a_mDHzq8mFX8c_NBxSYYLH` |
| 月別分割 最新（出力） | `1LtdHXG1Nth_8hKzreT0X2IqiAI8A4eak` |

Drive ツールは Google Drive コネクタ（`search_files`, `download_file_content`, `create_file`）。遅延ロードなら ToolSearch でまとめて読み込む。

## 手順

### 1. 入力ファイルを特定する

`search_files` で `parentId = '<スマホから出力のID>'`。`.txt`（通常は `[LINE] まつざわけのトーク.txt`）が複数あれば `createdTime` が最新のものを使う。タイトルと作成日時をユーザーへの報告用に控える。

### 2. 出力フォルダの既存ファイル名を全件取る

`search_files` で `parentId = '<月別分割 最新のID>'`、`excludeContentSnippets: true`、`pageSize: 100`。
**`nextPageToken` が返る限り必ず次ページを取る**（100件超あり、1ページ目だけだと差分判定を誤る）。
全ページの `title` を1行1件でテキストファイルに書く（スクラッチパッドがあればそこ、なければ `input/drive_existing.txt`）。

### 3. 入力ファイルをダウンロードする

`download_file_content` に手順1のファイル ID を渡す。約1MB あるので結果はコンテキストに収まらず、
「Output has been saved to `<path>`」とファイルに退避される。その `<path>` を次で使う（中身は `{content: <base64>}` の JSON）。
退避ファイルを Read したり、中身を表示したりしない。

### 4. 分割と差分判定（スクリプト）

```bash
py -I .claude/skills/line-monthly-split/scripts/prepare.py --download-json "<手順3のpath>" --existing "<手順2のファイル>"
```

- この PC の Bash では `python3` は使えない。`py` を使う。
- スクリプトがやること: base64 デコード → スマホ版形式チェック → `input/matsuzawake_<保存日>.txt` に保存 →
  `.venv` の Python で `cli.py split` → 最新月を `YYYY-MM_DD.txt` に改名 → 既存一覧と突き合わせ。
- 出力の読み方:
  - `[NG] ...` → 中止してユーザーに伝える（PC版エクスポートなど）。
  - `[警告] 保存日時 ... と実行日 ... が異なります` → 今日のエクスポートがまだ Drive に上がっていない可能性が高い。アップロード前にユーザーに確認する。
  - `[警告] 最新月 ... が実行月 ... と異なります` → 月初でまだ今月のメッセージがない場合など。付けるファイル名をユーザーに確認する。
  - `UPLOAD<TAB>名前<TAB>バイト数<TAB>ローカルパス` → アップロード対象。1件もなければ終了。
- 出力先が既にあると `[NG]` で止まる（同日の再実行など）。`--out` で別の場所を指定する。

通常、対象は1〜2件になる: 今回の最新月（`_DD` 付き）と、前回まで月途中版（`2026-09_20.txt` など）しかなかった前月の確定版（`2026-09.txt`）。

### 5. アップロード

`UPLOAD` の各行について:

1. 直前にもう一度 `search_files` で `parentId = '<月別分割 最新のID>' and title = '<名前>'` を実行し、ヒットしたらスキップ（二重作成を防ぐ安全策）。
2. ローカルパスを Read し、**行番号を除いた本文そのまま**を `create_file` に渡す:
   - `title`: 名前、`parentId`: 月別分割 最新の ID
   - `textContent`: 本文、`contentMimeType`: `text/plain`
   - `disableConversionToGoogleType: true`（付けないと Google ドキュメントに変換される）
3. 返ってきた `fileSize` がスクリプトのバイト数と一致するか確認する。ずれたら本文の写し間違いなのでユーザーに報告する。

### 6. 報告

- 入力ファイル名と保存日時
- アップロードしたファイル（Drive のリンク付き）と、それぞれ上げた理由（最新月 / 前月の確定版など）
- スキップ件数（同名が既にあるため）
- ローカル出力先のパス
