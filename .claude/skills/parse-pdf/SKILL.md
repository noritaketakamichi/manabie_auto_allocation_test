---
name: parse-pdf
description: 校舎のPDFデータ（枠取表・講師カード）をCSVに変換する手順。新しい校舎のデータ作成時に使う。
disable-model-invocation: true
argument-hint: [校舎ディレクトリパス]
---

# PDF→CSV変換（校舎データ作成）

校舎ディレクトリ: $ARGUMENTS

## 前提条件

- **Python 3.11**（python3.13は cffi archエラーで pdfplumber が動かない）
- `pip install pdfplumber`

```bash
/usr/local/bin/python3.11 -m pip install pdfplumber
```

## 既存校舎のCSV生成

```bash
/usr/local/bin/python3.11 scripts/parse_pdfs.py samplePdfs/tamapura  # 約8分
```

出力先: `samplePdfs/tamapura/output/`

## 新しい校舎のデータ作成手順

1. `samplePdfs/<校舎名>/input/` に PDF を配置（`student.pdf`, `teacher.pdf`）
2. `scripts/parse_pdfs.py` の `PERIOD_START`, `PERIOD_END`, `TIME_SLOTS` 等を校舎に合わせて修正（または校舎用に設定ファイルを分離）
3. `/usr/local/bin/python3.11 scripts/parse_pdfs.py samplePdfs/<校舎名>` を実行
4. 生成されたCSVを `sample_sheet/` フォーマットと照合して検証

## PDFの構造

- **枠取表（student.pdf）**: 生徒ごと2ページ（12月+1月）。日付×時限グリッドに科目・講師名。右側にサマリ（予定回数・科目別回数）
- **講師カード（teacher.pdf）**: 講師ごと2ページ（12月+1月）。日付×時限グリッドに科目・生徒名
- グリッドレイアウト:
  - 生徒PDF: 上段=日付1-20、下段=日付21-31
  - 講師PDF: 上段=日付1-16、下段=日付17-31
- セル内レイアウト: 科目名が上、人名が下（y方向で分離）

## パース処理の要点

### pdfplumber ベース
- `page.extract_words()` でテキスト抽出、`page.curves` でマーク検出
- マーク: grey curves (fill < 0.8) = 休校日、white curves (fill >= 0.99) = 出席不可

### 科目名の処理
- **正規化**: `小学生`, `中学生`, `高校生` 等のプレフィックスを除去。`SPE`, `JE`, `一般`, `受験` は残す
- **ワードマージ**: pdfplumber が `数学Ⅲ` → `数学` + `Ⅲ` に分割する場合あり。同一セル内の隣接ワードを結合して対処
- **サマリ閾値**: `page_width * 0.56` より右がサマリ領域。科目名は x≈480 から始まる
- **プレフィックス切り詰め除去**: 講師PDF由来で `受験` のように切り詰められた科目名は、同名のより長い科目が存在し、かつ生徒サマリに無い場合に除去

### クロスリファレンス
- 講師PDFのセル幅が狭く科目名が切り詰められる問題を、生徒PDFの同一授業から正しい科目名を取得して解決
- ルックアップキー: `(講師名, 日付, 時限)` — 生徒グリッドの講師名は短縮名（姓のみ等）のため、プレフィックスマッチで正式名に変換
- **未解決の短縮名**: 同姓の講師が複数いる等で一意に解決できない短縮名（例: `野村`, `田中`, `鈴木`）は講師として登録せずスキップ。該当レッスンの講師情報は空になる

## トラブルシューティング

- **科目名が不正に結合される**: `extract_lessons_from_grid` のワードマージ条件（`x1-x0 < 5`, `top差 < 3`）を確認
- **科目が欠落する**: サマリ領域の閾値 `page_width * 0.56` が適切か確認。PDF のレイアウトが異なる場合は調整が必要
- **クロスリファレンスが 0 件**: 講師名のマッチングを確認。生徒グリッドの講師名が姓のみの場合、プレフィックスマッチで一意に解決できるか確認
