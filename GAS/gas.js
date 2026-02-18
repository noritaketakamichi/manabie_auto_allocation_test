/**
 * メニューを追加
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('⚡ 自動配置ツール')
    .addItem('👤 1. 生徒用：入力シートを作成', 'createStudentUI')
    .addItem('👤 2. 生徒用：データを保存', 'saveStudentData')
    .addSeparator()
    .addItem('🎓 3. 講師用：入力シートを作成', 'createTeacherUI')
    .addItem('🎓 4. 講師用：データを保存', 'saveTeacherData')
    .addSeparator()
    .addItem('📊 5. 結果をスケジュール表で表示', 'visualizeAllSchedules')
    .addSeparator()
    .addItem('🗑️ 6. 配置結果をリセット', 'resetAllocation')
    .addToUi();
}

// ==================================================
//  ラッパー関数
// ==================================================
function createStudentUI() { createMatrixSheet('I03_student_list', 'UI_Student_Input', '生徒名'); }
function saveStudentData() { saveMatrixData('UI_Student_Input', 'I51_student_availability', 'student_id'); }
function createTeacherUI() { createMatrixSheet('I04_teacher_list', 'UI_Teacher_Input', '講師名'); }
function saveTeacherData() { saveMatrixData('UI_Teacher_Input', 'I52_teacher_availability', 'teacher_id'); }

// ==================================================
//  共通処理（コアロジック）
// ==================================================

/**
 * 入力用シートを作成する関数
 * (列幅維持 ＆ 生徒/講師情報 ＆ 時間帯名称表示)
 */
