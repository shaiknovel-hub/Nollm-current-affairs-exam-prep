import uuid
import json
import time
from datetime import datetime
from pathlib import Path
import streamlit as st
import pandas as pd

from src.database import init_db, connect, get_available_months, get_dashboard_metrics
from src.quiz_engine import (
    get_questions,
    record_attempt,
    start_quiz_session,
    finish_quiz_session,
    get_mistakes_detailed,
    get_topic_analytics,
    get_recent_sessions
)
from src.pdf_processor import (
    extract_pdf_data,
    ingest_directory_pdfs,
    get_imported_documents,
    get_extracted_text,
    PDF_DIR
)
from src.question_generator import (
    generate_questions_for_document,
    get_candidate_questions,
    update_candidate_question,
    bulk_set_approval_status,
    EXAM_TOPICS
)

# ---------------------------------------------------------
# Page Configuration & CSS Styling
# ---------------------------------------------------------
st.set_page_config(
    page_title="Current Affairs Exam Prep",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

init_db()

# Custom CSS for modern, premium styling
st.markdown("""
<style>
    /* Metric Card Styling */
    .metric-card {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.05) 0%, rgba(255, 255, 255, 0.02) 100%);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
        border-color: rgba(64, 158, 255, 0.4);
        transform: translateY(-2px);
    }
    .metric-title {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #888888;
        margin-bottom: 6px;
    }
    .metric-val {
        font-size: 1.8rem;
        font-weight: 700;
        color: #409eff;
        margin-bottom: 2px;
    }
    .metric-sub {
        font-size: 0.8rem;
        color: #666666;
    }

    /* Badges */
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 14px;
        font-size: 0.78rem;
        font-weight: 600;
        margin-right: 6px;
    }
    .badge-topic { background-color: #2b4360; color: #a5d8ff; }
    .badge-month { background-color: #3b3a2a; color: #ffe066; }
    .badge-diff-easy { background-color: #1e3a2f; color: #69db7c; }
    .badge-diff-med { background-color: #3d3419; color: #ffd43b; }
    .badge-diff-hard { background-color: #3b1d1d; color: #ff8787; }
    .badge-source { background-color: #2a2a2a; color: #ced4da; }

    /* Flashcard / Question box */
    .question-box {
        background-color: rgba(255, 255, 255, 0.03);
        border-left: 4px solid #409eff;
        border-radius: 0 8px 8px 0;
        padding: 16px 20px;
        margin: 14px 0;
    }
    .explanation-box {
        background-color: rgba(76, 175, 80, 0.08);
        border: 1px solid rgba(76, 175, 80, 0.25);
        border-radius: 8px;
        padding: 14px 18px;
        margin-top: 12px;
    }
    .memory-cue-box {
        background-color: rgba(255, 193, 7, 0.1);
        border: 1px solid rgba(255, 193, 7, 0.3);
        border-radius: 8px;
        padding: 12px 16px;
        margin-top: 10px;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Sidebar: Month Selector & System Scope
# ---------------------------------------------------------
available_months = get_available_months()
month_labels = [m["label"] for m in available_months] + ["All months"]

# Default to September 2026 if available, else first option
default_idx = 0
if "September 2026" in month_labels:
    default_idx = month_labels.index("September 2026")

with st.sidebar:
    st.title("📚 Exam Prep")
    st.caption("Month-wise Current Affairs System")
    st.markdown("---")

    st.subheader("🗓️ Select Month")
    selected_month_label = st.selectbox(
        "Active Study Month:",
        options=month_labels,
        index=default_idx,
        help="Filters questions, dashboard stats, mistake workbook, and mock tests strictly to the chosen month."
    )

    if selected_month_label == "All months":
        curr_month = "All months"
        curr_year = None
    else:
        m_parts = selected_month_label.split(" ")
        curr_month = m_parts[0]
        curr_year = int(m_parts[1]) if len(m_parts) > 1 else 2026

    st.info(f"**Current Scope:** {selected_month_label}\n\n*Offline SQLite question bank · Zero API calls during tests.*")
    st.markdown("---")

# ---------------------------------------------------------
# Top Dashboard Metrics
# ---------------------------------------------------------
metrics = get_dashboard_metrics(curr_month, curr_year)

col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.title("🎯 Current Affairs Preparation Studio")
    st.markdown(f"**Study Target:** `{selected_month_label}` · High-yield factual MCQs, grounded explanations & Spaced Repetition.")
with col_h2:
    st.write("")
    st.caption("Local & Offline Database")

m_c1, m_c2, m_c3, m_c4, m_c5, m_c6 = st.columns(6)

with m_c1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Approved MCQs</div>
        <div class="metric-val">{metrics['questions']}</div>
        <div class="metric-sub">In question bank</div>
    </div>
    """, unsafe_allow_html=True)

with m_c2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Topics Covered</div>
        <div class="metric-val">{metrics['topics']}</div>
        <div class="metric-sub">Factual domains</div>
    </div>
    """, unsafe_allow_html=True)

with m_c3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Attempts</div>
        <div class="metric-val">{metrics['attempts']}</div>
        <div class="metric-sub">Questions answered</div>
    </div>
    """, unsafe_allow_html=True)

