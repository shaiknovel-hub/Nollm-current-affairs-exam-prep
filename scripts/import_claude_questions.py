"""
Import questions from claude_questions.txt into the exam_prep.db database.
Handles TWO formats:

FORMAT 1 (old - uses END_QUESTION delimiter):
  ID: SEP22-AGR-004
  MONTH: September 2026
  TOPIC: Agriculture
  ...
  CORRECT_ANSWER: A
  EXPLANATION: ...
  MEMORY_TIP: ...
  END_QUESTION

FORMAT 2 (new - no END_QUESTION, uses dot for options, title-case fields):
  ID: SEP24-NAT-001
  Month: September 2026
  Topic: National Affairs
  ...
  A. Ministry of Civil Aviation
  B. Ministry of Railways
  Correct answer: A
  Explanation: ...
  Memory tip: ...
  (blank line or next ID: marks end)
"""

import re
import json
import sqlite3
import sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "exam_prep.db"
TXT_PATH = ROOT / "claude_questions.txt"

# ---------------------------------------------------------------------------
# Canonical topic mapping
# ---------------------------------------------------------------------------
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
    "banking and financial": "Economy, Banking & Finance",
    "business": "Economy, Banking & Finance",
    "business and economy": "Economy, Banking & Finance",
    "defence": "Defence, Exercises & Security",
    "defence and security": "Defence, Exercises & Security",
    "defence and space": "Defence, Exercises & Security",
    "economy": "Economy, Banking & Finance",
    "economy and business": "Economy, Banking & Finance",
    "economy and finance": "Economy, Banking & Finance",
    "economy and trade": "Economy, Banking & Finance",
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
    "international relations": "International Affairs & Summits",
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
    "science technology and space": "Science, Technology & Space",
    "schemes": "Government Schemes & Initiatives",
    "security": "Defence, Exercises & Security",
    "space": "Science, Technology & Space",
    "sports": "Sports & Cultural Events",
    "sports and culture": "Sports & Cultural Events",
    "sports and cultural": "Sports & Cultural Events",
    "sports and cultural events": "Sports & Cultural Events",
    "state news": "National Affairs & Governance",
    "summits": "International Affairs & Summits",
    "technology": "Science, Technology & Space",
    "telecom": "Science, Technology & Space",
    "trade": "Economy, Banking & Finance",
    "transport": "National Affairs & Governance",
    "welfare": "Government Schemes & Initiatives",
}

def map_topic(raw_topic: str) -> str:
    key = raw_topic.strip().lower()
    if key in TOPIC_MAP:
        return TOPIC_MAP[key]
    for k, v in TOPIC_MAP.items():
        words = [w for w in k.split() if len(w) > 4]
        if words and any(w in key for w in words):
            return v
    return "National Affairs & Governance"

def parse_month_year(raw: str):
    m = re.match(r'(\w+)\s+(\d{4})', raw.strip())
    if m:
        return m.group(1), int(m.group(2))
    return "September", 2026

def normalize_difficulty(d: str) -> str:
    d = d.strip().lower()
    return d if d in ("easy", "medium", "hard") else "medium"