function createMatrixSheet(listSheetName, uiSheetName, labelName) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheetSlots = ss.getSheetByName('I05_lesson_slot');
  const sheetList = ss.getSheetByName(listSheetName);
  const sheetTimeRange = ss.getSheetByName('I02_time_range');

  if (!sheetSlots || !sheetList) {
    Browser.msgBox(`エラー: シート '${listSheetName}' または 'I05_lesson_slot' が見つかりません。`);
    return;
  }

  // --------------------------------------------------
  // 0. 時間帯名称のマッピング作成 (ID -> Description)
  // --------------------------------------------------
  let trMap = new Map();
  if (sheetTimeRange && sheetTimeRange.getLastRow() > 1) {
    // id, description
    const trData = sheetTimeRange.getRange(2, 1, sheetTimeRange.getLastRow() - 1, 2).getValues();
    trData.forEach(r => trMap.set(r[0], r[1]));
  }

  // --------------------------------------------------
  // 1. 参照情報の取得 (生徒の希望 or 講師の指導可能科目)
  // --------------------------------------------------
  let refInfoMap = new Map();
  
  // 科目名マッピング
  const sheetCourse = ss.getSheetByName('I01_subject');
  let cMap = new Map();
  if (sheetCourse && sheetCourse.getLastRow() > 1) {
    const cData = sheetCourse.getRange(2, 1, sheetCourse.getLastRow() - 1, 2).getValues();
    cData.forEach(r => cMap.set(r[0], r[1]));
  }

  // 生徒用 (UI_Student_Input)
  if (uiSheetName === 'UI_Student_Input') {
    const sheetReq = ss.getSheetByName('I07_student_subject');
    if (sheetReq && sheetReq.getLastRow() > 1) {
      const rData = sheetReq.getRange(2, 1, sheetReq.getLastRow() - 1, 4).getValues();
      rData.forEach(r => {
        const sId = r[1];
        const cId = r[2];
        const sessions = r[3];
        const cName = cMap.get(cId) || `Course${cId}`;
        
        if (!refInfoMap.has(sId)) refInfoMap.set(sId, []);
        refInfoMap.get(sId).push(`${cName}:${sessions}`);
      });
    }
  }
  
  // 講師用 (UI_Teacher_Input)
  else if (uiSheetName === 'UI_Teacher_Input') {
    const sheetTeachable = ss.getSheetByName('I06_teachable_subjects');
    if (sheetTeachable && sheetTeachable.getLastRow() > 1) {
      const tData = sheetTeachable.getRange(2, 1, sheetTeachable.getLastRow() - 1, 2).getValues();
      tData.forEach(r => {
        const tId = r[0];
        const cId = r[1];
        const cName = cMap.get(cId) || `Course${cId}`;

        if (!refInfoMap.has(tId)) refInfoMap.set(tId, []);
        refInfoMap.get(tId).push(cName);
      });
    }
  }

  // --------------------------------------------------
  // 2. UIシートの準備
  // --------------------------------------------------
  let sheetUI = ss.getSheetByName(uiSheetName);
  let savedWidths = null;

  if (sheetUI) {
    const result = Browser.msgBox('確認', `シート "${uiSheetName}" を更新しますか？\n入力済みのデータ（チェックボックス）は消えますが、列幅は維持されます。`, Browser.Buttons.YES_NO);
    if (result == 'no') return;
    
    savedWidths = getColumnWidthsMap(sheetUI);
    sheetUI.clear();
  } else {
    sheetUI = ss.insertSheet(uiSheetName);
  }

  // --------------------------------------------------
  // 3. データ構築と書き込み
  // --------------------------------------------------
  const slotData = sheetSlots.getRange(2, 1, sheetSlots.getLastRow() - 1, 3).getValues();
  const listData = sheetList.getRange(2, 1, sheetList.getLastRow() - 1, 2).getValues();

  // ヘッダー（固定エリア）
  sheetUI.getRange(1, 1).setValue('id');
  sheetUI.getRange(1, 2).setValue('name');
  sheetUI.getRange(2, 1).setValue('ID(Hidden)');
  sheetUI.getRange(2, 2).setValue(labelName);

  // 列ヘッダー（スロット ＋ 時間名称）
  slotData.forEach((row, index) => {
    const colIndex = index + 3;
    const slotId = row[0];
    const dateStr = Utilities.formatDate(new Date(row[1]), Session.getScriptTimeZone(), "MM/dd");
    const timeId = row[2];
    
    // ★変更点：TimeRangeの名称を取得して表示
    const timeDesc = trMap.get(timeId) || `S${timeId}`; 
    const label = `${dateStr}\n${timeDesc}`;

    sheetUI.getRange(1, colIndex).setValue(slotId);
    sheetUI.getRange(2, colIndex).setValue(label);
  });

  // 行ヘッダー（人名 + 参照情報）
  listData.forEach((row, index) => {
    const rowIndex = index + 3;
    const personId = row[0];
    let displayName = row[1];

    if (refInfoMap.has(personId)) {
      const info = refInfoMap.get(personId).join(', ');
      displayName = `${displayName}\n[${info}]`;
    }

    sheetUI.getRange(rowIndex, 1).setValue(personId);
    sheetUI.getRange(rowIndex, 2).setValue(displayName);
  });

  // チェックボックス
  const lastRow = listData.length + 2;
  const lastCol = slotData.length + 2;
  if (listData.length > 0 && slotData.length > 0) {
    sheetUI.getRange(3, 3, listData.length, slotData.length).insertCheckboxes();
  }

  // --------------------------------------------------
  // 4. スタイル設定
  // --------------------------------------------------
  sheetUI.setFrozenRows(2);
  sheetUI.setFrozenColumns(2);
  sheetUI.hideRows(1);
  sheetUI.hideColumns(1);
  
  sheetUI.getRange(2, 1, 1, lastCol).setFontWeight('bold').setHorizontalAlignment('center');
  
  const nameColRange = sheetUI.getRange(3, 2, listData.length, 1);
  nameColRange.setWrapStrategy(SpreadsheetApp.WrapStrategy.WRAP);
  nameColRange.setVerticalAlignment("middle");

  if (savedWidths) {
    setColumnWidthsMap(sheetUI, savedWidths);
  } else {
    sheetUI.autoResizeColumns(2, lastCol - 1);
    sheetUI.setColumnWidth(2, 160);
  }
  
  Browser.msgBox(`完了: '${uiSheetName}' を更新しました。`);
}

/**
 * データを保存する関数（変更なし）
 */
function saveMatrixData(uiSheetName, outputSheetName, idColName) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheetUI = ss.getSheetByName(uiSheetName);
  
  if (!sheetUI) {
    Browser.msgBox(`エラー: 入力シート '${uiSheetName}' が見つかりません。`);
    return;
  }

  let sheetOutput = ss.getSheetByName(outputSheetName);
  if (!sheetOutput) sheetOutput = ss.insertSheet(outputSheetName);

  const lastRow = sheetUI.getLastRow();
  const lastCol = sheetUI.getLastColumn();

  if (lastRow < 3 || lastCol < 3) {
    Browser.msgBox("データが空のようです。");
    return;
  }

  const slotIds = sheetUI.getRange(1, 3, 1, lastCol - 2).getValues()[0];
  const dataRows = sheetUI.getRange(3, 1, lastRow - 2, lastCol).getValues();

  let outputData = [];
  dataRows.forEach(row => {
    const personId = row[0];
    for (let c = 2; c < row.length; c++) {
      if (row[c] === true) {
        outputData.push([personId, slotIds[c - 2]]);
      }
    }
  });

  sheetOutput.clear();
  sheetOutput.appendRow([idColName, 'slot_id']);
  if (outputData.length > 0) {
    sheetOutput.getRange(2, 1, outputData.length, 2).setValues(outputData);
    Browser.msgBox(`保存完了: ${outputData.length} 件を保存しました。`);
  } else {
    Browser.msgBox(`保存完了: データは空です。`);
  }
}

