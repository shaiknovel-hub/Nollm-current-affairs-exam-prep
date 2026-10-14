import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from src.database import connect, init_db

def get_questions(
    mode: str = "All approved questions",
    limit: int = 10,
    topic: Optional[str] = None,
    month: Optional[str] = None,
    year: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Retrieves approved questions filtered by month, year, topic, and practice mode.
    Never mixes questions from different months when a specific month is specified.
    """
    init_db()
    query = "SELECT * FROM questions WHERE approval_status = 'approved'"
    params = []

    if month and year and month != "All months":
        query += " AND month = ? AND year = ?"
        params.extend([month, year])

    if topic and topic != "All topics":
        query += " AND topic = ?"
        params.append(topic)

    with connect() as conn:
        rows = conn.execute(query, params).fetchall()

    questions = [dict(r) for r in rows]
    for q in questions:
        try:
            q["options"] = json.loads(q.pop("options_json"))
        except Exception:
            q["options"] = {}

    if not questions:
        return []

    # Filter based on practice mode
    if mode == "Mistakes only":
        with connect() as conn:
            wrong_query = """
                SELECT DISTINCT a.question_id 
                FROM attempts a
                JOIN questions q ON a.question_id = q.question_id
                WHERE a.is_correct = 0
            """
            w_params = []
            if month and year and month != "All months":
                wrong_query += " AND q.month = ? AND q.year = ?"
                w_params.extend([month, year])
            wrong = {r["question_id"] for r in conn.execute(wrong_query, w_params).fetchall()}
        questions = [q for q in questions if q["question_id"] in wrong]

    elif mode == "Due for review":
        with connect() as conn:
            due_query = """
                SELECT r.question_id 
                FROM review_schedule r
                JOIN questions q ON r.question_id = q.question_id
                WHERE r.next_review_at <= datetime('now', 'localtime')
            """
            d_params = []
            if month and year and month != "All months":
                due_query += " AND q.month = ? AND q.year = ?"
                d_params.extend([month, year])
            due = {r["question_id"] for r in conn.execute(due_query, d_params).fetchall()}
        questions = [q for q in questions if q["question_id"] in due]

    elif mode == "Weak topics":
        with connect() as conn:
            weak_query = """
                SELECT q.topic, 
                       CAST(SUM(CASE WHEN a.is_correct = 1 THEN 1 ELSE 0 END) AS REAL) / COUNT(*) AS acc
                FROM attempts a
                JOIN questions q ON a.question_id = q.question_id
                WHERE q.topic IS NOT NULL
                GROUP BY q.topic
                HAVING acc < 0.65
            """
            weak_topics = {r["topic"] for r in conn.execute(weak_query).fetchall()}
        if weak_topics:
            questions = [q for q in questions if q.get("topic") in weak_topics]

    random.shuffle(questions)
    return questions[:max(1, int(limit))]

def record_attempt(
    question_id: int,
    selected: str,
    correct: bool,
    session_id: str,
    response_time: Optional[float] = None
) -> None:
    """
    Records a user's answer attempt and updates the Spaced Repetition (SRS) schedule.
    """
    init_db()
    now = datetime.now()
    with connect() as conn:
        conn.execute(
            """INSERT INTO attempts(question_id, selected_option, is_correct, session_id, response_time)
               VALUES(?,?,?,?,?)""",
            (question_id, selected, int(correct), session_id, response_time)
        )

        old = conn.execute(
            "SELECT interval_days, consecutive_correct, lapse_count FROM review_schedule WHERE question_id=?",
            (question_id,)
        ).fetchone()

        interval, streak, lapses = (old["interval_days"], old["consecutive_correct"], old["lapse_count"]) if old else (1, 0, 0)
        
        if correct:
            streak += 1
            intervals = {1: 1, 2: 3, 3: 7, 4: 14}
            interval = intervals.get(streak, min(45, interval * 2))
        else:
            streak = 0
            interval = 1
            lapses += 1

        next_review = (now + timedelta(days=interval)).strftime("%Y-%m-%d %H:%M:%S")

        conn.execute("""
            INSERT INTO review_schedule(question_id, next_review_at, interval_days,
                consecutive_correct, lapse_count, last_result)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(question_id) DO UPDATE SET
                next_review_at=excluded.next_review_at,
                interval_days=excluded.interval_days,
                consecutive_correct=excluded.consecutive_correct,
                lapse_count=excluded.lapse_count,
                last_result=excluded.last_result
        """, (question_id, next_review, interval, streak, lapses, int(correct)))

def start_quiz_session(session_id: str, mode: str, month: str, year: int, topic: str, total_q: int) -> None:
    """Logs the start of a quiz session."""
    init_db()
    with connect() as conn:
        conn.execute("""
            INSERT INTO quiz_sessions(session_id, mode, month, year, topic, total_questions, started_at)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(session_id) DO UPDATE SET
                mode=excluded.mode,
                month=excluded.month,
                year=excluded.year,
                topic=excluded.topic,
                total_questions=excluded.total_questions
        """, (session_id, mode, month, year, topic, total_q, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

def finish_quiz_session(session_id: str, correct_count: int, total_questions: int) -> None:
    """Logs the completion of a quiz session."""
    init_db()
    acc = (correct_count / total_questions * 100) if total_questions > 0 else 0.0
    with connect() as conn:
        conn.execute("""
            UPDATE quiz_sessions
            SET completed_at = ?,
                correct_count = ?,
                total_questions = ?,
                accuracy = ?
            WHERE session_id = ?
        """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), correct_count, total_questions, acc, session_id))

def get_mistakes_detailed(month: Optional[str] = None, year: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Fetches all questions where the user made mistakes, along with SRS review details,
    for the mistake revision workbook.
    """
    init_db()
    query = """
        SELECT 
            q.question_id, q.question_text, q.options_json, q.correct_option,
            q.explanation, q.memory_cue, q.topic, q.subtopic, q.difficulty,
            q.month, q.year, q.source_filename, q.page_number,
            r.next_review_at, r.interval_days, r.consecutive_correct, r.lapse_count, r.last_result,
            COUNT(a.attempt_id) AS total_attempts,
            SUM(CASE WHEN a.is_correct = 0 THEN 1 ELSE 0 END) AS wrong_attempts
        FROM questions q
        JOIN attempts a ON q.question_id = a.question_id
        LEFT JOIN review_schedule r ON q.question_id = r.question_id
        WHERE q.approval_status = 'approved'
    """
    params = []
    if month and year and month != "All months":
        query += " AND q.month = ? AND q.year = ?"
        params.extend([month, year])

    query += """
        GROUP BY q.question_id
        HAVING wrong_attempts > 0
        ORDER BY r.lapse_count DESC, r.next_review_at ASC
    """

    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
        mistakes = []
        for r in rows:
            m = dict(r)
            try:
                m["options"] = json.loads(m.pop("options_json"))
            except Exception:
                m["options"] = {}
            mistakes.append(m)
        return mistakes

def get_topic_analytics(month: Optional[str] = None, year: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Computes attempt accuracy and question count for each topic.
    """
    init_db()
    query = """
        SELECT 
            COALESCE(q.topic, 'General') AS topic,
            COUNT(DISTINCT q.question_id) AS total_questions,
            COUNT(a.attempt_id) AS total_attempts,
            SUM(CASE WHEN a.is_correct = 1 THEN 1 ELSE 0 END) AS correct_attempts
        FROM questions q
        LEFT JOIN attempts a ON q.question_id = a.question_id
        WHERE q.approval_status = 'approved'
    """
    params = []
    if month and year and month != "All months":
        query += " AND q.month = ? AND q.year = ?"
        params.extend([month, year])

    query += " GROUP BY COALESCE(q.topic, 'General') ORDER BY total_attempts DESC, topic ASC"

    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
        result = []
        for r in rows:
            attempts = r["total_attempts"] or 0
            correct = r["correct_attempts"] or 0
            acc = round((correct / attempts * 100), 1) if attempts > 0 else 0.0
            result.append({
                "topic": r["topic"],
                "total_questions": r["total_questions"],
                "total_attempts": attempts,
                "correct_attempts": correct,
                "accuracy": acc
            })
        return result

def get_recent_sessions(limit: int = 10) -> List[Dict[str, Any]]:
    """Returns recent completed quiz sessions."""
    init_db()
    with connect() as conn:
        rows = conn.execute("""
            SELECT * FROM quiz_sessions
            WHERE completed_at IS NOT NULL
            ORDER BY completed_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
