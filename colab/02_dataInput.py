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
        # 生徒ごとの希望数集計
        req_summary = df_reqs.groupby('student_id')['sessions'].sum()
        print("  生徒名 | 希望コマ数合計")
        print("  -------|---------------")
        for sid, count in req_summary.items():
            print(f"  {s_map.get(sid, sid):<6} | {count} コマ")

        # 講師指定のチェック
        print("\n  [講師指定状況]")
        has_pref = False
        for _, row in df_reqs.iterrows():
            sid = row['student_id']
            cid = row['subject_id']
            # 指定があるか確認
            prefs = []
            for i in range(1, 4):
                col = f'desired_teacher_{i}'
                if col in row and pd.notna(row[col]) and row[col] != '':
                    prefs.append(t_map.get(row[col], str(row[col])))

            if prefs:
                has_pref = True
                print(f"  - {s_map.get(sid)} ({c_map.get(cid)}): {', '.join(prefs)}")

        if not has_pref:
            print("  (講師指定は見つかりませんでした。全講師対象として計算します)")

    else:
        print("  ⚠️ リクエストデータがありません。")

    # --- 2. 生徒の空き状況チェック ---
    print(f"\n📌 【生徒の空き状況】(student_availability)")
    if not df_s_avail.empty:
        s_avail_count = df_s_avail.groupby('student_id').size()
        print("  生徒名 | 空いているスロット数")
        print("  -------|---------------------")
        for sid, count in s_avail_count.items():
            print(f"  {s_map.get(sid, sid):<6} | {count} 箇所")

        # 警告: 希望数に対して空きが少なすぎる生徒
        print("  ---(チェック)---")
        for sid in req_summary.index:
            req = req_summary.get(sid, 0)
            avail = s_avail_count.get(sid, 0)
            if avail < req:
                print(f"  ⚠️ 注意: {s_map.get(sid)}さんは 希望{req}コマ に対し、空きが {avail}箇所 しかありません！（物理的に配置不可）")
            elif avail == 0:
                print(f"  ⚠️ 注意: {s_map.get(sid)}さんの空き情報が登録されていません。")
    else:
        print("  ⚠️ 生徒の空きデータが空です！GASで出力しましたか？")

    # --- 3. 講師の空き状況チェック ---
    print(f"\n📌 【講師の空き状況】")
    if not df_t_avail.empty:
        t_avail_count = df_t_avail.groupby('teacher_id').size()
        print(f"  登録講師数: {len(t_avail_count)} 名")
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
                value = int(row['value'])
            except (ValueError, TypeError):
                value = None
            constraint_flags[code] = {'activated': activated, 'value': value}
            if activated:
                active_list.append(row)
            else:
                inactive_list.append(row)

        print(f"\n  --- 有効な制約 ({len(active_list)} 件) ---")
        if active_list:
            print(f"  {'code':<40} | {'説明':<35} | 値の参照元")
            print(f"  {'-'*40}-+-{'-'*35}-+-----------")
            per_person = {'max_teacher_daily_slot', 'max_student_continuous_slot',
                          'max_student_daily_slot', 'max_teacher_continuous_vacant_slot'}
            for row in active_list:
                if row['code'] in per_person:
                    src = "個人別"
                else:
                    src = f"全体: {row['value']}"
                print(f"  {row['code']:<40} | {row['description']:<35} | {src}")
        else:
            print("  (なし)")

        print(f"\n  --- 無効な制約 ({len(inactive_list)} 件) ---")
        if inactive_list:
            for row in inactive_list:
                print(f"  ⬜ {row['code']} - {row['description']}")
        else:
            print("  (なし - すべて有効)")

        # 個人別制約の詳細表示
        if constraint_flags.get('max_teacher_daily_slot', {}).get('activated') or \
           constraint_flags.get('max_teacher_continuous_vacant_slot', {}).get('activated'):
            print(f"\n  [講師別の制約値]")
            print(f"  {'講師名':<12} | 1日上限 | 空きコマ上限")
            print(f"  {'-'*12}-+--------+------------")
            for _, row in df_teachers.iterrows():
                name = row['teacher_name']
                d = row.get('max_daily_slot', '-')
                v = row.get('max_continuous_vacant_slot', '-')
                print(f"  {name:<12} | {d:<6} | {v}")

        if constraint_flags.get('max_student_continuous_slot', {}).get('activated') or \
           constraint_flags.get('max_student_daily_slot', {}).get('activated'):
            print(f"\n  [生徒別の制約値]")
            print(f"  {'生徒名':<12} | 連続上限 | 1日上限")
            print(f"  {'-'*12}-+--------+--------")
            for _, row in df_students.iterrows():
                name = row['student_name']
                c = row.get('max_continuous_slot', '-')
                d = row.get('max_daily_slot', '-')
                print(f"  {name:<12} | {c:<6} | {d}")

    else:
        print("  ⚠️ 制約条件データがありません。デフォルト制約のみ適用します。")

    print("\n✅ データの確認が完了しました。")
    print("   問題なければ、次のセルで「最適化計算」を実行してください。")

except Exception as e:
    print(f"\n❌ エラーが発生しました: {e}")
