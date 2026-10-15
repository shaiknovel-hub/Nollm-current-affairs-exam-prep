import sqlite3
from pathlib import Path
import json
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "exam_prep.db"

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def _column_exists(conn, table_name, column_name):
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    columns = [row["name"] for row in cursor.fetchall()]
    return column_name in columns

def init_db():
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            document_id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            date TEXT,
            month TEXT,
            year INTEGER,
            page_count INTEGER,
            processing_status TEXT DEFAULT 'pending',
            content_hash TEXT,
            scanned_pages_json TEXT,
            error_message TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS questions (
            question_id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER,
            source_filename TEXT,
            page_number INTEGER,
            month TEXT,
            year INTEGER,
            topic TEXT,
            subtopic TEXT,
            question_text TEXT NOT NULL,
            options_json TEXT NOT NULL,
            correct_option TEXT NOT NULL CHECK(correct_option IN ('A','B','C','D')),
            explanation TEXT,
            memory_cue TEXT,
            key_concept TEXT,
            image_path TEXT,
            difficulty TEXT DEFAULT 'medium',
            approval_status TEXT DEFAULT 'approved',
            created_at TEXT,
            FOREIGN KEY(document_id) REFERENCES documents(document_id)
        );
        CREATE TABLE IF NOT EXISTS attempts (
            attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            selected_option TEXT,
            is_correct INTEGER NOT NULL,
            attempted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            session_id TEXT,
            response_time REAL,
            FOREIGN KEY(question_id) REFERENCES questions(question_id)
        );
        CREATE TABLE IF NOT EXISTS review_schedule (
            question_id INTEGER PRIMARY KEY,
            next_review_at TEXT,
            interval_days INTEGER DEFAULT 1,
            consecutive_correct INTEGER DEFAULT 0,
            lapse_count INTEGER DEFAULT 0,
            last_result INTEGER,
            FOREIGN KEY(question_id) REFERENCES questions(question_id)
        );
        CREATE TABLE IF NOT EXISTS quiz_sessions (
            session_id TEXT PRIMARY KEY,
            started_at TEXT,
            completed_at TEXT,
            mode TEXT,
            month TEXT,
            year INTEGER,
            topic TEXT,
            total_questions INTEGER DEFAULT 0,
            correct_count INTEGER DEFAULT 0,
            accuracy REAL DEFAULT 0.0
        );
        CREATE INDEX IF NOT EXISTS idx_questions_approval ON questions(approval_status);
        CREATE INDEX IF NOT EXISTS idx_attempts_question ON attempts(question_id);
        """)

        # Migration: Add any missing columns to existing tables safely
        migrations = [
            ("documents", "year", "INTEGER"),
            ("documents", "scanned_pages_json", "TEXT"),
            ("documents", "error_message", "TEXT"),
            ("documents", "created_at", "TEXT"),
            ("questions", "month", "TEXT"),
            ("questions", "year", "INTEGER"),
            ("questions", "subtopic", "TEXT"),
            ("questions", "key_concept", "TEXT"),
            ("questions", "created_at", "TEXT"),
            ("quiz_sessions", "month", "TEXT"),
            ("quiz_sessions", "year", "INTEGER"),
            ("quiz_sessions", "topic", "TEXT"),
            ("quiz_sessions", "accuracy", "REAL DEFAULT 0.0"),
        ]

        for table, column, col_type in migrations:
            if not _column_exists(conn, table, column):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

        # Backfill month and year for existing questions if NULL
        conn.execute("""
            UPDATE questions
            SET month = 'August', year = 2026
            WHERE (month IS NULL OR year IS NULL)
              AND (source_filename LIKE '%August%' OR source_filename LIKE '%Aug%')
        """)
        conn.execute("""
            UPDATE questions
            SET month = 'September', year = 2026
            WHERE (month IS NULL OR year IS NULL)
              AND (source_filename LIKE '%September%' OR source_filename LIKE '%Sep%')
        """)
        conn.execute("""
            UPDATE questions
            SET month = 'August', year = 2026
            WHERE month IS NULL OR year IS NULL
        """)

        # Performance indexes for month and topic filtering
        conn.execute("CREATE INDEX IF NOT EXISTS idx_questions_month_year ON questions(year, month, approval_status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_questions_topic ON questions(topic)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(content_hash)")

        
        # Import new questions on every initialization.
        # The seeder skips questions already present in SQLite.
        try:
            from src.seeder import seed_questions_from_file
        
            n = seed_questions_from_file(conn)
            if n > 0:
                conn.commit()
                print(f"[Database] Imported {n} new questions.")
        except Exception as exc:
            print(f"[Database] Question import failed: {exc}")

        


def get_available_months():
    """
    Returns list of dicts with available month/year combinations where approved or candidate questions exist.
    Always includes September 2026 as available for the user.
    """
    with connect() as conn:
        rows = conn.execute("""
            SELECT DISTINCT month, year FROM questions WHERE month IS NOT NULL AND year IS NOT NULL
            UNION
            SELECT DISTINCT month, year FROM documents WHERE month IS NOT NULL AND year IS NOT NULL
        """).fetchall()

    month_order = {
        'January': 1, 'February': 2, 'March': 3, 'April': 4,
        'May': 5, 'June': 6, 'July': 7, 'August': 8,
        'September': 9, 'October': 10, 'November': 11, 'December': 12
    }

    sorted_rows = sorted(
        rows,
        key=lambda r: (r["year"] or 0, month_order.get(r["month"], 0)),
        reverse=True
    )

    months = [{"month": r["month"], "year": r["year"], "label": f"{r['month']} {r['year']}"} for r in sorted_rows]
    labels = {m["label"] for m in months}
    if "September 2026" not in labels:
        months.insert(0, {"month": "September", "year": 2026, "label": "September 2026"})
        
    return months


def get_dashboard_metrics(selected_month=None, selected_year=None):
    """
    Calculates summary metrics filtered by month & year, or across all months.
    """
    where_q = ["approval_status='approved'"]
    where_doc = []
    where_att = []
    params_q = []
    params_doc = []
    params_att = []

    if selected_month and selected_year and selected_month != "All months":
        where_q.append("month = ? AND year = ?")
        params_q.extend([selected_month, selected_year])

        where_doc.append("month = ? AND year = ?")
        params_doc.extend([selected_month, selected_year])

        where_att.append("q.month = ? AND q.year = ?")
        params_att.extend([selected_month, selected_year])

    q_clause = " WHERE " + " AND ".join(where_q)
    doc_clause = (" WHERE " + " AND ".join(where_doc)) if where_doc else ""
    att_clause = (" WHERE " + " AND ".join(where_att)) if where_att else ""

    with connect() as conn:
        doc_count = conn.execute(f"SELECT COUNT(*) AS n FROM documents{doc_clause}", params_doc).fetchone()["n"]
        total_questions = conn.execute(f"SELECT COUNT(*) AS n FROM questions{q_clause}", params_q).fetchone()["n"]
        
        topic_count = conn.execute(f"""
            SELECT COUNT(DISTINCT topic) AS n 
            FROM questions{q_clause} AND topic IS NOT NULL
        """, params_q).fetchone()["n"]

        attempts_query = f"""
            SELECT 
                COUNT(*) AS total_attempts,
                SUM(CASE WHEN a.is_correct = 1 THEN 1 ELSE 0 END) AS correct_attempts,
                COUNT(DISTINCT CASE WHEN a.is_correct = 0 THEN a.question_id END) AS missed_questions
            FROM attempts a
            JOIN questions q ON a.question_id = q.question_id
            {att_clause}
        """
        att_row = conn.execute(attempts_query, params_att).fetchone()
        
        attempts = att_row["total_attempts"] if att_row else 0
        correct_attempts = att_row["correct_attempts"] if att_row and att_row["correct_attempts"] else 0
        wrong_count = att_row["missed_questions"] if att_row and att_row["missed_questions"] else 0
        
        due_query = f"""
            SELECT COUNT(*) AS n
            FROM review_schedule r
            JOIN questions q ON r.question_id = q.question_id
            WHERE r.next_review_at <= datetime('now', 'localtime')
            {(" AND q.month = ? AND q.year = ?") if selected_month and selected_year and selected_month != "All months" else ""}
        """
        due_count = conn.execute(due_query, params_q).fetchone()["n"]

    accuracy = (correct_attempts / attempts * 100) if attempts > 0 else 0.0

    return {
        "documents": doc_count,
        "topics": topic_count,
        "questions": total_questions,
        "attempts": attempts,
        "accuracy": accuracy,
        "wrong_count": wrong_count,
        "due_count": due_count
    }