with m_c4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Accuracy Rate</div>
        <div class="metric-val">{metrics['accuracy']:.1f}%</div>
        <div class="metric-sub">Overall performance</div>
    </div>
    """, unsafe_allow_html=True)

with m_c5:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Questions Missed</div>
        <div class="metric-val" style="color: #ff6b6b;">{metrics['wrong_count']}</div>
        <div class="metric-sub">Need review</div>
    </div>
    """, unsafe_allow_html=True)

with m_c6:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Due for Review</div>
        <div class="metric-val" style="color: #fcc419;">{metrics['due_count']}</div>
        <div class="metric-sub">Spaced Repetition</div>
    </div>
    """, unsafe_allow_html=True)

st.write("")

# ---------------------------------------------------------
# Tabbed Navigation
# ---------------------------------------------------------
tab_test, tab_mistakes, tab_analytics, tab_ingest, tab_studio = st.tabs([
    "📝 Practice & Mock Tests",
    "🔁 Mistake Review & SRS",
    "📊 Performance Analytics",
    "📥 Document Ingestion",
    "⚡ Question Studio & Approval"
])

# =========================================================
# TAB 1: PRACTICE & MOCK TESTS
# =========================================================
with tab_test:
    # Fetch available topics for current month
    with connect() as conn:
        q_filter = "WHERE approval_status='approved' AND topic IS NOT NULL"
        params_t = []
        if curr_month != "All months":
            q_filter += " AND month = ? AND year = ?"
            params_t.extend([curr_month, curr_year])
        
        db_topics = [r["topic"] for r in conn.execute(
            f"SELECT DISTINCT topic FROM questions {q_filter} ORDER BY topic",
            params_t
        ).fetchall()]
    
    test_topics = ["All topics"] + db_topics

    # Test Configuration Controls
    with st.expander("⚙️ Configure Practice / Mock Test", expanded=("quiz_questions" not in st.session_state)):
        tc1, tc2, tc3, tc4 = st.columns([2, 2, 2, 2])
        with tc1:
            test_mode = st.selectbox(
                "Test Mode:",
                ["All approved questions", "Mistakes only", "Due for review", "Weak topics"],
                help="Choose which subset of questions to practice."
            )
        with tc2:
            test_topic = st.selectbox("Topic Filter:", test_topics)
        with tc3:
            max_q = max(1, metrics['questions'])
            test_count = st.number_input("Question Count:", min_value=1, max_value=max_q, value=min(10, max_q))
        with tc4:
            st.write("")
            st.write("")
            start_btn = st.button("🚀 Start / Restart Test", type="primary", use_container_width=True)

        if start_btn:
            selected_qs = get_questions(
                mode=test_mode,
                limit=test_count,
                topic=test_topic,
                month=curr_month,
                year=curr_year
            )
            if not selected_qs:
                st.warning(f"No questions match '{test_mode}' for topic '{test_topic}' in {selected_month_label}.")
            else:
                sess_id = str(uuid.uuid4())
                st.session_state.quiz_questions = selected_qs
                st.session_state.quiz_index = 0
                st.session_state.quiz_answers = {}
                st.session_state.quiz_session_id = sess_id
                st.session_state.quiz_finished = False
                st.session_state.quiz_start_time = time.time()
                st.session_state.quiz_q_start_time = time.time()
                start_quiz_session(sess_id, test_mode, curr_month or "All", curr_year or 0, test_topic, len(selected_qs))
                st.rerun()

    # --- Quiz Execution Interface ---
    if "quiz_questions" in st.session_state and st.session_state.quiz_questions:
        questions = st.session_state.quiz_questions
        idx = st.session_state.get("quiz_index", 0)
        answers = st.session_state.get("quiz_answers", {})
        is_finished = st.session_state.get("quiz_finished", False)

        # 1. Test Completion Screen
        if is_finished or idx >= len(questions):
            correct_cnt = sum(1 for v in answers.values() if v.get("correct", False))
            total_answered = len(questions)
            score_pct = (correct_cnt / total_answered * 100) if total_answered > 0 else 0.0

            finish_quiz_session(st.session_state.quiz_session_id, correct_cnt, total_answered)

            st.success("🎉 Test Completed!")
            sc1, sc2, sc3, sc4 = st.columns(4)
            sc1.metric("Final Score", f"{correct_cnt} / {total_answered}", f"{score_pct:.1f}%")
            sc2.metric("Correct Answers", correct_cnt)
            sc3.metric("Incorrect Answers", total_answered - correct_cnt)
            
            elapsed = time.time() - st.session_state.get("quiz_start_time", time.time())
            sc4.metric("Time Taken", f"{int(elapsed // 60)}m {int(elapsed % 60)}s")

            st.write("---")
            st.subheader("📋 Comprehensive Question Review")

            for i, q in enumerate(questions, 1):
                ans = answers.get(q["question_id"])
                user_selected = ans["selected"] if ans else "Not answered"
                is_correct = ans["correct"] if ans else False

                with st.expander(f"Question {i}: {q['question_text'][:80]}... — {'✅ Correct' if is_correct else '❌ Incorrect'}", expanded=not is_correct):
                    diff_class = f"badge-diff-{q.get('difficulty', 'med')[:4]}"
                    st.markdown(f"""
                        <span class="badge badge-topic">{q.get('topic', 'General')}</span>
                        <span class="badge badge-month">{q.get('month', '')} {q.get('year', '')}</span>
                        <span class="badge {diff_class}">{q.get('difficulty', 'medium').capitalize()}</span>
                        <span class="badge badge-source">Source: {q.get('source_filename', 'Doc')} · Page {q.get('page_number', '—')}</span>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(f"#### {q['question_text']}")
                    
                    for letter, opt_text in q["options"].items():
                        prefix = "🔘"
                        if letter == q["correct_option"]:
                            prefix = "✅ **Correct:**"
                        elif letter == user_selected:
                            prefix = "❌ **Your Answer:**"
                        st.markdown(f"- {prefix} **{letter}.** {opt_text}")

                    if q.get("explanation"):
                        st.markdown(f"""
                        <div class="explanation-box">
                            <strong>📖 Grounded Explanation:</strong><br>{q['explanation']}
                        </div>
                        """, unsafe_allow_html=True)

                    if q.get("memory_cue"):
                        st.markdown(f"""
                        <div class="memory-cue-box">
                            🧠 <strong>High-Yield Memory Cue:</strong> {q['memory_cue']}
                        </div>
                        """, unsafe_allow_html=True)

            st.write("")
            rc1, rc2 = st.columns(2)
            with rc1:
                # Retry missed questions
                missed_qs = [q for q in questions if not answers.get(q["question_id"], {}).get("correct", False)]
                if missed_qs and st.button("🔄 Retry Missed Questions Only", type="primary", use_container_width=True):
                    sess_id = str(uuid.uuid4())
                    st.session_state.quiz_questions = missed_qs
                    st.session_state.quiz_index = 0
                    st.session_state.quiz_answers = {}
                    st.session_state.quiz_session_id = sess_id
                    st.session_state.quiz_finished = False
                    st.session_state.quiz_start_time = time.time()
                    st.session_state.quiz_q_start_time = time.time()
                    st.rerun()

            with rc2:
                if st.button("🏁 Start Fresh Practice Test", use_container_width=True):
                    for k in ["quiz_questions", "quiz_index", "quiz_answers", "quiz_session_id", "quiz_finished"]:
                        st.session_state.pop(k, None)
                    st.rerun()

        else:
            # 2. Live Question Answering View
            q = questions[idx]
            q_id = q["question_id"]
            progress_pct = (idx + 1) / len(questions)

            p_col1, p_col2 = st.columns([4, 1])
            with p_col1:
                st.progress(progress_pct, text=f"Question {idx + 1} of {len(questions)}")
            with p_col2:
                st.caption(f"Progress: {int(progress_pct*100)}%")

            # Badges header
            diff_class = f"badge-diff-{q.get('difficulty', 'med')[:4]}"
            st.markdown(f"""
                <span class="badge badge-topic">{q.get('topic', 'General')}</span>
                <span class="badge badge-month">{q.get('month', '')} {q.get('year', '')}</span>
                <span class="badge {diff_class}">{q.get('difficulty', 'medium').capitalize()}</span>
                <span class="badge badge-source">Source: {q.get('source_filename', 'Doc')} · Page {q.get('page_number', '—')}</span>
            """, unsafe_allow_html=True)

            # Question Text Box
            st.markdown(f"""
            <div class="question-box">
                <h3 style="margin: 0; font-weight: 600;">{q['question_text']}</h3>
            </div>
            """, unsafe_allow_html=True)

            if q.get("image_path"):
                st.image(q["image_path"], use_container_width=True)

            # Check if current question has already been answered
            ans_state = answers.get(q_id)

            if ans_state is None:
                # Option Radio Selection
                opt_labels = {k: f"{k}.  {v}" for k, v in q["options"].items()}
                selected_choice = st.radio(
                    "Select the best option:",
                    options=list(q["options"].keys()),
                    format_func=lambda k: opt_labels[k],
                    key=f"radio_q_{q_id}_{idx}"
                )

                st.write("")
                col_btn1, col_btn2 = st.columns([1, 4])
                with col_btn1:
                    if st.button("Check Answer", type="primary", use_container_width=True):
                        is_corr = (selected_choice == q["correct_option"])
                        elapsed_q = time.time() - st.session_state.get("quiz_q_start_time", time.time())
                        st.session_state.quiz_answers[q_id] = {
                            "selected": selected_choice,
                            "correct": is_corr,
                            "time": elapsed_q
                        }
                        record_attempt(q_id, selected_choice, is_corr, st.session_state.quiz_session_id, elapsed_q)
                        st.rerun()

            else:
                # Show results for this question
                user_sel = ans_state["selected"]
                is_corr = ans_state["correct"]

                if is_corr:
                    st.success(f"🎉 **Correct!** You selected **{user_sel}. {q['options'].get(user_sel, '')}**")
                else:
                    st.error(f"❌ **Incorrect.** You selected **{user_sel}. {q['options'].get(user_sel, '')}**")
                    st.info(f"✅ **Correct Answer:** **{q['correct_option']}. {q['options'].get(q['correct_option'], '')}**")

                if q.get("explanation"):
                    st.markdown(f"""
                    <div class="explanation-box">
                        <strong>📖 Source-Grounded Explanation:</strong><br>{q['explanation']}
                    </div>
                    """, unsafe_allow_html=True)

                if q.get("memory_cue"):
                    st.markdown(f"""
                    <div class="memory-cue-box">
                        🧠 <strong>Memory Cue:</strong> {q['memory_cue']}
                    </div>
                    """, unsafe_allow_html=True)

                st.write("")
                btn_txt = "Next Question ➡️" if (idx + 1 < len(questions)) else "Finish Test & View Score 🏁"
                if st.button(btn_txt, type="primary"):
                    if idx + 1 >= len(questions):
                        st.session_state.quiz_finished = True
                    else:
                        st.session_state.quiz_index += 1
                        st.session_state.quiz_q_start_time = time.time()
                    st.rerun()

    else:
        st.info("👈 Choose your test settings in the box above and click **'🚀 Start / Restart Test'** to begin practicing.")