# ---------------------------------------------------------------------------
# FORMAT 1 parser: END_QUESTION delimited blocks
# ---------------------------------------------------------------------------
def parse_format1(text: str):
    questions = []
    errors = []
    blocks = re.split(r'END_QUESTION', text, flags=re.IGNORECASE)

    for block in blocks:
        block = block.strip()
        if not block:
            continue
        # Must contain a QUESTION: field
        if not re.search(r'^QUESTION\s*:', block, re.I | re.M):
            continue
        if not re.search(r'^CORRECT_ANSWER\s*:', block, re.I | re.M):
            continue

        def get(pattern, default=""):
            m = re.search(pattern, block, re.IGNORECASE | re.MULTILINE)
            return m.group(1).strip() if m else default

        question   = get(r'^QUESTION\s*:\s*(.+)$')
        correct    = get(r'^CORRECT_ANSWER\s*:\s*([A-D])').upper()
        raw_topic  = get(r'^TOPIC\s*:\s*(.+)$', "General")
        subtopic   = get(r'^SUBTOPIC\s*:\s*(.+)$')
        difficulty = normalize_difficulty(get(r'^DIFFICULTY\s*:\s*(.+)$', "medium"))
        source     = get(r'^SOURCE\s*:\s*(.+)$', "claude_questions.txt")
        month_raw  = get(r'^MONTH\s*:\s*(.+)$', "September 2026")
        explanation= get(r'^EXPLANATION\s*:\s*(.+)$')
        memory_tip = get(r'^MEMORY_TIP\s*:\s*(.+)$')
        opt_a      = get(r'^A\s*:\s*(.+)$')
        opt_b      = get(r'^B\s*:\s*(.+)$')
        opt_c      = get(r'^C\s*:\s*(.+)$')
        opt_d      = get(r'^D\s*:\s*(.+)$')

        if not question:
            errors.append(f"[F1] No question in block: {block[:60]}")
            continue
        if correct not in ("A", "B", "C", "D"):
            errors.append(f"[F1] Bad answer '{correct}': {question[:60]}")
            continue
        if not all([opt_a, opt_b, opt_c, opt_d]):
            errors.append(f"[F1] Missing options: {question[:60]}")
            continue

        month_name, year = parse_month_year(month_raw)
        questions.append({
            "source_filename": source,
            "month": month_name,
            "year": year,
            "topic": map_topic(raw_topic),
            "subtopic": subtopic,
            "question_text": question,
            "options": {"A": opt_a, "B": opt_b, "C": opt_c, "D": opt_d},
            "correct_option": correct,
            "explanation": explanation,
            "memory_cue": memory_tip,
            "difficulty": difficulty,
            "key_concept": subtopic,
        })

    return questions, errors

# ---------------------------------------------------------------------------
# FORMAT 2 parser: ID:-delimited, dot-separated options, no END_QUESTION
# ---------------------------------------------------------------------------
def parse_format2(text: str):
    """
    Splits on 'ID:' boundaries. Each chunk is one question record.
    Options are like: A. text  B. text  or  A: text  B: text
    Correct answer field: 'Correct answer: A' or 'Correct Answer: A'
    """
    questions = []
    errors = []

    # Split on lines starting with 'ID:'
    chunks = re.split(r'(?m)^(?=ID\s*:)', text)

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        # Must have a Question field and Correct answer
        if not re.search(r'^Question\s*[:\.]', chunk, re.I | re.M):
            continue
        if not re.search(r'^Correct\s+answer\s*[:\.]', chunk, re.I | re.M):
            continue

        def get(pattern, default=""):
            m = re.search(pattern, chunk, re.IGNORECASE | re.MULTILINE)
            return m.group(1).strip() if m else default

        question   = get(r'^Question\s*[:.]\s*(.+)$')
        correct    = get(r'^Correct\s+answer\s*[:.]\s*([A-D])').upper()
        raw_topic  = get(r'^Topic\s*[:.]\s*(.+)$', "General")
        subtopic   = get(r'^Subtopic\s*[:.]\s*(.+)$')
        difficulty = normalize_difficulty(get(r'^Difficulty\s*[:.]\s*(.+)$', "medium"))
        source     = get(r'^Source\s*[:.]\s*(.+)$', "claude_questions.txt")
        month_raw  = get(r'^Month\s*[:.]\s*(.+)$', "September 2026")
        explanation= get(r'^Explanation\s*[:.]\s*(.+)$')
        memory_tip = get(r'^Memory\s+tip\s*[:.]\s*(.+)$')

        # Options: match "A. text" or "A: text" or "A) text"
        opt_a = get(r'^A\s*[.:\)]\s*(.+)$')
        opt_b = get(r'^B\s*[.:\)]\s*(.+)$')
        opt_c = get(r'^C\s*[.:\)]\s*(.+)$')
        opt_d = get(r'^D\s*[.:\)]\s*(.+)$')

        if not question:
            errors.append(f"[F2] No question in chunk: {chunk[:60]}")
            continue
        if correct not in ("A", "B", "C", "D"):
            errors.append(f"[F2] Bad answer '{correct}': {question[:60]}")
            continue
        if not all([opt_a, opt_b, opt_c, opt_d]):
            errors.append(f"[F2] Missing options for: {question[:60]}")
            continue

        month_name, year = parse_month_year(month_raw)
        questions.append({
            "source_filename": source,
            "month": month_name,
            "year": year,
            "topic": map_topic(raw_topic),
            "subtopic": subtopic,
            "question_text": question,
            "options": {"A": opt_a, "B": opt_b, "C": opt_c, "D": opt_d},
            "correct_option": correct,
            "explanation": explanation,
            "memory_cue": memory_tip,
            "difficulty": difficulty,
            "key_concept": subtopic,
        })

    return questions, errors

