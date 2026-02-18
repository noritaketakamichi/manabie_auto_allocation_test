---
name: parse-pdf
description: 校舎のPDFデータ（枠取表・講師カード）をCSVに変換する手順。新しい校舎のデータ作成時に使う。
disable-model-invocation: true
argument-hint: [校舎名]
---

# PDF→CSV変換（校舎データ作成）

校舎名: $ARGUMENTS

## 前提条件

```bash
brew install poppler  # 初回のみ（pdftotext が必要）
```

## 既存校舎のCSV生成

```bash
cd samplePdfs/tamapura
python3 parse_pdfs.py  # 5〜10分
```

## 新しい校舎のデータ作成手順

1. `samplePdfs/$0/input/` にPDFを配置
2. `samplePdfs/tamapura/parse_pdfs.py` をコピーして `samplePdfs/$0/parse_pdfs.py` を作成
3. 以下を校舎に合わせて修正:
   - `WAKUTORI_PDF`, `KOUSHI_PDF` のファイルパス
   - `PERIOD_START`, `PERIOD_END` の期間
   - `TIME_SLOTS` の時限構成（校舎により異なる可能性）
   - `constraint.csv` の `max_lesson_per_timeslot`（ブース数）
4. `python3 parse_pdfs.py` を実行
5. 生成されたCSVを `sample_sheet/` フォーマットと照合して検証

## PDFの構造

- **枠取表**: 生徒ごと2ページ（12月+1月）。日付×時限グリッドに科目・講師名
- **講師カード**: 講師ごと2ページ（12月+1月）。日付×時限グリッドに科目・生徒名
- レイアウト: 科目名は時限ラベルの**前の行**、人名は時限ラベルの**同じ行**
