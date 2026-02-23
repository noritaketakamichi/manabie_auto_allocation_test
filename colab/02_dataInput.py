# ==========================================
# 2. データの読み込みと「診断レポート」表示
# ==========================================

# シート名の定義
sheet_names = {
    'subjects':       'I01_subject',
    'time_ranges':   'I02_time_range',
    'students':      'I03_student_list',
    'teachers':      'I04_teacher_list',
    'slots':         'I05_lesson_slot',
    'teachable':     'I06_teachable_subjects',
    'student_reqs':  'I07_student_subject',
    'student_avail': 'I51_student_availability',
    'teacher_avail': 'I52_teacher_availability',
    'constraints':   'constraint'
}

dfs = {}

print("--- 📥 データを読み込んでいます... ---")
try:
    for key, sheet_name in sheet_names.items():
        try:
            ws = wb.worksheet(sheet_name)
            data = ws.get_all_records()
            dfs[key] = pd.DataFrame(data)
            print(f"・{sheet_name}: {len(dfs[key])}行 読み込みOK")
        except gspread.WorksheetNotFound:
            print(f"⚠️ 警告: シート '{sheet_name}' が見つかりません！")
            dfs[key] = pd.DataFrame()

    # 変数展開
    df_subjects = dfs['subjects']
    df_time_ranges = dfs['time_ranges']
    df_students = dfs['students']
    df_teachers = dfs['teachers']
    df_slots = dfs['slots']
    df_teachable = dfs['teachable']
    df_reqs = dfs['student_reqs']
    df_s_avail = dfs['student_avail']
    df_t_avail = dfs['teacher_avail']
    df_constraints = dfs['constraints']

    # ID列の型を統一（gspreadはint/str混在になることがある）
    def to_int_col(df, col, fill=0):
        """数値列をintに変換。変換不可はfill値で埋める。"""
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(fill).astype(int)

    for df, cols in [
        (df_students, ['id']),
        (df_teachers, ['id']),
        (df_subjects, ['id']),
        (df_time_ranges, ['id']),
        (df_slots, ['id', 'time_range_id']),
        (df_teachable, ['teacher_id', 'subject_id']),
        (df_s_avail, ['student_id', 'slot_id']),
        (df_t_avail, ['teacher_id', 'slot_id']),
    ]:
        if not df.empty:
            for col in cols:
                if col in df.columns:
                    to_int_col(df, col)

    if not df_reqs.empty:
        for col in ['student_id', 'subject_id', 'sessions']:
            if col in df_reqs.columns:
                to_int_col(df_reqs, col)
        # desired_teacher_*, max_slot_* は空欄=NaNのまま残す（0にすると存在しない講師ID扱いになる）
        for i in range(1, 4):
            for prefix in ['desired_teacher_', 'max_slot_']:
                col = f'{prefix}{i}'
                if col in df_reqs.columns:
                    df_reqs[col] = pd.to_numeric(df_reqs[col], errors='coerce')
        # gspreadが返す空行を除去
        df_reqs = df_reqs[df_reqs['student_id'] != 0].reset_index(drop=True)

    # マッピング作成
    s_map = dict(zip(df_students['id'], df_students['student_name']))
    t_map = dict(zip(df_teachers['id'], df_teachers['teacher_name']))
    c_map = dict(zip(df_subjects['id'], df_subjects['subject_name']))
    tr_map = dict(zip(df_time_ranges['id'], df_time_ranges['description']))

    print("\n" + "="*40)
    print("📊 データ診断レポート")
    print("="*40)

    # --- 1. 生徒の授業希望チェック ---
    print(f"\n📌 【授業リクエスト】(全 {len(df_reqs)} 件)")
    if not df_reqs.empty:
        req_summary = df_reqs.groupby('student_id')['sessions'].sum()
        total_sessions = req_summary.sum()
        pref_count = sum(1 for _, row in df_reqs.iterrows()
                         if any(pd.notna(row.get(f'desired_teacher_{i}', '')) and row.get(f'desired_teacher_{i}', '') != ''
                                for i in range(1, 4)))
        print(f"  生徒数: {len(req_summary)}名 / 合計希望コマ数: {total_sessions} / 講師指定あり: {pref_count}件")
    else:
        print("  ⚠️ リクエストデータがありません。")

    # --- 2. 生徒の空き状況チェック ---
    print(f"\n📌 【生徒の空き状況】(student_availability)")
    if not df_s_avail.empty:
        s_avail_count = df_s_avail.groupby('student_id').size()
        print(f"  登録生徒数: {len(s_avail_count)}名 / 平均空きスロット: {s_avail_count.mean():.0f}箇所")

        # 警告: 希望数に対して空きが少なすぎる生徒のみ表示
        if not df_reqs.empty:
            warnings = []
            for sid in req_summary.index:
                req = req_summary.get(sid, 0)
                avail = s_avail_count.get(sid, 0)
                if avail < req:
                    warnings.append(f"  ⚠️ {s_map.get(sid)}: 希望{req}コマ に対し空き{avail}箇所（不足）")
                elif avail == 0:
                    warnings.append(f"  ⚠️ {s_map.get(sid)}: 空き情報が未登録")
            if warnings:
                print("  --- 警告 ---")
                for w in warnings:
                    print(w)
    else:
        print("  ⚠️ 生徒の空きデータが空です！GASで出力しましたか？")

    # --- 3. 講師の空き状況チェック ---
    print(f"\n📌 【講師の空き状況】")
    if not df_t_avail.empty:
        t_avail_count = df_t_avail.groupby('teacher_id').size()
        print(f"  登録講師数: {len(t_avail_count)}名 / 平均空きスロット: {t_avail_count.mean():.0f}箇所")
    else:
        print("  ⚠️ 講師の空きデータがありません。")

    # --- 4. 制約条件チェック ---
    print(f"\n📌 【制約条件】(全 {len(df_constraints)} 件)")
    constraint_flags = {}
    if not df_constraints.empty:
        active_list = []
        inactive_list = []
        for _, row in df_constraints.iterrows():
            code = row['code']
            activated = str(row['activated']).upper() == 'TRUE'
            try:
                value = float(row['value'])
            except (ValueError, TypeError):
                value = None
            constraint_flags[code] = {'activated': activated, 'value': value}
            if activated:
                active_list.append(row)
            else:
                inactive_list.append(row)

        per_person = {'max_teacher_daily_slot', 'max_student_continuous_slot',
                      'max_student_daily_slot', 'max_teacher_continuous_vacant_slot',
                      'max_student_subject_daily_slot'}
        soft_constraints = {'soft_spread_subject_across_days', 'soft_student_consecutive_slots'}
        print(f"  有効: {len(active_list)}件 / 無効: {len(inactive_list)}件")
        for row in active_list:
            if row['code'] in soft_constraints:
                src = f"ソフト制約: weight={row['value']}"
            elif row['code'] in per_person:
                src = "個人別"
            else:
                src = f"全体: {row['value']}"
            print(f"  ✅ {row['code']} ({src})")
        for row in inactive_list:
            print(f"  ⬜ {row['code']}")

    else:
        print("  ⚠️ 制約条件データがありません。デフォルト制約のみ適用します。")

    print("\n✅ データの確認が完了しました。")
    print("   問題なければ、次のセルで「最適化計算」を実行してください。")

except Exception as e:
    print(f"\n❌ エラーが発生しました: {e}")