# ---------------------------------------------------------------------------
# Combined parser - auto-detects both formats in same file
# ---------------------------------------------------------------------------
def parse_all_questions(filepath: Path):
    text = filepath.read_text(encoding="utf-8")

    # Split at the END_OF_QUESTION_BANK marker if present
    text = re.split(r'END_OF_QUESTION_BANK', text, flags=re.I)[0]

    # Find the split point between format 1 (has END_QUESTION) and format 2
    # Format 1 blocks end with END_QUESTION; format 2 never has it
    f1_text = ""
    f2_text = ""

    last_end_question = [m.end() for m in re.finditer(r'END_QUESTION', text, re.I)]
    if last_end_question:
        split_pos = last_end_question[-1]
        f1_text = text[:split_pos]
        f2_text = text[split_pos:]
    else:
        f2_text = text

    q1, e1 = parse_format1(f1_text) if f1_text.strip() else ([], [])
    q2, e2 = parse_format2(f2_text) if f2_text.strip() else ([], [])

    # De-duplicate by question_text
    seen = set()
    all_questions = []
    for q in q1 + q2:
        key = q["question_text"].strip().lower()
        if key not in seen:
            seen.add(key)
            all_questions.append(q)

    return all_questions, e1 + e2

# ---------------------------------------------------------------------------
# DB import
# ---------------------------------------------------------------------------
def import_to_db(questions):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DELETE FROM review_schedule")
    conn.execute("DELETE FROM attempts")
    deleted = conn.execute("DELETE FROM questions").rowcount
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    print(f"Cleared {deleted} existing questions (+ all attempts and review records).")

    inserted = 0
    skipped = 0

    for q in questions:
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
                json.dumps(q["options"]),
                q["correct_option"],
                q["explanation"],
                q["memory_cue"],
                q["key_concept"],
                q["difficulty"],
            ))
            inserted += 1
        except Exception as e:
            print(f"  ERROR: '{q['question_text'][:60]}': {e}")
            skipped += 1

    conn.commit()
    conn.close()
    return inserted, skipped

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
def print_summary(questions, errors, inserted, skipped):
    topic_counts = Counter(q["topic"] for q in questions)
    diff_counts  = Counter(q["difficulty"] for q in questions)
    source_counts = Counter(q["source_filename"] for q in questions)

    print("\n" + "="*65)
    print("  IMPORT COMPLETE")
    print("="*65)
    print(f"  Questions parsed    : {len(questions)}")
    print(f"  Inserted into DB    : {inserted}")
    print(f"  Skipped (errors)    : {skipped}")
    print(f"  Parse warnings      : {len(errors)}")
    print()
    print("  By Topic:")
    for topic, count in sorted(topic_counts.items(), key=lambda x: -x[1]):
        print(f"    {topic:<52} {count:>4}")
    print()
    print("  By Difficulty:")
    for diff, count in sorted(diff_counts.items()):
        print(f"    {diff:<12} {count:>4}")
    print()
    print("  By Source PDF:")
    for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        short = src.replace("Toppers-CA-", "").replace("-by-AffairsCloud-1-v01.pdf","").replace("-by-AffairsCloud-1-1-v01.pdf","")
        print(f"    {short:<45} {count:>4}")
    if errors:
        print(f"\n  Warnings ({len(errors)} total, first 10):")
        for e in errors[:10]:
            print(f"    - {e}")
    print("="*65)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if not TXT_PATH.exists():
        print(f"ERROR: File not found: {TXT_PATH}")
        sys.exit(1)

    print(f"Parsing: {TXT_PATH}  ({TXT_PATH.stat().st_size // 1024} KB, {sum(1 for _ in TXT_PATH.open('r', encoding='utf-8'))} lines)")
    questions, errors = parse_all_questions(TXT_PATH)
    print(f"Parsed {len(questions)} unique questions ({len(errors)} warnings).")

    if not questions:
        print("No questions found. Aborting.")
        sys.exit(1)

    inserted, skipped = import_to_db(questions)
    print_summary(questions, errors, inserted, skipped)
