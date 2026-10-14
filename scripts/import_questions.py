import json
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database import init_db, connect

DEFAULT_SOURCE = ROOT / "data" / "sample_questions.json"

def import_questions_from_json(file_path: Path, default_month: str = "August", default_year: int = 2026):
    init_db()
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return 0, 0

    data = json.loads(file_path.read_text(encoding="utf-8"))
    added = 0
    skipped = 0

    with connect() as conn:
        for q in data:
            if not q.get("approved", True):
                continue
            options = q.get("options", {})
            if set(options) != {"A", "B", "C", "D"} or q.get("correct_option") not in options:
                print(f"SKIP invalid question: {q.get('question', '<no question>')}")
                skipped += 1
                continue

            q_text = q["question"]
            month = q.get("month", default_month)
            year = q.get("year", default_year)

            # Deduplication: Check if question with exact text already exists
            existing = conn.execute(
                "SELECT question_id FROM questions WHERE question_text = ?",
                (q_text,)
            ).fetchone()

            if existing:
                skipped += 1
                continue

            conn.execute("""
                INSERT INTO questions(
                    source_filename, page_number, month, year, topic, subtopic,
                    question_text, options_json, correct_option, explanation,
                    memory_cue, key_concept, difficulty, approval_status
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                q.get("source_filename"),
                q.get("page_number"),
                month,
                year,
                q.get("topic", "General"),
                q.get("subtopic"),
                q_text,
                json.dumps(options, ensure_ascii=False),
                q["correct_option"],
                q.get("explanation", ""),
                q.get("memory_cue", ""),
                q.get("key_concept", ""),
                q.get("difficulty", "medium"),
                "approved" if q.get("approved", True) else "pending_review"
            ))
            added += 1

    print(f"Import complete: {added} questions imported, {skipped} skipped (duplicates or invalid).")
    return added, skipped

def main():
    parser = argparse.ArgumentParser(description="Import questions from JSON into SQLite database.")
    parser.add_argument("--file", type=str, default=str(DEFAULT_SOURCE), help="Path to JSON file")
    parser.add_argument("--month", type=str, default="August", help="Target month (e.g. August, September)")
    parser.add_argument("--year", type=int, default=2026, help="Target year (e.g. 2026)")
    args = parser.parse_args()

    import_questions_from_json(Path(args.file), args.month, args.year)

if __name__ == "__main__":
    main()