# =========================================================
# TAB 2: MISTAKE REVIEW & SPACED REPETITION (SRS)
# =========================================================
with tab_mistakes:
    st.header("🔁 Mistake Workbook & Spaced Repetition (SRS)")
    st.caption("Targeted revision of questions you missed · Leitner automated intervals (1d → 3d → 7d → 14d)")

    mistakes_list = get_mistakes_detailed(curr_month, curr_year)

    if not mistakes_list:
        st.success(f"🌟 Great job! No recorded mistakes found for `{selected_month_label}`.")
    else:
        m_count = len(mistakes_list)
        st.warning(f"You have **{m_count} unique questions** needing review in `{selected_month_label}`.")

        # Interactive Flashcard / Drill Studio
        st.subheader("💡 Interactive Mistake Flashcards")
        
        # Topic selector within mistakes
        m_topics = ["All topics"] + sorted(list({m.get("topic") or "General" for m in mistakes_list}))
        sel_m_topic = st.selectbox("Filter Mistakes by Topic:", m_topics, key="sel_m_topic")

        filtered_mistakes = mistakes_list
        if sel_m_topic != "All topics":
            filtered_mistakes = [m for m in mistakes_list if (m.get("topic") or "General") == sel_m_topic]

        for i, m in enumerate(filtered_mistakes, 1):
            with st.expander(f"Mistake #{i}: [{m.get('topic', 'General')}] {m['question_text'][:80]}...", expanded=(i==1)):
                st.markdown(f"### {m['question_text']}")
                
                # SRS Details
                sc1, sc2, sc3, sc4 = st.columns(4)
                sc1.caption(f"**Lapses (Missed):** {m.get('lapse_count', 1)} times")
                sc2.caption(f"**Current Interval:** {m.get('interval_days', 1)} days")
                sc3.caption(f"**Streak:** {m.get('consecutive_correct', 0)} correct")
                sc4.caption(f"**Next Review Due:** {m.get('next_review_at', 'Now')}")

                # Show options
                for letter, opt in m["options"].items():
                    is_correct_opt = (letter == m["correct_option"])
                    color_style = "color: #69db7c; font-weight: bold;" if is_correct_opt else ""
                    st.markdown(f"- <span style='{color_style}'>**{letter}.** {opt}</span>", unsafe_allow_html=True)

                if m.get("explanation"):
                    st.markdown(f"""
                    <div class="explanation-box">
                        <strong>📖 Source Citation & Explanation:</strong><br>{m['explanation']}
                    </div>
                    """, unsafe_allow_html=True)

                if m.get("memory_cue"):
                    st.markdown(f"""
                    <div class="memory-cue-box">
                        🧠 <strong>Key Memory Cue:</strong> {m['memory_cue']}
                    </div>
                    """, unsafe_allow_html=True)

                st.caption(f"Source: {m.get('source_filename', 'N/A')} · Page {m.get('page_number', '—')}")

