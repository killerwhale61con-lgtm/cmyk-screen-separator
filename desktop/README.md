# GitHub版 0.3.0-beta（未署名・検証用）

Microsoft Storeへの申請・登録を行わず、GitHub Releasesで無料配布するWindows 11 x64用デスクトップアプリです。起動用CMDではなくCMYKScreenSeparator.exeを使用します。GIMP 3は別途必要です。PythonやGIMP本体を配布物に同梱しません。

**未署名のEXEです。Smart App Controlが有効なPCでは、旧版と同様に起動がブロックされる可能性があります。EXE化やGitHubへの公開だけでこの問題は解消しません。ブロックが解消した版としては公開しません。** セキュリティ機能を無効にしたり、ブロックされた実行ファイルを別の方法で実行したりする手順は案内していません。

公開にStoreのアプリ審査は不要です。一方、広く信頼される署名を付けるには、別途コード署名用の証明書や署名サービスが必要です。証明書の発行時の本人・組織確認と、アプリ公開審査は別です。現在、署名は未準備で、証明書や有料サービスの購入・申請はしていません。

## 起動と使い方

ZIPをすべて展開し、CMYKScreenSeparator.exeを起動します。GIMP 3が見つからない場合は、公式GIMPをインストールしてアプリを起動し直してください。

「写真を選ぶ」でフォルダー内のサムネイルと拡大画像を確認し、JPEG/PNGを選びます。用紙サイズ、画像の比率、余白/中央切り抜き、DPIを設定し、出力ピクセル数を確認します。「4色分解して書き出す」を押すと、GIMPを呼び出してC/M/Y/Kの4枚を作ります。

初期設定では分解後に保存先を指定します。キャンセル時も未保存の4枚を保持し、再起動後に「保存先を選んで保存」で再開します。既存ファイルと元写真を上書きしません。

## ビルド

開発用Python 3とWindows 11に含まれる.NET Frameworkコンパイラーで作成できます。

`python desktop/build_portable.py --output 新しい出力フォルダー`

UIの共通ソースはstore/srcにありますが、GitHub版にはStoreのアプリID、MSIX、Store登録を必要としません。通常版GIMPは直接バッチ起動し、Store版GIMPは正式なWindowsアプリ起動APIを使います。Store版GIMPのAPI経由のバッチ実行は未確認です。

ZIPにはEXE、GIMP内で実行するworker.py、GPLライセンス、対応するビルド用ソースを含めます。ソース改変・再配布はGPL-3.0-or-laterに従って行えます。

## 確認範囲

2026-11-24：Windows 11実機で通常のEXE起動を試し、「アプリケーション制御ポリシーによってこのファイルがブロックされました」となりました。このPCでの起動不具合は未解決です。

ビルド結果・署名状態・配布物の整合性はBUILD-REPORT.jsonに記録します。コンパイル成功を起動成功として扱いません。新しいWindows Forms画面、GIMP連携、インターネットからのダウンロード後の起動は実機確認が必要です。従来のworker.pyの処理試験は、新画面の動作確認を意味しません。GIMPで手作業した4版との比較と実印刷試験も未完了です。

公式資料：
- https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options
- https://learn.microsoft.com/en-us/windows/security/application-security/application-control/smart-app-control