// ==================================================
//  可視化機能（列幅維持 ＆ 時間帯名称表示）
// ==================================================

function visualizeStudentSchedule() { visualizeScheduleFor('student'); }
function visualizeTeacherSchedule() { visualizeScheduleFor('teacher'); }
function visualizeAllSchedules() {
  visualizeScheduleFor('student');
  visualizeScheduleFor('teacher');
}

/**
 * スケジュール可視化の共通関数
 * @param {'student'|'teacher'} mode - 生徒 or 講師
 */
function visualizeScheduleFor(mode) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheetAllocated = ss.getSheetByName('O01_output_allocated_lessons');
  const sheetSlots = ss.getSheetByName('I05_lesson_slot');
  const sheetTimeRange = ss.getSheetByName('I02_time_range');

  const isStudent = (mode === 'student');
  const listSheetName = isStudent ? 'I03_student_list' : 'I04_teacher_list';
  const vizSheetName = isStudent ? 'Visualized_Student_Schedule' : 'Visualized_Teacher_Schedule';
  const idColName = isStudent ? 'student_id' : 'teacher_id';
  const labelName = isStudent ? '生徒名' : '講師名';

  const sheetList = ss.getSheetByName(listSheetName);

  if (!sheetAllocated || !sheetSlots || !sheetList) {
    Browser.msgBox(`エラー: 必要なシート（O01, I05, ${listSheetName}）が見つかりません。`);
    return;
  }

  // 時間帯名称マップ作成
  let trMap = new Map();
  if (sheetTimeRange && sheetTimeRange.getLastRow() > 1) {
    const trData = sheetTimeRange.getRange(2, 1, sheetTimeRange.getLastRow() - 1, 2).getValues();
    trData.forEach(r => trMap.set(r[0], r[1]));
  }

  let sheetViz = ss.getSheetByName(vizSheetName);
  let savedWidths = null;

  if (sheetViz) {
    savedWidths = getColumnWidthsMap(sheetViz);
    sheetViz.clear();
  } else {
    sheetViz = ss.insertSheet(vizSheetName);
  }

  // --- データ準備 ---
  const slotData = sheetSlots.getRange(2, 1, sheetSlots.getLastRow() - 1, 3).getValues();
  const listData = sheetList.getRange(2, 1, sheetList.getLastRow() - 1, 2).getValues();
  const allocValues = sheetAllocated.getDataRange().getValues();
  const allocHeader = allocValues[0];
  const allocData = allocValues.slice(1);

  const colIdx = {
    slot: allocHeader.indexOf('slot_id'),
    student: allocHeader.indexOf('student_id'),
    teacher: allocHeader.indexOf('teacher_id'),
    s_name: allocHeader.indexOf('生徒名'),
    t_name: allocHeader.indexOf('講師名'),
    c_name: allocHeader.indexOf('科目名')
  };

  if (colIdx.slot === -1) return;

  const slotMap = {}; slotData.forEach((row, i) => slotMap[row[0]] = i);
  const personMap = {}; listData.forEach((row, i) => personMap[row[0]] = i);

  // マトリクス作成
  const numRows = listData.length + 2;
  const numCols = slotData.length + 2;
  const outputMatrix = Array.from({length: numRows}, () => Array(numCols).fill(''));

  // ヘッダー
  outputMatrix[0][0] = idColName; outputMatrix[1][0] = 'ID';
  outputMatrix[0][1] = 'name'; outputMatrix[1][1] = labelName;

  slotData.forEach((row, i) => {
    const col = i + 2;
    const dateStr = Utilities.formatDate(new Date(row[1]), Session.getScriptTimeZone(), "MM/dd");
    const timeId = row[2];
    const timeDesc = trMap.get(timeId) || `S${timeId}`;
    outputMatrix[0][col] = row[0];
    outputMatrix[1][col] = `${dateStr}\n${timeDesc}`;
  });

  listData.forEach((row, i) => {
    const r = i + 2;
    outputMatrix[r][0] = row[0];
    outputMatrix[r][1] = row[1];
  });

  // データ埋め
  // 生徒用: セルに「【科目名】\n講師名」を表示
  // 講師用: セルに「【科目名】\n生徒名」を表示
  const personIdCol = isStudent ? colIdx.student : colIdx.teacher;
  allocData.forEach(row => {
    const personId = row[personIdCol];
    const slotId = row[colIdx.slot];
    const rIndex = personMap[personId];
    const cIndex = slotMap[slotId];
    if (rIndex !== undefined && cIndex !== undefined) {
      const courseName = row[colIdx.c_name];
      const counterpartName = isStudent ? row[colIdx.t_name] : row[colIdx.s_name];
      const cellText = `【${courseName}】\n${counterpartName}`;

      // 同じセルに複数の授業がある場合（講師が同時に複数生徒を持つケースなど）
      const existing = outputMatrix[rIndex + 2][cIndex + 2];
      outputMatrix[rIndex + 2][cIndex + 2] = existing ? `${existing}\n${cellText}` : cellText;
    }
  });

  // 書き込み
  sheetViz.getRange(1, 1, numRows, numCols).setValues(outputMatrix);

  // スタイル
  sheetViz.setFrozenRows(2);
  sheetViz.setFrozenColumns(2);
  sheetViz.hideRows(1);
  sheetViz.hideColumns(1);

  const dataRange = sheetViz.getRange(3, 3, numRows - 2, numCols - 2);
  dataRange.setWrapStrategy(SpreadsheetApp.WrapStrategy.WRAP);
  dataRange.setVerticalAlignment('middle');
  dataRange.setHorizontalAlignment('center');
  sheetViz.getRange(2, 2, numRows - 1, numCols - 1).setBorder(true, true, true, true, true, true);

  if (savedWidths) {
    setColumnWidthsMap(sheetViz, savedWidths);
  } else {
    sheetViz.autoResizeColumns(2, numCols - 1);
  }

  Browser.msgBox(`可視化完了: ${labelName}スケジュール表を更新しました。`);
}

