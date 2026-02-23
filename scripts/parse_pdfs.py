#!/usr/local/bin/python3.11
"""
Parse TOMAS 枠取表 and 講師カード PDFs to generate scheduling input CSVs.

Uses pdfplumber to extract:
- Vector curves for availability marks (grey=closed, white=unavailable)
- Text for lessons (subject + person name) and summary data
"""

import re
import csv
import os
import sys
from collections import defaultdict
from datetime import date, timedelta

import pdfplumber

# ============================================================
# Configuration
# ============================================================
if len(sys.argv) < 2:
    print("Usage: python3.11 scripts/parse_pdfs.py <campus_dir>")
    print("Example: python3.11 scripts/parse_pdfs.py samplePdfs/tamapura")
    sys.exit(1)
BASE_DIR = os.path.abspath(sys.argv[1])
INPUT_DIR = os.path.join(BASE_DIR, "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

WAKUTORI_PDF = os.path.join(INPUT_DIR, "student.pdf")
KOUSHI_PDF = os.path.join(INPUT_DIR, "teacher.pdf")

PERIOD_START = date(2025, 12, 22)
PERIOD_END = date(2026, 1, 10)

TIME_SLOTS = ["S限", "A限", "B限", "0限", "1限", "2限", "3限", "4限"]

SUBJECT_KEYWORDS = r'(受験|算数|国語|英語|理科|社会|数学|物理|化学|生物|地理|歴史|古文|漢文|小論|作文|現代文|世界史|日本史|英検|SPE|一般)'

# Curve color thresholds
GREY_THRESHOLD = 0.8  # fill[0] < 0.8 → grey (closed)


# ============================================================
# Helpers
# ============================================================

def get_period_dates():
    dates = []
    d = PERIOD_START
    while d <= PERIOD_END:
        dates.append(d)
        d += timedelta(days=1)
    return dates


def normalize_subject(subj):
    """Normalize subject name by removing common prefixes and truncation marks."""
    subj = subj.strip()
    subj = re.sub(r'⋯$', '', subj)  # Remove midline ellipsis (PDF truncation)
    subj = re.sub(r'^(小学生|中学生|高校生|高校|中学)', '', subj)
    subj = re.sub(r'⋯$', '', subj)  # Remove again after prefix removal
    return subj


def resolve_truncated_subject(norm_subj, known_subjects):
    """Resolve a truncated subject name against known full names.

    If norm_subj is a prefix of exactly one known subject, return that.
    Otherwise return norm_subj as-is.
    """
    if norm_subj in known_subjects:
        return norm_subj
    # Try prefix matching
    matches = [ks for ks in known_subjects if ks.startswith(norm_subj) and ks != norm_subj]
    if len(matches) == 1:
        return matches[0]
    return norm_subj


def is_subject_text(text):
    """Check if text looks like a subject name."""
    return bool(re.search(SUBJECT_KEYWORDS, text))


# ============================================================
# Grid position extraction
# ============================================================

def extract_date_positions(words, y_min, y_max, date_min=1, date_max=31):
    """Extract date number → x-position mapping from words in a y-range."""
    positions = {}
    for w in words:
        if y_min < w['top'] < y_max and w['text'].isdigit():
            dnum = int(w['text'])
            if date_min <= dnum <= date_max:
                positions[dnum] = w['x0']
    return positions


def extract_slot_positions(words, y_min, y_max):
    """Extract time slot name → y-position mapping from words in a y-range."""
    positions = {}
    for w in words:
        if y_min < w['top'] < y_max:
            for ts in TIME_SLOTS:
                if w['text'] == ts:
                    positions[ts] = w['top']
    return positions


def find_nearest(val, positions, max_dist=25):
    """Find the nearest key in positions dict to a given value."""
    best = None
    best_d = float('inf')
    for name, pos in positions.items():
        d = abs(val - pos)
        if d < best_d:
            best_d = d
            best = name
    return best if best_d <= max_dist else None


# ============================================================
# Mark detection (curve analysis)
# ============================================================

def extract_marks(page, sections):
    """
    Extract cell marks from PDF page curves.

    Each curve is classified by fill color:
    - Grey (fill[0] < 0.8) → 'closed' (school closed)
    - White (fill[0] >= 0.99) → 'unavailable' (student/teacher can't attend)

    Args:
        page: pdfplumber page object
        sections: list of dicts with keys 'date_positions' and 'slot_positions'

    Returns:
        dict of {(date_num, slot_name): 'closed' | 'unavailable'}
        (cells not in the dict are 'available')
    """
    marks = {}

    for curve in page.curves:
        pts = curve.get('pts', [])
        if len(pts) < 4:
            continue

        fill = curve.get('non_stroking_color')
        if not fill or not isinstance(fill, tuple):
            continue

        # Classify by color
        if fill[0] < GREY_THRESHOLD:
            mark_type = 'closed'
        elif fill[0] >= 0.99:
            mark_type = 'unavailable'
        else:
            continue

        # Get curve center
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        cx = (min(xs) + max(xs)) / 2
        cy = (min(ys) + max(ys)) / 2

        # Try each section
        for section in sections:
            date_num = find_nearest(cx, section['date_positions'])
            slot_name = find_nearest(cy, section['slot_positions'])
            if date_num is not None and slot_name is not None:
                key = (date_num, slot_name)
                # closed takes priority over unavailable
                if key not in marks or mark_type == 'closed':
                    marks[key] = mark_type
                break

    return marks


# ============================================================
# Lesson text extraction
# ============================================================

def extract_lessons_from_grid(words, sections, month, max_x=None):
    """
    Extract lesson entries (subject + person name) from grid text.

    Pattern: subject text appears above person name at similar x position.
    Both are mapped to the nearest grid cell.

    Returns:
        list of {date, time_slot, subject, person}
    """
    if max_x is None:
        max_x = 900

    # Collect words mapped to grid cells
    raw_grid_items = []
    for w in words:
        # Skip header area and summary area
        if w['x0'] > max_x:
            continue
        for section in sections:
            date_num = find_nearest(w['x0'], section['date_positions'])
            slot_name = find_nearest(w['top'], section['slot_positions'])
            if date_num is not None and slot_name is not None:
                raw_grid_items.append({
                    'text': w['text'],
                    'x0': w['x0'],
                    'x1': w.get('x1', w['x0'] + 10),
                    'top': w['top'],
                    'bottom': w.get('bottom', w['top'] + 10),
                    'date_num': date_num,
                    'slot_name': slot_name,
                })
                break

    # Merge horizontally adjacent words on the same line within the same cell.
    # This handles cases where pdfplumber splits "数学Ⅲ" into "数学" + "Ⅲ"
    # or "英検" into "英" + "検" due to character spacing > x_tolerance.
    raw_grid_items.sort(key=lambda g: (g['date_num'], g['slot_name'], g['top'], g['x0']))
    grid_items = []
    for item in raw_grid_items:
        if (grid_items
                and grid_items[-1]['date_num'] == item['date_num']
                and grid_items[-1]['slot_name'] == item['slot_name']
                and abs(grid_items[-1]['top'] - item['top']) < 3
                and item['x0'] - grid_items[-1]['x1'] < 5):
            # Merge: append text, extend x1
            grid_items[-1]['text'] += item['text']
            grid_items[-1]['x1'] = item['x1']
        else:
            grid_items.append(dict(item))

    # Classify after merging
    for g in grid_items:
        g['is_subject'] = is_subject_text(g['text'])

    # Separate subjects and names
    subjects = [g for g in grid_items if g['is_subject']]
    names = [g for g in grid_items if not g['is_subject']
             and not g['text'].isdigit()
             and g['text'] not in ('月', '火', '水', '木', '金', '土', '日')
             and '予定' not in g['text']
             and '回' not in g['text']
             and '備考' not in g['text']
             and 'レギュラー' not in g['text']
             and len(g['text']) >= 2]

    # Match subjects with names in the same cell (same date, adjacent slot y)
    entries = []
    used_names = set()

    for subj in subjects:
        # Find name at similar x position, slightly below (within same cell)
        best_name = None
        best_dist = float('inf')
        for n_idx, name in enumerate(names):
            if n_idx in used_names:
                continue
            x_dist = abs(subj['x0'] - name['x0'])
            y_dist = name['top'] - subj['top']
            # Name should be below subject, within same cell (~10-15 px)
            if x_dist < 20 and 3 < y_dist < 20:
                dist = x_dist + y_dist
                if dist < best_dist:
                    best_dist = dist
                    best_name = (n_idx, name)

        year = 2025 if month == 12 else 2026
        try:
            full_date = date(year, month, subj['date_num'])
        except ValueError:
            continue
        if not (PERIOD_START <= full_date <= PERIOD_END):
            continue

        person = ''
        if best_name:
            used_names.add(best_name[0])
            person = re.sub(r'\s+', '', best_name[1]['text'])

        # Clean subject text
        subj_text = re.sub(r'\s*\d+/\d+回$', '', subj['text']).strip()
        if subj_text:
            entries.append({
                'date': full_date,
                'time_slot': subj['slot_name'],
                'subject': subj_text,
                'person': person
            })

    return entries


# ============================================================
# Header parsing
# ============================================================

def parse_student_header(words):
    """Extract student name, grade, and month from header words."""
    result = {'student_name': None, 'grade': None, 'month': None}

    # Sort header words by x position
    header_words = sorted(
        [w for w in words if w['top'] < 60],
        key=lambda w: w['x0']
    )
    header_text = ' '.join(w['text'] for w in header_words)

    m_month = re.search(r'(\d{1,2})月', header_text)
    if m_month:
        result['month'] = int(m_month.group(1))

    m_grade = re.search(r'学年\s+(\S+)', header_text)
    if m_grade:
        result['grade'] = m_grade.group(1)

    # Find name after 生徒氏名
    m_name = re.search(r'生徒氏名', header_text)
    if m_name:
        after = header_text[m_name.end():].strip()
        name_parts = after.split()
        if len(name_parts) >= 2:
            result['student_name'] = name_parts[0] + name_parts[1]
        elif len(name_parts) == 1:
            result['student_name'] = name_parts[0]

    return result


def parse_teacher_header(words):
    """Extract teacher name, ID, and month from header words."""
    result = {'teacher_name': None, 'teacher_id': None, 'month': None}

    header_words = sorted(
        [w for w in words if w['top'] < 70],
        key=lambda w: w['x0']
    )
    header_text = ' '.join(w['text'] for w in header_words)

    m_month = re.search(r'(\d{1,2})月', header_text)
    if m_month:
        result['month'] = int(m_month.group(1))

    m_id = re.search(r'講師番号\s+(\d+)', header_text)
    if m_id:
        result['teacher_id'] = m_id.group(1)

    m_name = re.search(r'講師氏名', header_text)
    if m_name:
        after = header_text[m_name.end():].strip()
        name_parts = after.split()
        if len(name_parts) >= 2:
            result['teacher_name'] = name_parts[0] + name_parts[1]
        elif len(name_parts) == 1:
            result['teacher_name'] = name_parts[0]

    return result


# ============================================================
# Summary parsing (student only)
# ============================================================

def parse_summary(words, page_width):
    """Extract 予定回数 and subject session counts from summary area."""
    total_sessions = 0
    subject_sessions = {}

    # Summary is typically on the right side (subject names start at x~480)
    summary_x_min = page_width * 0.56
    summary_words = sorted(
        [w for w in words if w['x0'] > summary_x_min],
        key=lambda w: w['top']
    )
    summary_text = ' '.join(w['text'] for w in summary_words)

    m_total = re.search(r'予定回数\s*(\d+)回', summary_text)
    if m_total:
        total_sessions = int(m_total.group(1))

    for m in re.finditer(r'(\S+?)\s+(\d+)/(\d+)回', summary_text):
        subj_name = m.group(1)
        planned = int(m.group(2))
        if is_subject_text(subj_name):
            subject_sessions[subj_name] = planned

    return total_sessions, subject_sessions


# ============================================================
# Page parsers
# ============================================================

def detect_sections_student(words):
    """Detect top and bottom grid sections for student PDF."""
    sections = []

    # Top section: dates at y~105, slots at y 130-315
    top_dates = extract_date_positions(words, 90, 120, 1, 20)
    top_slots = extract_slot_positions(words, 120, 320)
    if top_dates and top_slots:
        sections.append({
            'date_positions': top_dates,
            'slot_positions': top_slots,
            'label': 'top'
        })

    # Bottom section: dates at y~335, slots at y 360-555
    bottom_dates = extract_date_positions(words, 325, 355, 21, 31)
    bottom_slots = extract_slot_positions(words, 355, 560)
    if bottom_dates and bottom_slots:
        sections.append({
            'date_positions': bottom_dates,
            'slot_positions': bottom_slots,
            'label': 'bottom'
        })

    return sections


def detect_sections_teacher(words):
    """Detect top and bottom grid sections for teacher PDF."""
    sections = []

    # Top section: dates at y~94, slots at y 115-280
    top_dates = extract_date_positions(words, 80, 100, 1, 16)
    top_slots = extract_slot_positions(words, 110, 290)
    if top_dates and top_slots:
        sections.append({
            'date_positions': top_dates,
            'slot_positions': top_slots,
            'label': 'top'
        })

    # Bottom section: dates at y~296, slots at y 315-480
    bottom_dates = extract_date_positions(words, 285, 310, 17, 31)
    bottom_slots = extract_slot_positions(words, 310, 490)
    if bottom_dates and bottom_slots:
        sections.append({
            'date_positions': bottom_dates,
            'slot_positions': bottom_slots,
            'label': 'bottom'
        })

    return sections


def parse_student_page(page):
    """Parse a single student PDF page."""
    words = page.extract_words()
    if len(words) < 10:
        return None

    header = parse_student_header(words)
    if not header['student_name'] or not header['month']:
        return None

    sections = detect_sections_student(words)
    if not sections:
        return None

    marks = extract_marks(page, sections)
    lessons = extract_lessons_from_grid(words, sections, header['month'])
    total_sessions, subject_sessions = parse_summary(words, page.width)

    return {
        'student_name': header['student_name'],
        'grade': header['grade'],
        'month': header['month'],
        'marks': marks,
        'lessons': lessons,
        'total_sessions': total_sessions,
        'subject_sessions': subject_sessions
    }


def parse_teacher_page(page):
    """Parse a single teacher PDF page."""
    words = page.extract_words()
    if len(words) < 10:
        return None

    header = parse_teacher_header(words)
    if not header['teacher_name'] or not header['month']:
        return None

    sections = detect_sections_teacher(words)
    if not sections:
        return None

    marks = extract_marks(page, sections)
    lessons = extract_lessons_from_grid(words, sections, header['month'])

    return {
        'teacher_name': header['teacher_name'],
        'teacher_id': header['teacher_id'],
        'month': header['month'],
        'marks': marks,
        'lessons': lessons
    }


# ============================================================
# Closed days extraction
# ============================================================

def extract_closed_days(marks_dict, month):
    """Extract closed dates from marks (grey curves)."""
    closed_dates = set()
    year = 2025 if month == 12 else 2026
    for (date_num, slot_name), status in marks_dict.items():
        if status == 'closed':
            try:
                d = date(year, month, date_num)
                if PERIOD_START <= d <= PERIOD_END:
                    closed_dates.add(d)
            except ValueError:
                pass
    return closed_dates


# ============================================================
# Main
# ============================================================

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ---- Parse 枠取表 (Student Schedule) ----
    print("=" * 60)
    print("Parsing 枠取表 (Student Schedule)...")
    print("=" * 60)

    pdf_student = pdfplumber.open(WAKUTORI_PDF)
    total_student_pages = len(pdf_student.pages)
    print(f"Total pages: {total_student_pages}")

    students = {}
    closed_days = set()
    first_page_processed = False

    for p_idx in range(total_student_pages):
        if p_idx % 50 == 0:
            print(f"  Processing page {p_idx}/{total_student_pages}...")

        page = pdf_student.pages[p_idx]
        data = parse_student_page(page)
        if not data:
            continue

        name = data['student_name']

        # Extract closed days from the first valid page
        if not first_page_processed:
            for month_val in [12, 1]:
                if data['month'] == month_val:
                    closed_days |= extract_closed_days(data['marks'], month_val)
            first_page_processed = True
        else:
            # Also collect closed days from other pages to ensure completeness
            closed_days |= extract_closed_days(data['marks'], data['month'])

        if name not in students:
            students[name] = {
                'grade': data['grade'],
                'subject_sessions': {},
                'lessons': [],
                'marks': {}
            }

        # Merge subject sessions (take max)
        for subj, planned in data['subject_sessions'].items():
            if subj not in students[name]['subject_sessions']:
                students[name]['subject_sessions'][subj] = planned
            else:
                students[name]['subject_sessions'][subj] = max(
                    students[name]['subject_sessions'][subj], planned
                )

        # Merge lessons
        students[name]['lessons'].extend(data['lessons'])

        # Merge marks (convert date_num to full date)
        year = 2025 if data['month'] == 12 else 2026
        for (date_num, slot_name), status in data['marks'].items():
            try:
                full_date = date(year, data['month'], date_num)
            except ValueError:
                continue
            if PERIOD_START <= full_date <= PERIOD_END:
                key = (full_date, slot_name)
                if key not in students[name]['marks'] or status == 'closed':
                    students[name]['marks'][key] = status

    pdf_student.close()

    print(f"Found {len(students)} unique students")
    total_student_lessons = sum(len(s['lessons']) for s in students.values())
    print(f"Total lessons extracted from 枠取表: {total_student_lessons}")
    print(f"Closed days detected: {sorted(closed_days)}")

    # ---- Parse 講師カード (Teacher Schedule) ----
    print()
    print("=" * 60)
    print("Parsing 講師カード (Teacher Schedule)...")
    print("=" * 60)

    pdf_teacher = pdfplumber.open(KOUSHI_PDF)
    total_teacher_pages = len(pdf_teacher.pages)
    print(f"Total pages: {total_teacher_pages}")

    teachers = {}
    for p_idx in range(total_teacher_pages):
        if p_idx % 50 == 0:
            print(f"  Processing page {p_idx}/{total_teacher_pages}...")

        page = pdf_teacher.pages[p_idx]
        data = parse_teacher_page(page)
        if not data:
            continue

        name = data['teacher_name']

        # Also collect closed days from teacher pages
        closed_days |= extract_closed_days(data['marks'], data['month'])

        if name not in teachers:
            teachers[name] = {
                'teacher_id': data['teacher_id'],
                'lessons': [],
                'marks': {}
            }

        teachers[name]['lessons'].extend(data['lessons'])

        # Merge marks
        year = 2025 if data['month'] == 12 else 2026
        for (date_num, slot_name), status in data['marks'].items():
            try:
                full_date = date(year, data['month'], date_num)
            except ValueError:
                continue
            if PERIOD_START <= full_date <= PERIOD_END:
                key = (full_date, slot_name)
                if key not in teachers[name]['marks'] or status == 'closed':
                    teachers[name]['marks'][key] = status

    pdf_teacher.close()

    print(f"Found {len(teachers)} unique teachers")
    total_teacher_lessons = sum(len(t['lessons']) for t in teachers.values())
    print(f"Total lessons extracted from 講師カード: {total_teacher_lessons}")
    print(f"Final closed days: {sorted(closed_days)}")

    # ---- Cross-reference: resolve teacher lesson subjects ----
    # Student PDF has full subject names; teacher PDF may have truncated ones.
    # Build lookup from student lessons: (teacher_name, date, time_slot) -> subject
    # In student lessons, lesson['person'] = teacher name (from grid).
    student_lesson_lookup = {}
    for s_name, s_data in students.items():
        for lesson in s_data['lessons']:
            teacher_in_grid = lesson['person']
            if teacher_in_grid:
                key = (teacher_in_grid, lesson['date'], lesson['time_slot'])
                student_lesson_lookup[key] = lesson['subject']

    # Build short-name to full-name mapping for teachers.
    # Student grid cells are narrow and often show only last names (e.g., "三浦")
    # while teacher dict has full names (e.g., "三浦正俊").
    short_to_full = {}
    for full_name in teachers.keys():
        short_to_full[full_name] = full_name  # exact match
    # Also map by prefix: if a short name is a unique prefix of exactly one teacher
    # Compare with spaces removed to handle "岡ノ上" matching "岡ノ上 大樹(185897)"
    teacher_names_in_student_grid = set(k[0] for k in student_lesson_lookup.keys())
    for short_name in teacher_names_in_student_grid:
        if short_name in short_to_full:
            continue
        short_nospace = short_name.replace(' ', '').replace('\u3000', '')
        matches = [fn for fn in teachers.keys()
                   if fn.replace(' ', '').replace('\u3000', '').startswith(short_nospace)]
        if len(matches) == 1:
            short_to_full[short_name] = matches[0]

    # Rebuild lookup with normalized teacher names
    normalized_lookup = {}
    for (teacher_grid_name, d, ts), subj in student_lesson_lookup.items():
        full_name = short_to_full.get(teacher_grid_name)
        if full_name:
            normalized_lookup[(full_name, d, ts)] = subj

    resolved_count = 0
    for t_name, t_data in teachers.items():
        for lesson in t_data['lessons']:
            key = (t_name, lesson['date'], lesson['time_slot'])
            student_subject = normalized_lookup.get(key)
            if student_subject:
                if student_subject != lesson['subject']:
                    resolved_count += 1
                lesson['subject'] = student_subject

    print(f"Cross-reference: resolved {resolved_count} teacher lesson subjects from student PDF")

    # ---- Build derived data ----
    print()
    print("=" * 60)
    print("Building derived data...")
    print("=" * 60)

    # Collect all subjects
    all_subjects = set()
    for s_data in students.values():
        for subj in s_data['subject_sessions'].keys():
            all_subjects.add(normalize_subject(subj))
        for lesson in s_data['lessons']:
            all_subjects.add(normalize_subject(lesson['subject']))
    for t_data in teachers.values():
        for lesson in t_data['lessons']:
            all_subjects.add(normalize_subject(lesson['subject']))
    all_subjects.discard('')

    # Resolve truncated subjects (from PDF cell clipping)
    # First, separate clean subjects from truncated ones
    clean_subjects = {s for s in all_subjects if not s.endswith('⋯') and '⋯' not in s}
    truncated = {s for s in all_subjects if s.endswith('⋯') or '⋯' in s}
    if truncated:
        print(f"Truncated subjects found (will resolve): {sorted(truncated)}")
        for ts in truncated:
            resolved = resolve_truncated_subject(ts.replace('⋯', ''), clean_subjects)
            if resolved != ts.replace('⋯', ''):
                print(f"  '{ts}' → '{resolved}'")
        # Remove truncated subjects; they'll be resolved during lookup
        all_subjects = clean_subjects

    # Remove subjects that are strict prefixes of other subjects AND only appear
    # in teacher lessons (not in any student summary). These are truncated names
    # from narrow teacher PDF cells (e.g., "受験" when "受験国語" exists).
    # Student summaries have authoritative full subject names.
    student_summary_subjects = set()
    for s_data in students.values():
        for subj in s_data['subject_sessions'].keys():
            student_summary_subjects.add(normalize_subject(subj))
    prefix_truncated = set()
    for s in all_subjects:
        if s in student_summary_subjects:
            continue  # Present in student summary → valid subject
        longer = [o for o in all_subjects if o.startswith(s) and o != s]
        if longer:
            prefix_truncated.add(s)
    if prefix_truncated:
        print(f"Prefix-truncated subjects removed: {sorted(prefix_truncated)}")
        all_subjects -= prefix_truncated

    all_subjects = sorted(all_subjects)
    print(f"Subjects: {len(all_subjects)}: {all_subjects}")

    subject_id_map = {subj: i + 1 for i, subj in enumerate(all_subjects)}

    # Student IDs
    student_names = sorted(students.keys())
    student_id_map = {name: i + 1 for i, name in enumerate(student_names)}

    # Teacher IDs
    all_teacher_names = sorted(teachers.keys())
    teacher_id_map = {name: i + 1 for i, name in enumerate(all_teacher_names)}

    # Normalize student lesson person names using short_to_full mapping
    # This resolves short names (e.g., "岡ノ上") to full names (e.g., "岡ノ上大樹(185897)")
    normalized_person_count = 0
    for s_data in students.values():
        for lesson in s_data['lessons']:
            if lesson['person'] and lesson['person'] not in teacher_id_map:
                full_name = short_to_full.get(lesson['person'])
                if full_name and full_name in teacher_id_map:
                    lesson['person'] = full_name
                    normalized_person_count += 1
    if normalized_person_count:
        print(f"Normalized {normalized_person_count} student lesson person names to full teacher names")

    # Clear unresolved short names (e.g., "野村", "啓太") that couldn't be
    # matched to a full teacher name. These are ambiguous (multiple teachers
    # share the same surname) and should not be added as separate teachers.
    unresolved_names = set()
    for s_data in students.values():
        for lesson in s_data['lessons']:
            if lesson['person'] and lesson['person'] not in teacher_id_map:
                unresolved_names.add(lesson['person'])
                lesson['person'] = ''
    if unresolved_names:
        print(f"Unresolved teacher short names (cleared): {sorted(unresolved_names)}")

    print(f"Students: {len(student_id_map)}, Teachers: {len(teacher_id_map)}")

    # Period dates and lesson slots
    period_dates = get_period_dates()
    lesson_slots = []
    slot_lookup = {}
    slot_id = 1
    for d in period_dates:
        for ts_idx, ts in enumerate(TIME_SLOTS):
            lesson_slots.append({'id': slot_id, 'date': d, 'time_range_id': ts_idx + 1})
            slot_lookup[(d, ts)] = slot_id
            slot_id += 1
    print(f"Lesson slots: {len(lesson_slots)}")

    # Helper to resolve subject to ID
    def get_subject_id(raw_subject):
        norm = normalize_subject(raw_subject)
        sid = subject_id_map.get(norm)
        if sid is None:
            resolved = resolve_truncated_subject(norm, set(subject_id_map.keys()))
            sid = subject_id_map.get(resolved)
        return sid

    # Teachable subjects
    teachable_subjects = set()
    for t_name, t_data in teachers.items():
        t_id = teacher_id_map.get(t_name)
        if t_id is None:
            continue
        for lesson in t_data['lessons']:
            s_id = get_subject_id(lesson['subject'])
            if s_id:
                teachable_subjects.add((t_id, s_id))
    # Also from student schedules
    for s_data in students.values():
        for lesson in s_data['lessons']:
            if lesson['person']:
                t_id = teacher_id_map.get(lesson['person'])
                s_id = get_subject_id(lesson['subject'])
                if t_id and s_id:
                    teachable_subjects.add((t_id, s_id))
    print(f"Teachable subject pairs: {len(teachable_subjects)}")

    # Student-subject data
    student_subjects = []
    known_subj_set = set(subject_id_map.keys())
    for s_name, s_data in students.items():
        s_id = student_id_map[s_name]
        subject_teacher_count = defaultdict(lambda: defaultdict(int))
        for lesson in s_data['lessons']:
            norm_subj = normalize_subject(lesson['subject'])
            norm_subj = resolve_truncated_subject(norm_subj, known_subj_set)
            if lesson['person']:
                subject_teacher_count[norm_subj][lesson['person']] += 1

        processed = set()
        for raw_subj, sessions in s_data['subject_sessions'].items():
            norm_subj = normalize_subject(raw_subj)
            norm_subj = resolve_truncated_subject(norm_subj, known_subj_set)
            if norm_subj in processed:
                continue
            processed.add(norm_subj)
            if sessions <= 0:
                continue
            subj_id = subject_id_map.get(norm_subj)
            if not subj_id:
                continue

            teachers_ranked = sorted(
                subject_teacher_count.get(norm_subj, {}).items(),
                key=lambda x: -x[1]
            )
            entry = {
                'student_id': s_id, 'subject_id': subj_id, 'sessions': sessions,
                'desired_teacher_1': '', 'max_slot_1': '',
                'desired_teacher_2': '', 'max_slot_2': '',
                'desired_teacher_3': '', 'max_slot_3': ''
            }
            for rank, (t_name, count) in enumerate(teachers_ranked[:3]):
                t_id = teacher_id_map.get(t_name)
                if t_id:
                    entry[f'desired_teacher_{rank+1}'] = t_id
                    entry[f'max_slot_{rank+1}'] = count
            student_subjects.append(entry)

        # Handle subjects from lessons not in subject_sessions
        for norm_subj, tcounts in subject_teacher_count.items():
            if norm_subj in processed:
                continue
            subj_id = subject_id_map.get(norm_subj)
            if not subj_id:
                continue
            total_lessons = sum(tcounts.values())
            teachers_ranked = sorted(tcounts.items(), key=lambda x: -x[1])
            entry = {
                'student_id': s_id, 'subject_id': subj_id, 'sessions': total_lessons,
                'desired_teacher_1': '', 'max_slot_1': '',
                'desired_teacher_2': '', 'max_slot_2': '',
                'desired_teacher_3': '', 'max_slot_3': ''
            }
            for rank, (t_name, count) in enumerate(teachers_ranked[:3]):
                t_id = teacher_id_map.get(t_name)
                if t_id:
                    entry[f'desired_teacher_{rank+1}'] = t_id
                    entry[f'max_slot_{rank+1}'] = count
            student_subjects.append(entry)

    print(f"Student-subject entries: {len(student_subjects)}")

    # ---- Availability (mark-based) ----
    print()
    print("Building availability data from marks...")

    # Student availability: cells with no curve AND within period AND not closed
    student_availability = []
    for s_name in student_names:
        s_id = student_id_map[s_name]
        s_marks = students[s_name]['marks']
        for d in period_dates:
            if d in closed_days:
                continue
            for ts in TIME_SLOTS:
                key = (d, ts)
                status = s_marks.get(key)
                if status is None:  # No curve = available
                    sid = slot_lookup.get((d, ts))
                    if sid:
                        student_availability.append((s_id, sid))

    # Teacher availability: cells with no curve AND within period AND not closed
    teacher_availability = []
    for t_name in all_teacher_names:
        t_id = teacher_id_map[t_name]
        if t_name in teachers:
            t_marks = teachers[t_name]['marks']
        else:
            t_marks = {}
        for d in period_dates:
            if d in closed_days:
                continue
            for ts in TIME_SLOTS:
                key = (d, ts)
                status = t_marks.get(key)
                if status is None:  # No curve = available
                    sid = slot_lookup.get((d, ts))
                    if sid:
                        teacher_availability.append((t_id, sid))

    print(f"Student availability slots: {len(student_availability)}")
    print(f"Teacher availability slots: {len(teacher_availability)}")

    # ---- Write CSVs ----
    print()
    print("=" * 60)
    print("Writing CSV files...")
    print("=" * 60)

    def write_csv(filename, headers, rows):
        path = os.path.join(OUTPUT_DIR, filename)
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in rows:
                writer.writerow(row)
        print(f"  {filename}: {len(rows)} rows")

    write_csv('I01_subject.csv', ['id', 'subject_name'],
              [[sid, subj] for subj, sid in sorted(subject_id_map.items(), key=lambda x: x[1])])

    write_csv('I02_time_range.csv', ['id', 'description'],
              [[i + 1, ts] for i, ts in enumerate(TIME_SLOTS)])

    write_csv('I03_student_list.csv', ['id', 'student_name', 'max_continuous_slot', 'max_daily_slot'],
              [[student_id_map[n],
                f"{n}({students[n]['grade']})" if students[n].get('grade') else n,
                2, 3] for n in student_names])

    write_csv('I04_teacher_list.csv', ['id', 'teacher_name', 'max_daily_slot', 'max_continuous_vacant_slot'],
              [[teacher_id_map[n],
                f"{n}({teachers[n]['teacher_id']})" if n in teachers and teachers[n].get('teacher_id') else n,
                4, 1] for n in all_teacher_names])

    write_csv('I05_lesson_slot.csv', ['id', 'date', 'time_range_id'],
              [[s['id'], s['date'].isoformat(), s['time_range_id']] for s in lesson_slots])

    write_csv('I06_teachable_subjects.csv', ['teacher_id', 'subject_id'],
              sorted(teachable_subjects))

    write_csv('I07_student_subject.csv',
              ['student_id', 'subject_id', 'sessions',
               'desired_teacher_1', 'max_slot_1', 'desired_teacher_2', 'max_slot_2',
               'desired_teacher_3', 'max_slot_3'],
              [[e['student_id'], e['subject_id'], e['sessions'],
                e['desired_teacher_1'], e['max_slot_1'],
                e['desired_teacher_2'], e['max_slot_2'],
                e['desired_teacher_3'], e['max_slot_3']]
               for e in sorted(student_subjects, key=lambda x: (x['student_id'], x['subject_id']))])

    write_csv('I51_student_availability.csv', ['student_id', 'slot_id'],
              student_availability)

    write_csv('I52_teacher_availability.csv', ['teacher_id', 'slot_id'],
              teacher_availability)

    # constraint.csv
    path = os.path.join(OUTPUT_DIR, 'constraint.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['code', 'description', 'activated', 'value'])
        writer.writerow(['max_teacher_daily_slot', '講師の1日あたりの授業数上限定義', 'TRUE', ''])
        writer.writerow(['max_student_continuous_slot', '生徒の連続コマ上限定義', 'TRUE', ''])
        writer.writerow(['max_student_daily_slot', '生徒の1日あたり上限コマ数設定', 'TRUE', ''])
        writer.writerow(['max_lesson_per_timeslot', '同一時限の上限コマ数（ブース数に限りがあるため）', 'TRUE', 3])
        writer.writerow(['max_teacher_continuous_vacant_slot', '講師の空きコマ上限数（間空きすぎるのはNG）', 'TRUE', ''])
        writer.writerow(['max_student_subject_daily_slot', '生徒の科目ごとの1日受講コマ数上限（I07のmax_daily_subject_slot参照）', 'TRUE', ''])
        writer.writerow(['soft_spread_subject_across_days', '同じ科目は同じ日に固まらないほうがよい（ソフト制約）', 'TRUE', 0.1])
        writer.writerow(['soft_student_consecutive_slots', '生徒のコマはなるべく連続するようにする（ソフト制約）', 'TRUE', 0.05])
    print(f"  constraint.csv: written")

    # ---- Quality Validation ----
    print()
    print("=" * 60)
    print("Quality Validation")
    print("=" * 60)

    # 1. Closed days summary
    print(f"\n1. Closed days ({len(closed_days)} days):")
    for d in sorted(closed_days):
        weekday = ['月', '火', '水', '木', '金', '土', '日'][d.weekday()]
        print(f"   {d.isoformat()} ({weekday})")

    # 2. Lesson-availability consistency
    print(f"\n2. Lesson-availability consistency check:")
    inconsistencies = 0

    # Check student lessons
    for s_name, s_data in students.items():
        s_id = student_id_map[s_name]
        s_avail_set = set()
        for sa_s_id, sa_slot_id in student_availability:
            if sa_s_id == s_id:
                s_avail_set.add(sa_slot_id)

        for lesson in s_data['lessons']:
            sid = slot_lookup.get((lesson['date'], lesson['time_slot']))
            if sid and sid not in s_avail_set:
                print(f"   WARNING: Student {s_name} has lesson on {lesson['date']} {lesson['time_slot']} but is not available")
                inconsistencies += 1

    # Check teacher lessons
    teacher_avail_sets = defaultdict(set)
    for ta_t_id, ta_slot_id in teacher_availability:
        teacher_avail_sets[ta_t_id].add(ta_slot_id)

    for t_name, t_data in teachers.items():
        t_id = teacher_id_map[t_name]
        for lesson in t_data['lessons']:
            sid = slot_lookup.get((lesson['date'], lesson['time_slot']))
            if sid and sid not in teacher_avail_sets[t_id]:
                print(f"   WARNING: Teacher {t_name} has lesson on {lesson['date']} {lesson['time_slot']} but is not available")
                inconsistencies += 1

    if inconsistencies == 0:
        print("   OK - All lessons are on available slots")
    else:
        print(f"   {inconsistencies} inconsistencies found")

    # 3. Subject sessions match
    print(f"\n3. Subject sessions check:")
    session_mismatches = 0
    for s_name, s_data in students.items():
        for raw_subj, planned in s_data['subject_sessions'].items():
            norm = normalize_subject(raw_subj)
            found = False
            for entry in student_subjects:
                if entry['student_id'] == student_id_map[s_name]:
                    subj_name = [k for k, v in subject_id_map.items() if v == entry['subject_id']]
                    if subj_name and subj_name[0] == norm and entry['sessions'] == planned:
                        found = True
                        break
            if not found and planned > 0:
                session_mismatches += 1
    if session_mismatches == 0:
        print("   OK - All subject sessions match")
    else:
        print(f"   {session_mismatches} mismatches found")

    # 4. Summary
    print(f"\n4. Summary:")
    print(f"   Students: {len(students)}")
    print(f"   Teachers: {len(teachers)}")
    print(f"   Subjects: {len(all_subjects)}")
    print(f"   Student lessons: {total_student_lessons}")
    print(f"   Teacher lessons: {total_teacher_lessons}")
    print(f"   Closed days: {len(closed_days)}")

    # 5. Availability stats
    period_slots = len(period_dates) * len(TIME_SLOTS)
    closed_slots = len(closed_days) * len(TIME_SLOTS)
    open_slots = period_slots - closed_slots
    print(f"\n5. Availability stats:")
    print(f"   Period slots per person: {period_slots}")
    print(f"   Closed slots: {closed_slots}")
    print(f"   Open slots: {open_slots}")
    avg_student_avail = len(student_availability) / len(student_id_map) if student_id_map else 0
    avg_teacher_avail = len(teacher_availability) / len(teacher_id_map) if teacher_id_map else 0
    print(f"   Avg student available slots: {avg_student_avail:.1f} / {open_slots}")
    print(f"   Avg teacher available slots: {avg_teacher_avail:.1f} / {open_slots}")

    print()
    print("Done! Output files in:", OUTPUT_DIR)


if __name__ == '__main__':
    main()
