# Microsoft Store版（開発中）

0.3.0.0は、起動用CMDを使わない.NET Framework 4.8 / Windows Formsの専用画面です。写真のサムネイル一覧と拡大表示、分解後の保存先選択、保存保留と再開を実装しています。GIMP本体は同梱しません。Store版GIMPはWindowsのIApplicationActivationManagerで起動し、既存worker.pyをGIMPのPythonバッチで実行します。

## 現在の確認範囲

- C#コンパイル成功。
- Microsoft Windows SDK MakeAppxの通常のマニフェスト検証とMSIX作成に成功（検証省略なし）。
- パッケージ展開成功。CMD/BAT/PowerShellの起動スクリプト、GIMPランタイムを含まないことを確認。
- worker.pyは従来のGIMP処理と同一。従来の処理試験と新画面の動作確認は別です。
- 新画面の起動、Store版GIMPの正式API経由のバッチ起動、Store署名後のSmart App Control環境での実行、手作業4版との比較は未確認です。

仮IDのMSIXは未署名・未公開です。利用者用インストーラーではありません。自己署名証明書のインストールやWindowsの保護設定変更は行いません。

## 正式な提出まで

1. https://storedeveloper.microsoft.com/ から個人開発者として登録。本人確認・規約同意は公開者本人が行います。
2. Partner CenterでWindowsアプリの名前を予約します。GIMPの公式アプリと誤認されない名前にします。候補：CMYK網点4色分解。
3. 製品IDページのPackage/Identity/Name、Package/Identity/Publisher、Package/Properties/PublisherDisplayNameを取得します。これらは公開パッケージ用識別子です。パスワード・秘密鍵・本人確認書類をソースやチャットへ保存しません。
4. StoreIdentity.example.jsonを別名コピーし、上記3項目と正式なDisplayNameを記入します。
5. 開発用PythonとMicrosoft Windows SDKを使い、build_msix.py --identity 正式ID.json --sdk SDKフォルダー --output 新しい出力フォルダー を実行します。仮IDを使う構造確認に限り --preview が必要です。
6. 正式IDでパッケージを提出し、Store署名済みの非公開配布等で新画面・GIMP連携・JPEG出力を実機確認します。審査メモに外部GIMP依存とrunFullTrustの用途を記載します。
7. 動作確認用スクリーンショット、年齢区分、価格「無料」、説明、サポートURL、プライバシーポリシーを確認してから公開します。

アカウント登録・名前予約は未完了です。Storeの審査通過や公開日は保証できません。MSIXのMicrosoft署名は認定後に行われます。

## 公開前の実機確認

Store署名済み版をWindows 11へインストールし、起動、写真の選択とプレビュー、300/600/1200 DPI・カスタム、余白/切り抜き、Store版GIMPでの4色処理、保存キャンセル→再起動→再保存、権限のない保存先からの再試行、既存ファイルと元画像の不変を確認します。同じ設定のGIMP手作業版と4色の順序、反転方向、円形・周期7・角度45・品質1を比較します。C/M/Y/KのJPEGを寸法・JFIF DPI・白黒・最高品質まで検査します。

公式資料：
- https://learn.microsoft.com/en-us/windows/apps/publish/partner-center/open-a-developer-account?tabs=individual
- https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options
- https://learn.microsoft.com/en-us/windows/msix/desktop/desktop-to-uwp-manual-conversion

