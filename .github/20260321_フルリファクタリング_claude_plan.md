このリポジトリ内のあらゆるソースファイルを、根本的に整理、リファクタリングしてほしい
私が考える基本設計方針はcopilot-instructions.md に記載した。下記は機能面、内部処理面での情報である。必要に応じて活用すること。

1. 私が今まで実行していた手順
1.1. launch.json内に以下2.と3.のスクリプト実行手順を記載した
1.2. inputフォルダ内に実際の入力ファイル(LINEから出力したトーク履歴)を置いてある
2. line_log_simple.pyにある機能について
2.1. このスクリプトの動作については私が別の生成AIにお願いしてREADME.mdに書いた
2.2. 別の生成AIのコンテキストと実際のスクリプトが異なる可能性がある
3. line_bot_server.pyについて
3.1. ChatGPT APIとLINE APIを使い、2で別々に実行していたような機能をスクリプト単体で提供するもの
3.2 line_bot_serverから参照しているwater_server_beモジュールのシンボルは、私が別用途で開発しているLine botアプリケーションから引用してきたもの
3.2.1. water serverは単にアプリケーションの名前である
3.2.2. poetryの機能を用いてこのリポジトリにかつてimportした記憶があるが、設定が途中のままになっている可能性がある
3.2.3 water serverのPublicなリポジトリは下記
3.2.4. https://github.com/shingaryu/water-server-be
