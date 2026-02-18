# ==========================================
# 3. 最適化計算の実行 (追記配置対応 + 制約条件)
# ==========================================

print("--- 🧠 最適化計算を開始します ---")

try:
    # --------------------------------------------------
    # 0. 既存配置データの読み込みとモード判定
    # --------------------------------------------------
    try:
        ws_allocated = wb.worksheet('O01_output_allocated_lessons')
        existing_data = ws_allocated.get_all_records()
        df_existing = pd.DataFrame(existing_data)

        if not df_existing.empty and 'slot_id' in df_existing.columns:
            print(f"ℹ️ 既存の配置データが見つかりました ({len(df_existing)} 件)。")
            print("   これらを【固定】して、残りの授業を配置します。")
            use_existing = True
        else:
            print("ℹ️ 既存の配置データはありません。新規に配置します。")
            use_existing = False
            df_existing = pd.DataFrame()
    except gspread.WorksheetNotFound:
        print("ℹ️ O01_output_allocated_lessons シートが見つかりません。新規に配置します。")
        use_existing = False
        df_existing = pd.DataFrame()

    # --------------------------------------------------
    # 1. 前処理
    # --------------------------------------------------
    slot_map = {row['id']: f"{row['date']} ({tr_map.get(row['time_range_id'], row['time_range_id'])})" for _, row in df_slots.iterrows()}

    # 指導可能辞書
    teachable_dict = collections.defaultdict(set)
    for _, row in df_teachable.iterrows():
        teachable_dict[row['teacher_id']].add(row['subject_id'])

    # 空き状況セット (Base Availability)
    student_avail_set = collections.defaultdict(set)
    for _, row in df_s_avail.iterrows():
        student_avail_set[row['student_id']].add(row['slot_id'])

    teacher_avail_set = collections.defaultdict(set)
    for _, row in df_t_avail.iterrows():
        teacher_avail_set[row['teacher_id']].add(row['slot_id'])

    # スロットのヘルパー構造
    slot_to_date = dict(zip(df_slots['id'], df_slots['date']))
    slot_to_tr = dict(zip(df_slots['id'], df_slots['time_range_id']))

    # 日付ごとのスロット一覧 (time_range_id昇順)
    slots_by_date = collections.defaultdict(list)
    for _, row in df_slots.iterrows():
        slots_by_date[row['date']].append((row['time_range_id'], row['id']))
    for date in slots_by_date:
        slots_by_date[date].sort()

    # --------------------------------------------------
    # 2. 既存配置によるリソース消費の反映
    # --------------------------------------------------
    student_busy_slots = collections.defaultdict(set)
    teacher_busy_slots = collections.defaultdict(set)

    existing_counts = collections.defaultdict(int)
    existing_teacher_counts = collections.defaultdict(int)
    existing_slot_counts = collections.defaultdict(int)

    if use_existing:
        for _, row in df_existing.iterrows():
            sid = row['student_id']
            tid = row['teacher_id']
            cid = row['subject_id']
            slid = row['slot_id']

            student_busy_slots[sid].add(slid)
            teacher_busy_slots[tid].add(slid)

            existing_counts[(sid, cid)] += 1
            existing_teacher_counts[(sid, cid, tid)] += 1
            existing_slot_counts[slid] += 1

    # --------------------------------------------------
    # 3. リクエスト情報の構築 (残りコマ数の計算)
    # --------------------------------------------------
    all_slots = df_slots['id'].tolist()
    all_teachers = df_teachers['id'].tolist()

    requests = []
    limit_constraints = {}

    for _, row in df_reqs.iterrows():
        sid = row['student_id']
        cid = row['subject_id']
        total_sessions = row['sessions']

        already_assigned = existing_counts[(sid, cid)]
        remaining_sessions = total_sessions - already_assigned

        if remaining_sessions <= 0:
            continue

        desired_teachers = []
        for i in range(1, 4):
            t_col = f'desired_teacher_{i}'
            limit_col = f'max_slot_{i}'

            if t_col in row and pd.notna(row[t_col]) and row[t_col] != '':
                tid = row[t_col]
                desired_teachers.append(tid)

                if limit_col in row and pd.notna(row[limit_col]) and row[limit_col] != '':
                    raw_limit = int(row[limit_col])
                    already_by_teacher = existing_teacher_counts[(sid, cid, tid)]
                    remaining_limit = max(0, raw_limit - already_by_teacher)
                    limit_constraints[(sid, cid, tid)] = remaining_limit
                else:
                    limit_constraints[(sid, cid, tid)] = remaining_sessions

        if not desired_teachers:
            desired_teachers = [t for t in all_teachers if cid in teachable_dict.get(t, set())]

        requests.append({
            'sid': sid,
            'cid': cid,
            'sessions': remaining_sessions,
            'allowed_teachers': desired_teachers
        })

    if not requests:
        print("🎉 全ての授業が既に配置済みです。計算を終了します。")
        raise Exception("新規に配置すべき授業がありませんでした。")

    # --------------------------------------------------
    # 4. 最適化モデル作成
    # --------------------------------------------------
    solver = pywraplp.Solver.CreateSolver('SCIP')
    solver.SetTimeLimit(30000)

    x = {}
    print(f"  残り {len(requests)} 件のリクエストについて変数を生成中...")

    for req in requests:
        sid, cid = req['sid'], req['cid']

        candidate_teachers = [t for t in req['allowed_teachers'] if cid in teachable_dict.get(t, set())]

        for tid in candidate_teachers:
            base_avail = student_avail_set[sid].intersection(teacher_avail_set[tid])

            real_avail = []
            for slid in base_avail:
                if (slid not in student_busy_slots[sid]) and (slid not in teacher_busy_slots[tid]):
                    real_avail.append(slid)

            limit = limit_constraints.get((sid, cid, tid), 999)
            if limit <= 0:
                continue

            for slid in real_avail:
                x[(sid, cid, tid, slid)] = solver.IntVar(0, 1, f'x_{sid}_{cid}_{tid}_{slid}')

    print(f"  -> 生成された変数数: {len(x)}")

    # ==============================================
    # 制約条件
    # ==============================================
    constraint_count = 0

    # --- 基本制約: 残りコマ数上限（合計） ---
    for req in requests:
        sid, cid, sessions = req['sid'], req['cid'], req['sessions']
        relevant_vars = [v for (s, c, t, sl), v in x.items() if s == sid and c == cid]
        if relevant_vars:
            solver.Add(solver.Sum(relevant_vars) <= sessions)
            constraint_count += 1

    # --- 基本制約: 講師ごとの残りコマ数上限 ---
    for (sid, cid, tid), limit in limit_constraints.items():
        relevant_vars = [v for (s, c, t, sl), v in x.items() if s == sid and c == cid and t == tid]
        if relevant_vars:
            solver.Add(solver.Sum(relevant_vars) <= limit)
            constraint_count += 1

    # --- 基本制約: 同時受講禁止（生徒は同一スロットに1つまで） ---
    for sid in s_map.keys():
        for slid in all_slots:
            vars_s = [v for (s, c, t, sl), v in x.items() if s == sid and sl == slid]
            if vars_s:
                solver.Add(solver.Sum(vars_s) <= 1)
                constraint_count += 1

    # --- 基本制約: 同時指導禁止（講師は同一スロットに1つまで） ---
    for tid in t_map.keys():
        for slid in all_slots:
            vars_t = [v for (s, c, t, sl), v in x.items() if t == tid and sl == slid]
            if vars_t:
                solver.Add(solver.Sum(vars_t) <= 1)
                constraint_count += 1

    print(f"  基本制約: {constraint_count} 件")

    # ==============================================
    # 追加制約（constraint シートで ON/OFF 制御）
    # すべてハード制約。配置数は目的関数で最大化する。
    # ==============================================
    extra_count = 0

    # 個人別設定のマッピング作成
    teacher_settings = {}
    for _, row in df_teachers.iterrows():
        teacher_settings[row['id']] = row.to_dict()

    student_settings = {}
    for _, row in df_students.iterrows():
        student_settings[row['id']] = row.to_dict()

    # --- 制約1: 講師の1日あたりの授業数上限（講師ごと） ---
    c1 = constraint_flags.get('max_teacher_daily_slot', {})
    if c1.get('activated'):
        for tid in t_map.keys():
            t_setting = teacher_settings.get(tid, {})
            val_raw = t_setting.get('max_daily_slot', '')
            if val_raw == '' or pd.isna(val_raw):
                continue
            val = int(val_raw)
            for date, tr_slots in slots_by_date.items():
                date_slot_ids = set(sl for _, sl in tr_slots)
                existing_count = sum(1 for sl in date_slot_ids if sl in teacher_busy_slots[tid])
                remaining = max(0, val - existing_count)
                vars_td = [v for (s, c, t, sl), v in x.items() if t == tid and sl in date_slot_ids]
                if vars_td:
                    solver.Add(solver.Sum(vars_td) <= remaining)
                    extra_count += 1
        print(f"  制約1 ON: 講師1日上限（個人別） (+{extra_count}件)")

    # --- 制約2: 生徒の連続コマ上限（生徒ごと） ---
    c2 = constraint_flags.get('max_student_continuous_slot', {})
    if c2.get('activated'):
        before = extra_count
        for sid in s_map.keys():
            s_setting = student_settings.get(sid, {})
            val_raw = s_setting.get('max_continuous_slot', '')
            if val_raw == '' or pd.isna(val_raw):
                continue
            val = int(val_raw)
            window_size = val + 1
            for date, tr_slots in slots_by_date.items():
                if len(tr_slots) < window_size:
                    continue
                for start in range(len(tr_slots) - window_size + 1):
                    window = tr_slots[start:start + window_size]
                    window_slot_ids = [sl for _, sl in window]
                    existing_in_window = sum(1 for sl in window_slot_ids if sl in student_busy_slots[sid])
                    remaining = max(0, val - existing_in_window)
                    vars_w = [v for (s, c, t, sl), v in x.items() if s == sid and sl in set(window_slot_ids)]
                    if vars_w:
                        solver.Add(solver.Sum(vars_w) <= remaining)
                        extra_count += 1
        print(f"  制約2 ON: 生徒連続上限（個人別） (+{extra_count - before}件)")

    # --- 制約3: 生徒の1日あたり上限コマ数（生徒ごと） ---
    c3 = constraint_flags.get('max_student_daily_slot', {})
    if c3.get('activated'):
        before = extra_count
        for sid in s_map.keys():
            s_setting = student_settings.get(sid, {})
            val_raw = s_setting.get('max_daily_slot', '')
            if val_raw == '' or pd.isna(val_raw):
                continue
            val = int(val_raw)
            for date, tr_slots in slots_by_date.items():
                date_slot_ids = set(sl for _, sl in tr_slots)
                existing_count = sum(1 for sl in date_slot_ids if sl in student_busy_slots[sid])
                remaining = max(0, val - existing_count)
                vars_sd = [v for (s, c, t, sl), v in x.items() if s == sid and sl in date_slot_ids]
                if vars_sd:
                    solver.Add(solver.Sum(vars_sd) <= remaining)
                    extra_count += 1
        print(f"  制約3 ON: 生徒1日上限（個人別） (+{extra_count - before}件)")

    # --- 制約4: 同一時限の上限コマ数（ブース上限） ---
    c4 = constraint_flags.get('max_lesson_per_timeslot', {})
    if c4.get('activated'):
        val = c4['value']
        before = extra_count
        for slid in all_slots:
            existing_count = existing_slot_counts[slid]
            remaining = max(0, val - existing_count)
            vars_slot = [v for (s, c, t, sl), v in x.items() if sl == slid]
            if vars_slot:
                solver.Add(solver.Sum(vars_slot) <= remaining)
                extra_count += 1
        print(f"  制約4 ON: 同一時限上限 {val}コマ (+{extra_count - before}件)")

    # --- 制約5: 講師の空きコマ上限数（講師ごと） ---
    c5 = constraint_flags.get('max_teacher_continuous_vacant_slot', {})
    if c5.get('activated'):
        before = extra_count
        c5_warnings = []
        for tid in t_map.keys():
            t_setting = teacher_settings.get(tid, {})
            val_raw = t_setting.get('max_continuous_vacant_slot', '')
            if val_raw == '' or pd.isna(val_raw):
                continue
            val = int(val_raw)
            for date, tr_slots in slots_by_date.items():
                n = len(tr_slots)
                for i in range(n):
                    for j in range(i + 1, n):
                        gap = j - i - 1
                        if gap <= val:
                            continue

                        slot_a = tr_slots[i][1]
                        slot_b = tr_slots[j][1]
                        intermediate_slots = [tr_slots[k][1] for k in range(i + 1, j)]
                        needed = gap - val

                        vars_a = [v for (s, c, t, sl), v in x.items() if t == tid and sl == slot_a]
                        vars_b = [v for (s, c, t, sl), v in x.items() if t == tid and sl == slot_b]
                        vars_inter = [v for (s, c, t, sl), v in x.items() if t == tid and sl in set(intermediate_slots)]

                        has_a = 1 if slot_a in teacher_busy_slots[tid] else 0
                        has_b = 1 if slot_b in teacher_busy_slots[tid] else 0
                        existing_inter = sum(1 for sl in intermediate_slots if sl in teacher_busy_slots[tid])

                        if has_a and has_b:
                            # 両端が既存配置（固定）の場合
                            remaining_needed = needed - existing_inter
                            if remaining_needed <= 0:
                                pass  # 既存配置で充足済み
                            elif vars_inter:
                                solver.Add(solver.Sum(vars_inter) >= remaining_needed)
                                extra_count += 1
                            else:
                                # 埋められるスロットがない → 制約追加をスキップ（既存データの問題）
                                c5_warnings.append(
                                    f"{t_map.get(tid)} {date}: 既存配置間の空きコマ({gap}コマ)が上限({val})を超えていますが、埋められる候補がありません"
                                )
                        elif has_a and vars_b:
                            solver.Add(solver.Sum(vars_inter) + existing_inter >= needed * solver.Sum(vars_b))
                            extra_count += 1
                        elif has_b and vars_a:
                            solver.Add(solver.Sum(vars_inter) + existing_inter >= needed * solver.Sum(vars_a))
                            extra_count += 1
                        elif vars_a and vars_b:
                            solver.Add(
                                solver.Sum(vars_inter) + existing_inter >=
                                needed * (solver.Sum(vars_a) + solver.Sum(vars_b) - 1)
                            )
                            extra_count += 1

        print(f"  制約5 ON: 講師空きコマ上限（個人別） (+{extra_count - before}件)")
        for w in c5_warnings:
            print(f"    ⚠️ {w}")

    print(f"  制約合計: {constraint_count + extra_count} 件")

    # 目的関数: 配置数を最大化
    objective = solver.Objective()
    for v in x.values():
        objective.SetCoefficient(v, 1)
    objective.SetMaximization()

    # 計算実行
    print("  計算中...")
    status = solver.Solve()

    if status in [pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE]:
        print("  ★ 計算完了（すべてのハード制約を満たしています）。")
        if use_existing:
            print("  既存データとマージします。")

        new_allocated = []
        new_counts = collections.defaultdict(int)

        for (sid, cid, tid, slid), v in x.items():
            if v.solution_value() > 0.5:
                new_allocated.append([
                    slid, sid, tid, cid,
                    slot_map.get(slid, str(slid)),
                    s_map.get(sid), t_map.get(tid), c_map.get(cid)
                ])
                new_counts[(sid, cid)] += 1
                student_busy_slots[sid].add(slid)
                teacher_busy_slots[tid].add(slid)

        df_new = pd.DataFrame(new_allocated, columns=['slot_id', 'student_id', 'teacher_id', 'subject_id', '日時', '生徒名', '講師名', '科目名'])
        df_final = pd.concat([df_existing, df_new], ignore_index=True)
        df_final = df_final.sort_values(['slot_id', 'student_id'])

        # 未配置検証
        unallocated = []
        total_counts = collections.defaultdict(int)

        for _, row in df_final.iterrows():
            total_counts[(row['student_id'], row['subject_id'])] += 1

        for _, row in df_reqs.iterrows():
            sid, cid, total_req = row['student_id'], row['subject_id'], row['sessions']
            current_total = total_counts[(sid, cid)]
            diff = total_req - current_total

            if diff > 0:
                if (sid, cid) not in [(req['sid'], req['cid']) for req in requests]:
                     msg = "要確認（データ不整合?）"
                else:
                     msg = "枠確保できず（制約による上限）"

                unallocated.append([sid, cid, diff, s_map.get(sid), c_map.get(cid), msg])

        un_columns = ['student_id', 'subject_id', '不足数', '生徒名', '科目名', '理由']
        if unallocated:
            df_un = pd.DataFrame(unallocated, columns=un_columns)
        else:
            df_un = pd.DataFrame(columns=un_columns)

        # 充足率レポート作成
        fulfillment_rows = []
        for _, row in df_reqs.iterrows():
            sid = row['student_id']
            cid = row['subject_id']
            requested = row['sessions']
            allocated = total_counts[(sid, cid)]
            rate = allocated / requested if requested > 0 else 0.0
            fulfillment_rows.append([
                sid, s_map.get(sid), cid, c_map.get(cid),
                requested, allocated, round(rate * 100, 1)
            ])

        df_fulfill = pd.DataFrame(fulfillment_rows, columns=[
            'student_id', '生徒名', 'subject_id', '科目名',
            '希望コマ数', '配置コマ数', '充足率(%)'
        ])
        df_fulfill = df_fulfill.sort_values(['student_id', 'subject_id'])

        print(f"\n✅ 最終結果: 全 {len(df_final)} コマ (うち新規 {len(df_new)} コマ)")
        display(df_final[['日時', '生徒名', '講師名', '科目名']].tail())

        if not df_un.empty:
            print(f"⚠️ 未配置: {len(df_un)} 件（制約を満たす範囲で最大限配置しました）")
            display(df_un)
        else:
            print("✅ 未配置なし: すべてのリクエストが配置されました。")

        # 充足率サマリー表示
        total_requested = df_fulfill['希望コマ数'].sum()
        total_allocated = df_fulfill['配置コマ数'].sum()
        overall_rate = round(total_allocated / total_requested * 100, 1) if total_requested > 0 else 0.0
        print(f"\n📊 充足率: {total_allocated}/{total_requested} コマ ({overall_rate}%)")
        display(df_fulfill)

        # シートへの書き込み
        import traceback

        def save_sheet(name, df):
            print(f"\n  --- save_sheet('{name}') 開始 ---")
            print(f"  DataFrame shape: {df.shape}")
            try:
                try:
                    ws = wb.worksheet(name)
                    print(f"  既存シート '{name}' を取得しました。")
                except Exception as e_ws:
                    print(f"  シート '{name}' が見つかりません。新規作成します。({e_ws})")
                    ws = wb.add_worksheet(name, 1000, 20)
                ws.clear()
                print(f"  シートをクリアしました。")
                data = [df.columns.values.tolist()] + df.values.tolist()
                print(f"  書き込みデータ: {len(data)} 行")
                ws.update(data)
                print(f"  ✅ シート '{name}' に保存完了。")
            except Exception as e:
                print(f"  ❌ 書き込みエラー({name}): {e}")
                traceback.print_exc()

        save_sheet('O01_output_allocated_lessons', df_final)
        save_sheet('O02_output_unallocated_lessons', df_un)
        save_sheet('O03_output_fulfillment', df_fulfill)

    else:
        status_names = {
            pywraplp.Solver.OPTIMAL: "OPTIMAL",
            pywraplp.Solver.FEASIBLE: "FEASIBLE",
            pywraplp.Solver.INFEASIBLE: "INFEASIBLE（解なし）",
            pywraplp.Solver.UNBOUNDED: "UNBOUNDED（非有界）",
            pywraplp.Solver.ABNORMAL: "ABNORMAL（ソルバー異常）",
            pywraplp.Solver.NOT_SOLVED: "NOT_SOLVED（未計算）",
        }
        print(f"\n❌ 計算できませんでした。")
        print(f"   ソルバーステータス: {status_names.get(status, f'不明({status})')}")
        print(f"   変数数: {len(x)}, 制約数: {constraint_count + extra_count}")

        # --- INFEASIBLE デバッグ情報 ---
        if status == pywraplp.Solver.INFEASIBLE:
            print(f"\n{'='*50}")
            print("🔍 INFEASIBLE 診断レポート")
            print(f"{'='*50}")

            # リクエストごとの配置可能性チェック
            print(f"\n📌 リクエスト別 配置可能性:")
            for req in requests:
                sid, cid, sessions = req['sid'], req['cid'], req['sessions']
                relevant_vars = [k for k in x.keys() if k[0] == sid and k[1] == cid]
                unique_slots = set(k[3] for k in relevant_vars)
                unique_teachers = set(k[2] for k in relevant_vars)
                status_icon = "✅" if len(unique_slots) >= sessions else "⚠️"
                print(f"  {status_icon} {s_map.get(sid)} x {c_map.get(cid)}: "
                      f"希望{sessions}コマ / 候補スロット{len(unique_slots)}個 / 候補講師{len(unique_teachers)}名")

            # リソース利用状況
            print(f"\n📌 リソース利用状況:")
            for tid in t_map.keys():
                t_vars = [k for k in x.keys() if k[2] == tid]
                t_slots = set(k[3] for k in t_vars)
                existing = len(teacher_busy_slots.get(tid, set()))
                print(f"  講師 {t_map.get(tid)}: 候補変数{len(t_vars)}個 / "
                      f"候補スロット{len(t_slots)}個 / 既存{existing}コマ")

            # 制約影響分析
            print(f"\n📌 有効な追加制約:")
            for code, flags in constraint_flags.items():
                if flags.get('activated'):
                    print(f"  ✅ {code}")
                else:
                    print(f"  ⬜ {code} (無効)")

            print(f"\n💡 対処法:")
            print(f"  1. 制約条件を一部OFFにして再実行してみてください")
            print(f"  2. 生徒・講師の空き枠を増やしてください")
            print(f"  3. 講師の指導可能科目を確認してください")
            print(f"  4. 制約5(空きコマ上限)が有効な場合、値を緩めてみてください")
            print(f"{'='*50}")

except Exception as e:
    import traceback
    print(f"\n❌ エラーまたは中断: {e}")
    traceback.print_exc()