# =========================================================
# TAB 3: PERFORMANCE ANALYTICS & WEAK AREAS
# =========================================================
with tab_analytics:
    st.header("📊 Performance Analytics & Topic Mastery")
    st.caption("Detailed diagnostics of factual retention and weak topic identification")

    analytics_data = get_topic_analytics(curr_month, curr_year)

    if not analytics_data:
        st.info("No attempt records yet for this selection. Take a mock test to view analytics!")
    else:
        # Convert to DataFrame
        df_topics = pd.DataFrame(analytics_data)

        # Highlight weak areas (< 60% accuracy)
        weak_topics = df_topics[df_topics["total_attempts"] > 0]
        weak_topics = weak_topics[weak_topics["accuracy"] < 60.0]

        if not weak_topics.empty:
            st.error(f"⚠️ **Focus Revision Needed:** You scored under 60% in: **{', '.join(weak_topics['topic'].tolist())}**")

        st.subheader("Topic-wise Mastery Breakdown")
        
        # Display progress bars per topic
        for _, row in df_topics.iterrows():
            top_col1, top_col2, top_col3 = st.columns([3, 4, 1])
            with top_col1:
                st.markdown(f"**{row['topic']}**")
                st.caption(f"{row['total_questions']} questions · {row['total_attempts']} attempts")
            with top_col2:
                acc = row["accuracy"]
                # Color code
                st.progress(acc / 100.0)
            with top_col3:
                st.markdown(f"**{row['accuracy']:.1f}%**")
            st.write("---")

        # Recent Sessions Log
        st.subheader("🕒 Recent Mock Test Sessions")
        recent = get_recent_sessions(8)
        if recent:
            df_sess = pd.DataFrame(recent)[["completed_at", "mode", "month", "topic", "total_questions", "correct_count", "accuracy"]]
            df_sess.columns = ["Completed", "Mode", "Month", "Topic", "Questions", "Correct", "Accuracy %"]
            st.dataframe(df_sess, use_container_width=True)

