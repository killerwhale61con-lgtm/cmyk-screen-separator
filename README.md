# CMYK Screen Separator

写真からシルクスクリーン用のCMYK網点4版を作成する、Windows 11向けの無料・オープンソースツールです。GIMP 3を別途インストールして利用します。GIMPの公式製品ではありません。

## 配布方針

Microsoft Store版の申請準備を中止し、GitHub Releasesで配布するEXE版へ変更しました。利用者にStore開発者登録やアプリの審査は不要です。写真のサムネイル・拡大プレビュー、分解後の保存先指定を備えたWindows Forms画面を実装しています。

**0.3.0-betaは未署名の検証用ビルドです。2026-11-24にこの開発PCで通常起動を試しましたが、アプリケーション制御ポリシーによってブロックされました。起動問題は未解決です。** EXE化・GitHub公開だけではSmart App Controlの信頼は得られません。起動できる修正版として案内していません。Windowsの保護機能を無効にする手順は提供しません。

[GitHub版のビルド方法・使い方・制限](desktop/README.md) · [リリース一覧](https://github.com/killerwhale61con-lgtm/cmyk-screen-separator/releases)

Storeアプリ審査と署名用証明書の本人・組織確認は別です。広く信頼される署名には証明書または署名サービスの準備が残ります。署名の購入・申請はまだ行っていません。[Microsoft公式資料](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options)

## 機能

- JPEG/PNGのサムネイル一覧と拡大プレビュー
- A4・A3・任意の幅/高さmm、元画像・1:1・3:2・4:3・任意比率
- 白余白または中央切り抜き、DPIと出力ピクセル数の事前表示
- GIMP標準CMYK分解→各色の階調反転1回→新聞印刷（円形・周期7・角度45°・品質1）
- C.JPEG / M.JPEG / Y.JPEG / K.JPEGを白黒・最高品質・同寸法/DPIで個別保存
- 分解後の保存先選択、保存保留と再開、新規出力フォルダー、元画像を上書きしない

## 確認状況

従来のworker.pyはGIMP 3.2.8と3.0.0で処理試験を実施しています。新しいEXE版はコンパイル・ZIP整合性検証まで成功しましたが、このPCでは起動時にブロックされるため、新画面とGIMP連携の動作確認は完了していません。GIMPの手作業4版との比較・実印刷試験も未完了です。

旧0.2.0-betaのCMD版もSmart App Controlが有効な環境には未対応です。Store向けコードはstore/に保管していますが、Storeへの申請・公開は進めません。

## ライセンスとソース

GPL-3.0-or-later。LICENSEを参照してください。GitHub版ZIPには対応するソースとビルド用スクリプトを同梱します。GIMP本体、個人の写真、開発環境のランタイムは同梱しません。
