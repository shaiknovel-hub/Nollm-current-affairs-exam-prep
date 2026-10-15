"""
Auto-seeds the SQLite database from claude_questions.txt when the DB is empty.
Called by init_db() so Streamlit Cloud always has questions ready.
"""

import re
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_FILE = ROOT / "claude_questions.txt"

TOPIC_MAP = {
    "agriculture": "Environment, Ecology & Agriculture",
    "agriculture and trade": "Environment, Ecology & Agriculture",
    "appointments": "Appointments, Resignations & Committees",
    "appointments and committees": "Appointments, Resignations & Committees",
    "awards": "Awards, Honors & Rankings",
    "awards and business": "Awards, Honors & Rankings",
    "awards and culture": "Awards, Honors & Rankings",
    "awards and recognitions": "Awards, Honors & Rankings",
    "banking": "Economy, Banking & Finance",
    "banking and economy": "Economy, Banking & Finance",
    "banking and finance": "Economy, Banking & Finance",
    "business": "Economy, Banking & Finance",
    "business and economy": "Economy, Banking & Finance",
    "defence": "Defence, Exercises & Security",
    "defence and security": "Defence, Exercises & Security",
    "economy": "Economy, Banking & Finance",
    "economy and business": "Economy, Banking & Finance",
    "economy and finance": "Economy, Banking & Finance",
    "education": "Science, Technology & Space",
    "education and technology": "Science, Technology & Space",
    "environment": "Environment, Ecology & Agriculture",
    "environment and ecology": "Environment, Ecology & Agriculture",
    "environment and climate": "Environment, Ecology & Agriculture",
    "finance": "Economy, Banking & Finance",
    "governance": "National Affairs & Governance",
    "government": "National Affairs & Governance",
    "government schemes": "Government Schemes & Initiatives",
    "government schemes and initiatives": "Government Schemes & Initiatives",
    "health": "National Affairs & Governance",
    "heritage": "Awards, Honors & Rankings",
    "india and world": "International Affairs & Summits",
    "infrastructure": "National Affairs & Governance",
    "international": "International Affairs & Summits",
    "international affairs": "International Affairs & Summits",
    "international affairs and summits": "International Affairs & Summits",
    "law": "National Affairs & Governance",
    "national": "National Affairs & Governance",
    "national affairs": "National Affairs & Governance",
    "national affairs and governance": "National Affairs & Governance",
    "obituaries": "Appointments, Resignations & Committees",
    "obituary": "Appointments, Resignations & Committees",
    "polity": "National Affairs & Governance",
    "politics": "National Affairs & Governance",
    "rankings": "Awards, Honors & Rankings",
    "science": "Science, Technology & Space",
    "science and technology": "Science, Technology & Space",
    "schemes": "Government Schemes & Initiatives",
    "security": "Defence, Exercises & Security",
    "space": "Science, Technology & Space",
    "sports": "Sports & Cultural Events",
    "sports and culture": "Sports & Cultural Events",
    "sports and cultural events": "Sports & Cultural Events",
    "state news": "National Affairs & Governance",
    "summits": "International Affairs & Summits",
    "technology": "Science, Technology & Space",
    "telecom": "Science, Technology & Space",
    "trade": "Economy, Banking & Finance",
    "transport": "National Affairs & Governance",
    "welfare": "Government Schemes & Initiatives",
}

def _map_topic(raw: str) -> str:
    key = raw.strip().lower()
    if key in TOPIC_MAP:
        return TOPIC_MAP[key]
    for k, v in TOPIC_MAP.items():
        words = [w for w in k.split() if len(w) > 4]
        if words and any(w in key for w in words):
            return v
    return "National Affairs & Governance"

def _parse_month_year(raw: str):
    m = re.match(r'(\w+)\s+(\d{4})', raw.strip())
    return (m.group(1), int(m.group(2))) if m else ("September", 2026)

def _norm_diff(d: str) -> str:
    d = d.strip().lower()
    return d if d in ("easy", "medium", "hard") else "medium"

def _get(pattern, block, default=""):
    m = re.search(pattern, block, re.IGNORECASE | re.MULTILINE)
    return m.group(1).strip() if m else default

def _parse_format1(text: str):
    questions = []
    for block in re.split(r'END_QUESTION', text, flags=re.IGNORECASE):
        block = block.strip()
        if not block:
            continue
        if not re.search(r'^QUESTION\s*:', block, re.I | re.M):
            continue
        if not re.search(r'^CORRECT_ANSWER\s*:', block, re.I | re.M):
            continue
        question  = _get(r'^QUESTION\s*:\s*(.+)$', block)
        correct   = _get(r'^CORRECT_ANSWER\s*:\s*([A-D])', block).upper()
        raw_topic = _get(r'^TOPIC\s*:\s*(.+)$', block, "General")
        subtopic  = _get(r'^SUBTOPIC\s*:\s*(.+)$', block)
        difficulty= _norm_diff(_get(r'^DIFFICULTY\s*:\s*(.+)$', block, "medium"))
        source    = _get(r'^SOURCE\s*:\s*(.+)$', block, "claude_questions.txt")
        month_raw = _get(r'^MONTH\s*:\s*(.+)$', block, "September 2026")
        expl      = _get(r'^EXPLANATION\s*:\s*(.+)$', block)
        tip       = _get(r'^MEMORY_TIP\s*:\s*(.+)$', block)
        a = _get(r'^A\s*:\s*(.+)$', block)
        b = _get(r'^B\s*:\s*(.+)$', block)
        c = _get(r'^C\s*:\s*(.+)$', block)
        d = _get(r'^D\s*:\s*(.+)$', block)
        if not question or correct not in "ABCD" or not all([a, b, c, d]):
            continue
        month_name, year = _parse_month_year(month_raw)
        questions.append({"source_filename": source, "month": month_name, "year": year,
            "topic": _map_topic(raw_topic), "subtopic": subtopic, "question_text": question,
            "options": {"A": a, "B": b, "C": c, "D": d}, "correct_option": correct,
            "explanation": expl, "memory_cue": tip, "difficulty": difficulty})
    return questions

