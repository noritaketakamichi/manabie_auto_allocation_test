# autoScheduling プロジェクト

TOMAS 個別指導塾の講習スケジュールを自動最適化するシステム。
生徒・講師・科目・時限の制約を満たしつつ、授業枠を自動配置する。

## ディレクトリ構成

```
autoScheduling/
├── GAS/gas.js                 # Google Apps Script（スプレッドシート連携）
├── colab/03_optimization.py   # 最適化エンジン（Google Colab用）
├── sample_sheet/              # サンプルCSV（フォーマット定義）
│   ├── I01_subject.csv        # 科目マスタ
│   ├── I02_time_range.csv     # 時限マスタ
│   ├── I03_student_list.csv   # 生徒リスト
│   ├── I04_teacher_list.csv   # 講師リスト
│   ├── I05_lesson_slot.csv    # 授業枠（日付×時限）
│   ├── I06_teachable_subjects.csv  # 講師担当科目
│   ├── I07_student_subject.csv     # 生徒受講科目（希望講師含む）
│   ├── I51_student_availability.csv # 生徒可用枠
│   ├── I52_teacher_availability.csv # 講師可用枠
│   ├── constraint.csv         # 制約条件
│   ├── O01_output_allocated_lessons.csv   # 出力: 配置済み授業
│   └── O02_output_unallocated_lessons.csv # 出力: 未配置授業
└── samplePdfs/                # 校舎別PDFデータ
    └── tamapura/              # たまプラーザ校
        ├── input/             # 元PDF（枠取表・講師カード）
        ├── output/            # 生成済みCSV
        └── parse_pdfs.py      # PDF→CSV変換スクリプト
```

## CSVフォーマット仕様

### 入力ファイル（I系）

| ファイル | ヘッダー | 説明 |
|---|---|---|
| I01_subject | id, subject_name | 科目マスタ |
| I02_time_range | id, description | 時限マスタ（S限,A限,B限,0限,1限,2限,3限,4限） |
| I03_student_list | id, student_name, max_continuous_slot, max_daily_slot | 生徒リスト+制約 |
| I04_teacher_list | id, teacher_name, max_daily_slot, max_continuous_vacant_slot | 講師リスト+制約 |
| I05_lesson_slot | id, date, time_range_id | 日付×時限の全組合せ |
| I06_teachable_subjects | teacher_id, subject_id | 講師が教えられる科目 |
| I07_student_subject | student_id, subject_id, sessions, desired_teacher_1, max_slot_1, desired_teacher_2, max_slot_2, desired_teacher_3, max_slot_3, max_daily_subject_slot | 受講科目・回数・希望講師・科目別1日上限 |
| I51_student_availability | student_id, slot_id | 生徒が出席可能な枠 |
| I52_teacher_availability | teacher_id, slot_id | 講師が出勤可能な枠 |
| constraint | code, description, activated, value | 制約条件 |

### 制約条件（constraint.csv）

| code | 説明 |
|---|---|
| max_teacher_daily_slot | 講師の1日あたり授業数上限（I04のmax_daily_slot参照） |
| max_student_continuous_slot | 生徒の連続コマ上限（I03のmax_continuous_slot参照） |
| max_student_daily_slot | 生徒の1日あたり上限コマ数（I03のmax_daily_slot参照） |
| max_lesson_per_timeslot | 同一時限の上限コマ数（ブース数制限） |
| max_teacher_continuous_vacant_slot | 講師の空きコマ上限数（I04参照） |
| max_student_subject_daily_slot | 生徒の科目ごとの1日受講コマ数上限（I07のmax_daily_subject_slot参照） |

### 出力ファイル（O系）は対象外

O01, O02 は最適化エンジンの出力。入力データ作成時は不要。

## 科目名の正規化

PDFでは科目名に `JE`, `小学生`, `中学生`, `高校生` などのプレフィックスが付く。
`normalize_subject()` 関数で除去。ただし `SPE` プレフィックスは残す仕様。
