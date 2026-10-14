import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database import connect, init_db
from src.question_generator import generate_questions_for_document

def main():
    init_db()
    with connect() as conn:
        rows = conn.execute("SELECT document_id, filename, month, year FROM documents WHERE month = 'September'").fetchall()
        docs = [dict(r) for r in rows]

    print(f"Generating comprehensive exam questions from {len(docs)} September documents...")

    total_saved = 0
    for d in docs:
        res = generate_questions_for_document(d["document_id"], d["month"], d["year"], max_questions=80)
        print(f"  {d['filename']}: Found {res.get('generated', 0)} candidates | Added {res.get('saved_to_review', 0)} new questions")
        total_saved += res.get('saved_to_review', 0)

    with connect() as conn:
        total_sep = conn.execute("SELECT COUNT(*) AS n FROM questions WHERE month='September'").fetchone()["n"]
        total_all = conn.execute("SELECT COUNT(*) AS n FROM questions").fetchone()["n"]
        by_topic = conn.execute("SELECT topic, COUNT(*) as c FROM questions WHERE month='September' GROUP BY topic ORDER BY c DESC").fetchall()

    print(f"\n==========================================")
    print(f"New questions generated: {total_saved}")
    print(f"Total September questions in question bank: {total_sep}")
    print(f"Total questions across all months: {total_all}")
    print("\nTopic Breakdown for September 2026:")
    for r in by_topic:
        print(f"  - {r['topic']}: {r['c']} questions")
    print(f"==========================================")

if __name__ == "__main__":
    main()