def _parse_format2(text: str):
    questions = []
    for chunk in re.split(r'(?m)^(?=ID\s*:)', text):
        chunk = chunk.strip()
        if not chunk:
            continue
        if not re.search(r'^Question\s*[:\.]', chunk, re.I | re.M):
            continue
        if not re.search(r'^Correct\s+answer\s*[:\.]', chunk, re.I | re.M):
            continue
        question  = _get(r'^Question\s*[:.]\s*(.+)$', chunk)
        correct   = _get(r'^Correct\s+answer\s*[:.]\s*([A-D])', chunk).upper()
        raw_topic = _get(r'^Topic\s*[:.]\s*(.+)$', chunk, "General")
        subtopic  = _get(r'^Subtopic\s*[:.]\s*(.+)$', chunk)
        difficulty= _norm_diff(_get(r'^Difficulty\s*[:.]\s*(.+)$', chunk, "medium"))
        source    = _get(r'^Source\s*[:.]\s*(.+)$', chunk, "claude_questions.txt")
        month_raw = _get(r'^Month\s*[:.]\s*(.+)$', chunk, "September 2026")
        expl      = _get(r'^Explanation\s*[:.]\s*(.+)$', chunk)
        tip       = _get(r'^Memory\s+tip\s*[:.]\s*(.+)$', chunk)
        a = _get(r'^A\s*[.:\)]\s*(.+)$', chunk)
        b = _get(r'^B\s*[.:\)]\s*(.+)$', chunk)
        c = _get(r'^C\s*[.:\)]\s*(.+)$', chunk)
        d = _get(r'^D\s*[.:\)]\s*(.+)$', chunk)
        if not question or correct not in "ABCD" or not all([a, b, c, d]):
            continue
        month_name, year = _parse_month_year(month_raw)
        questions.append({"source_filename": source, "month": month_name, "year": year,
            "topic": _map_topic(raw_topic), "subtopic": subtopic, "question_text": question,
            "options": {"A": a, "B": b, "C": c, "D": d}, "correct_option": correct,
            "explanation": expl, "memory_cue": tip, "difficulty": difficulty})
    return questions


def seed_questions_from_file(conn: sqlite3.Connection) -> int:
    """
    Import new questions from claude_questions.txt without deleting or
    modifying existing questions. Safe to run repeatedly.
    Returns the number of questions inserted.
    """
    if not QUESTIONS_FILE.exists():
        print(f"[Seeder] File not found: {QUESTIONS_FILE}")
        return 0

    text = QUESTIONS_FILE.read_text(encoding="utf-8")
    text = re.split(r'END_OF_QUESTION_BANK', text, flags=re.I)[0]

    last_eq = [m.end() for m in re.finditer(r'END_QUESTION', text, re.I)]
    if last_eq:
        f1_text = text[:last_eq[-1]]
        f2_text = text[last_eq[-1]:]
    else:
        f1_text = ""
        f2_text = text

    all_qs = _parse_format1(f1_text) + _parse_format2(f2_text)

    # Normalize question text to detect existing and repeated questions.
    def question_key(value):
        return " ".join(value.casefold().split())

    seen = set()

    # Load questions already in SQLite. Do not delete or update them.
    existing_rows = conn.execute(
        "SELECT question_text FROM questions"
    ).fetchall()

    for row in existing_rows:
        seen.add(question_key(row[0]))

    inserted = 0
    skipped = 0
    errors = 0

    for q in all_qs:
        key = question_key(q["question_text"])

        if not key or key in seen:
            skipped += 1
            continue

        try:
            conn.execute("""
                INSERT INTO questions (
                    source_filename, month, year, topic, subtopic,
                    question_text, options_json, correct_option,
                    explanation, memory_cue, key_concept,
                    difficulty, approval_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved', datetime('now'))
            """, (
                q["source_filename"],
                q["month"],
                q["year"],
                q["topic"],
                q["subtopic"],
                q["question_text"],
                json.dumps(q["options"], ensure_ascii=False),
                q["correct_option"],
                q["explanation"],
                q["memory_cue"],
                q["subtopic"],
                q["difficulty"],
            ))

            # Prevent duplicates within the same import.
            seen.add(key)
            inserted += 1

        except Exception as exc:
            errors += 1
            print(
                f"[Seeder] Failed to import question "
                f"{q['question_text'][:100]!r}: {exc}"
            )

    print(
        f"[Seeder] Parsed {len(all_qs)} questions; "
        f"inserted {inserted}; skipped duplicates {skipped}; "
        f"errors {errors}."
    )

    return inserted