// ==================================================
//  配置リセット機能
// ==================================================

/**
 * 配置結果（O01, O02）とスケジュール表をクリアする
 */
function resetAllocation() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  const result = Browser.msgBox(
    '⚠️ 配置リセット',
    '以下のシートのデータをすべて削除します。\n\n' +
    '・O01_output_allocated_lessons（配置結果）\n' +
    '・O02_output_unallocated_lessons（未配置リスト）\n' +
    '・O03_output_fulfillment（充足率）\n' +
    '・Visualized_Student_Schedule（生徒スケジュール表）\n' +
    '・Visualized_Teacher_Schedule（講師スケジュール表）\n\n' +
    'よろしいですか？',
    Browser.Buttons.YES_NO
  );

  if (result == 'no') return;

  const sheetsToReset = [
    { name: 'O01_output_allocated_lessons', headers: ['slot_id', 'student_id', 'teacher_id', 'subject_id', '日時', '生徒名', '講師名', '科目名'] },
    { name: 'O02_output_unallocated_lessons', headers: ['student_id', 'subject_id', '不足数', '生徒名', '科目名', '理由'] },
    { name: 'O03_output_fulfillment', headers: ['student_id', '生徒名', 'subject_id', '科目名', '希望コマ数', '配置コマ数', '充足率(%)'] }
  ];

  let resetCount = 0;

  sheetsToReset.forEach(({ name, headers }) => {
    const sheet = ss.getSheetByName(name);
    if (sheet) {
      sheet.clear();
      sheet.appendRow(headers);
      resetCount++;
    }
  });

  // スケジュール表はデータのみクリア
  ['Visualized_Student_Schedule', 'Visualized_Teacher_Schedule'].forEach(name => {
    const sheet = ss.getSheetByName(name);
    if (sheet) {
      sheet.clear();
      resetCount++;
    }
  });

  Browser.msgBox(`リセット完了: ${resetCount} シートをクリアしました。\n再度Colabから最適化を実行してください。`);
}

// ==================================================
//  ユーティリティ関数（列幅の保存・復元用）
// ==================================================

function getColumnWidthsMap(sheet) {
  const widths = {};
  const lastCol = sheet.getLastColumn();
  if (lastCol < 1) return null;
  
  for (let i = 1; i <= lastCol; i++) {
    widths[i] = sheet.getColumnWidth(i);
  }
  return widths;
}

function setColumnWidthsMap(sheet, widthsMap) {
  if (!widthsMap) return;
  const maxCol = sheet.getMaxColumns();
  
  for (const colIndexStr in widthsMap) {
    const colIndex = parseInt(colIndexStr);
    if (colIndex <= maxCol) {
      sheet.setColumnWidth(colIndex, widthsMap[colIndex]);
    }
  }
}