# =========================================================
# TAB 4: DOCUMENT INGESTION (PDF EXTRACTION)
# =========================================================
with tab_ingest:
    st.header("📥 Document Ingestion & PyMuPDF Extraction")
    st.caption("Extract factual current affairs directly from local PDFs · 100% offline · Content-hash deduplication")

    ing_col1, ing_col2 = st.columns([1, 1])

    with ing_col1:
        st.subheader("1. Upload PDF Files")
        st.write("Upload your September (or other month) current affairs PDFs directly here:")
        uploaded_files = st.file_uploader(
            "Select one or multiple PDF documents:",
            type=["pdf"],
            accept_multiple_files=True
        )

        up_month = st.selectbox("Assign Month:", ["September", "August", "October", "November", "December", "January", "February", "March", "April", "May", "June", "July"], index=0, key="up_month")
        up_year = st.number_input("Assign Year:", min_value=2024, max_value=2030, value=2026, key="up_year")

        if uploaded_files and st.button("📥 Process Uploaded PDFs", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            success_cnt = 0
            dup_cnt = 0
            scanned_pages_cnt = 0

            for i, f in enumerate(uploaded_files):
                status_text.text(f"Extracting {f.name} ({i+1}/{len(uploaded_files)})...")
                raw_bytes = f.read()
                res = extract_pdf_data(raw_bytes, f.name, up_month, up_year)
                
                if res["status"] == "success":
                    success_cnt += 1
                    scanned_pages_cnt += len(res.get("scanned_pages", []))
                elif res["status"] == "duplicate":
                    dup_cnt += 1

                progress_bar.progress((i + 1) / len(uploaded_files))

            status_text.empty()
            st.success(f"Processing Complete! ✅ {success_cnt} extracted, 🔁 {dup_cnt} duplicate(s) skipped.")
            if scanned_pages_cnt > 0:
                st.warning(f"⚠️ {scanned_pages_cnt} page(s) had sparse text and may be scanned or image-based.")
            st.rerun()

    with ing_col2:
        st.subheader("2. Batch Scan `data/pdfs/` Folder")
        st.write(f"Or drop PDF files into the directory: `{PDF_DIR}` and trigger batch processing:")
        
        folder_month = st.selectbox("Folder Target Month:", ["September", "August", "October", "November"], index=0, key="f_month")
        folder_year = st.number_input("Folder Target Year:", min_value=2024, max_value=2030, value=2026, key="f_year")

        if st.button("📁 Ingest All PDFs from data/pdfs/"):
            with st.spinner("Processing local PDFs..."):
                results = ingest_directory_pdfs(PDF_DIR, folder_month, folder_year)
                st.write("---")
                st.markdown(f"**Total Files Scanned:** {results['total_files']}")
                st.markdown(f"**Successfully Extracted:** {len(results['successful'])}")
                st.markdown(f"**Duplicates Skipped:** {len(results['duplicates'])}")
                st.markdown(f"**Total Pages Extracted:** {results['total_pages']}")
                if results['scanned_pages_detected'] > 0:
                    st.warning(f"**Scanned/Sparse Pages Detected:** {results['scanned_pages_detected']}")
            st.rerun()

    st.write("---")
    st.subheader("📚 Imported Document Library")
    imported_docs = get_imported_documents(curr_month, curr_year)
    
    if not imported_docs:
        st.info("No documents imported yet for this month. Upload PDFs above to begin.")
    else:
        df_docs = pd.DataFrame(imported_docs)[["document_id", "filename", "month", "year", "page_count", "processing_status"]]
        df_docs.columns = ["ID", "Filename", "Month", "Year", "Pages", "Status"]
        st.dataframe(df_docs, use_container_width=True)

        # Extracted Text Inspector
        with st.expander("🔍 View Extracted Text for Document"):
            doc_choice = st.selectbox(
                "Choose document to preview extracted text:",
                options=imported_docs,
                format_func=lambda d: f"{d['filename']} ({d['month']} {d['year']})"
            )
            if doc_choice:
                text_content = get_extracted_text(doc_choice["document_id"])
                if text_content:
                    st.text_area("Extracted Text Preview:", text_content[:5000], height=300)
                    st.caption(f"Total extracted character count: {len(text_content):,}")
                else:
                    st.warning("Extracted text file not found.")

# =========================================================
# TAB 5: QUESTION STUDIO & APPROVAL
# =========================================================
with tab_studio:
    st.header("⚡ Question Studio & Approval Pipeline")
    st.caption("Generate exam MCQs from extracted documents, review candidate questions, edit, and approve into quiz bank.")

    st.subheader("1. Generate Candidate Questions from Documents")
    all_docs = get_imported_documents(curr_month, curr_year)
    
    if not all_docs:
        st.warning("Please import at least one PDF in the 'Document Ingestion' tab first.")
    else:
        gen_c1, gen_c2, gen_c3 = st.columns([3, 2, 2])
        with gen_c1:
            sel_gen_doc = st.selectbox(
                "Select Document to Generate Questions From:",
                options=all_docs,
                format_func=lambda d: f"{d['filename']} ({d['month']} {d['year']} · {d['page_count']} pages)"
            )
        with gen_c2:
            max_cand = st.number_input("Max Questions to Generate:", min_value=1, max_value=50, value=15)
        with gen_c3:
            st.write("")
            st.write("")
            if st.button("⚡ Generate Candidate MCQs", type="primary", use_container_width=True):
                with st.spinner("Analyzing factual statements and creating MCQs..."):
                    gen_res = generate_questions_for_document(
                        sel_gen_doc["document_id"],
                        sel_gen_doc["month"],
                        sel_gen_doc["year"],
                        max_questions=max_cand
                    )
                    st.success(f"Generated {gen_res.get('generated', 0)} candidates ({gen_res.get('saved_to_review', 0)} new saved to review).")
                st.rerun()

    st.write("---")
    st.subheader("2. Candidate Approval Studio")

    status_filter = st.selectbox("Status Filter:", ["pending_review", "approved", "rejected"], index=0)
    candidates = get_candidate_questions(status_filter, curr_month, curr_year)

    st.markdown(f"Found **{len(candidates)}** question(s) in `{status_filter}` state.")

    if candidates and status_filter == "pending_review":
        if st.button("⚡ Bulk Approve All Pending Questions", type="primary"):
            approved_n = bulk_set_approval_status("approved", curr_month, curr_year, "pending_review")
            st.success(f"Successfully approved and published {approved_n} questions to the active question bank!")
            st.rerun()

    st.write("")

    # Card by Card Candidate Review
    for idx, c in enumerate(candidates, 1):
        q_id = c["question_id"]
        with st.expander(f"#{idx} [{c.get('topic', 'General')}] {c['question_text'][:70]}...", expanded=(idx==1)):
            with st.form(key=f"edit_form_{q_id}"):
                f_text = st.text_area("Question Text:", value=c["question_text"])
                
                f_top = st.selectbox("Topic:", EXAM_TOPICS, index=EXAM_TOPICS.index(c["topic"]) if c["topic"] in EXAM_TOPICS else 0)
                f_diff = st.selectbox("Difficulty:", ["easy", "medium", "hard"], index=["easy", "medium", "hard"].index(c.get("difficulty", "medium")))
                
                # Options
                opts = c.get("options", {})
                oc1, oc2 = st.columns(2)
                with oc1:
                    opt_a = st.text_input("Option A:", value=opts.get("A", ""))
                    opt_b = st.text_input("Option B:", value=opts.get("B", ""))
                with oc2:
                    opt_c = st.text_input("Option C:", value=opts.get("C", ""))
                    opt_d = st.text_input("Option D:", value=opts.get("D", ""))

                f_correct = st.selectbox("Correct Option:", ["A", "B", "C", "D"], index=["A", "B", "C", "D"].index(c["correct_option"]))
                f_exp = st.text_area("Source Grounded Explanation:", value=c.get("explanation", ""))
                f_cue = st.text_input("Memory Cue:", value=c.get("memory_cue", ""))

                fc1, fc2, fc3 = st.columns(3)
                with fc1:
                    approve_submit = st.form_submit_button("✅ Approve & Publish", type="primary", use_container_width=True)
                with fc2:
                    reject_submit = st.form_submit_button("❌ Reject", use_container_width=True)
                with fc3:
                    save_submit = st.form_submit_button("💾 Save Edits Only", use_container_width=True)

                if approve_submit:
                    update_candidate_question(
                        q_id, f_text,
                        {"A": opt_a, "B": opt_b, "C": opt_c, "D": opt_d},
                        f_correct, f_top, f_diff, f_exp, f_cue,
                        "approved"
                    )
                    st.success(f"Question #{q_id} approved!")
                    st.rerun()

                elif reject_submit:
                    update_candidate_question(
                        q_id, f_text,
                        {"A": opt_a, "B": opt_b, "C": opt_c, "D": opt_d},
                        f_correct, f_top, f_diff, f_exp, f_cue,
                        "rejected"
                    )
                    st.warning(f"Question #{q_id} rejected.")
                    st.rerun()

                elif save_submit:
                    update_candidate_question(
                        q_id, f_text,
                        {"A": opt_a, "B": opt_b, "C": opt_c, "D": opt_d},
                        f_correct, f_top, f_diff, f_exp, f_cue,
                        status_filter
                    )
                    st.info(f"Changes saved for question #{q_id}.")
                    st.rerun()
