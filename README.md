# CMYK Screen Separator

写真をシルクスクリーン用のCMYK網点4版へ変換する、Windows 11向け無料ツールです。GIMP 3を利用する非公式アプリです。

## ダウンロード

[Windows用ZIP（0.2.0-beta）](https://github.com/killerwhale61con-lgtm/cmyk-screen-separator/releases/download/v0.2.0-beta/CMYK-Screen-Separator-0.2.0-beta-windows.zip) · [リリース一覧](https://github.com/killerwhale61con-lgtm/cmyk-screen-separator/releases)

GIMP 3が必要です。ZIPをすべて展開して「起動.cmd」を実行してください。

## インストールと起動

1. [公式GIMP 3](https://www.gimp.org/downloads/)をインストールします。
2. Windows用リリースZIPをすべて展開します。
3. `起動.cmd`または`Start.cmd`をダブルクリックします。

Pythonの追加インストールは不要です。Store版のみの場合は、初回に既存GIMPからローカル作業用コピーを準備します。配布ZIPにGIMP本体は含みません。

## 使い方

「画像を選ぶ」でサムネイル一覧と拡大プレビューから写真を選びます。用紙サイズ・画像比率・余白／中央切り抜き・DPIを設定し、表示されたピクセル寸法を確認して分解します。

初期設定では**分解後に保存先を選択**します。保存先選択をキャンセルしても4枚を保持し、再起動後も「保存先を選んで保存」から再開できます。保存先では新規サブフォルダーを作り、既存ファイルと元写真は上書きしません。

## 出力

- `C.JPEG` / `M.JPEG` / `Y.JPEG` / `K.JPEG`
- GIMP標準CMYK分解、各色の階調反転1回
- 新聞印刷：白地に黒、円形、周期7 px、角度45°、品質1
- JPEG品質100%、同じ寸法・DPI、グレースケール
- サイズ・切り抜き・余白は網点化前に適用

## 状態

**0.2.0-beta**。GIMP 3.2.8でサムネイル選択、分解後保存、保存保留・復元、保存失敗後の再試行、JPEG／PNG入力、寸法とDPIを検証しています。GIMPの手作業4版との完全一致比較と実印刷試験は未完了です。

詳しい条件・制限は[README.txt](README.txt)、検証項目は[TESTED.json](TESTED.json)を参照してください。

## ライセンスと公開

独自コードはGPL-3.0-or-later。ソースコードは配布ZIPに含まれます。[LICENSE](LICENSE)と[NOTICE](NOTICE)を参照してください。

`python tools/build_release.py`で公開用ZIPを生成できます。固定したファイル一覧だけを梱包し、写真・ログ・個人設定・GIMP本体を除外します。公開方法は[PUBLISHING.txt](PUBLISHING.txt)に記載しています。

