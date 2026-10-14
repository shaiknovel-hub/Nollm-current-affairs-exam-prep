import pytest
import sqlite3
import json
import pymupdf
from pathlib import Path

from src.database import init_db, connect, get_available_months, get_dashboard_metrics
from src.pdf_processor import extract_pdf_data, calculate_sha256, get_imported_documents
from src.question_generator import (
    extract_candidate_facts_from_text,
    generate_questions_for_document,
    get_candidate_questions,
    update_candidate_question,
    bulk_set_approval_status
)
from src.quiz_engine import (
    get_questions,
    record_attempt,
    get_mistakes_detailed,
    get_topic_analytics
)

def test_database_initialization():
    init_db()
    with connect() as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "questions" in tables
        assert "documents" in tables
        assert "attempts" in tables
        assert "review_schedule" in tables
        assert "quiz_sessions" in tables

def test_available_months():
    months = get_available_months()
    labels = [m["label"] for m in months]
    assert "September 2026" in labels
    assert "August 2026" in labels

def test_month_filtering_and_separation():
    # September questions must not include August questions
    sep_qs = get_questions("All approved questions", limit=50, month="September", year=2026)
    for q in sep_qs:
        assert q["month"] == "September"
        assert q["year"] == 2026

    aug_qs = get_questions("All approved questions", limit=50, month="August", year=2026)
    for q in aug_qs:
        assert q["month"] == "August"
        assert q["year"] == 2026

def test_pdf_extraction_and_deduplication(tmp_path):
    # Create a dummy PDF with PyMuPDF
    doc = pymupdf.open()
    page = doc.new_page()
    sample_text = (
        "National Semiconductor Mission:\n"
        "The Union Cabinet approved a semiconductor unit in Sanand with outlay of ₹3,300 crore.\n"
        "Exercise Yudh Abhyas was held in Rajasthan with the United States Army.\n"
    )
    page.insert_text((50, 72), sample_text, fontsize=11)
    pdf_bytes = doc.write()

    # First extraction
    res1 = extract_pdf_data(pdf_bytes, "test_doc_unit.pdf", month="September", year=2026)
    assert res1["status"] in ("success", "duplicate")

    # Second extraction of identical content should trigger duplicate detection
    res2 = extract_pdf_data(pdf_bytes, "test_doc_unit_copy.pdf", month="September", year=2026)
    assert res2["status"] == "duplicate"

def test_candidate_question_generation_from_text():
    sample_passage = (
        "Cabinet approves PM-eBus Sewa Payment Security Mechanism with total outlay of ₹3,435 crore.\n"
        "Indo-US joint military drill Exercise Vajra Prahar was held in Umroi, Meghalaya.\n"
        "Gross GST revenue collections stood at ₹1.74 lakh crore in August 2026.\n"
    )
    candidates = extract_candidate_facts_from_text(sample_passage, "unit_test.pdf", 1, "September", 2026)
    assert len(candidates) >= 1
    for c in candidates:
        assert "A" in c["options"] and "D" in c["options"]
        assert c["correct_option"] in ["A", "B", "C", "D"]
        assert len(c["explanation"]) > 10
        assert len(c["memory_cue"]) > 5
        # Ensure questions never contain meta/booklet phrases
        q_lower = c["question_text"].lower()
        assert "page" not in q_lower
        assert "booklet" not in q_lower
        assert "material" not in q_lower
        assert "document" not in q_lower

def test_spaced_repetition_scheduling():
    q_id = 1
    session_id = "test-session-123"
    record_attempt(q_id, "C", True, session_id, response_time=4.5)
    with connect() as conn:
        sched = conn.execute("SELECT * FROM review_schedule WHERE question_id=?", (q_id,)).fetchone()
        assert sched is not None
        assert sched["interval_days"] >= 1
        assert sched["last_result"] == 1

def test_dashboard_metrics():
    m_all = get_dashboard_metrics("All months")
    assert m_all["questions"] >= 16
    assert m_all["attempts"] >= 12

    m_aug = get_dashboard_metrics("August", 2026)
    assert m_aug["questions"] >= 16
