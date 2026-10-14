# 📚 Current Affairs Exam Prep

A modern, interactive MCQ quiz app for IBPS/banking exam preparation, built with Streamlit.

**Live App → [Open on Streamlit Cloud](https://your-app-url.streamlit.app)**

---

## Features

- 📝 **172 high-quality MCQs** from September 2026 AffairsCloud PDFs
- 🗂️ **Topic-wise filtering** — Economy, Defence, Environment, Sports & more
- 📊 **Dashboard metrics** — accuracy, attempts, weak areas
- 🔁 **Spaced repetition** — review questions you got wrong
- 💡 **Explanations & memory tips** for every question
- 🌙 **Dark mode** premium UI

## Topics Covered

| Topic | Questions |
|---|---|
| National Affairs & Governance | 56 |
| Economy, Banking & Finance | 40 |
| Science, Technology & Space | 19 |
| Environment, Ecology & Agriculture | 16 |
| Defence, Exercises & Security | 12 |
| International Affairs & Summits | 10 |
| Sports & Cultural Events | 8 |
| Awards, Honors & Rankings | 6 |
| Appointments, Resignations & Committees | 5 |

## Run Locally

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/current-affairs-exam-prep.git
cd current-affairs-exam-prep

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
streamlit run app.py
```

The database auto-seeds from `claude_questions.txt` on first launch — no manual setup needed.

## Tech Stack

- **Python 3.11+**
- **Streamlit** — UI framework
- **SQLite** — local database
- **PyMuPDF** — PDF text extraction
- **Pandas** — data analytics

## Deploying to Streamlit Community Cloud

1. Push this repo to GitHub (public or private)
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click **New app** → connect your GitHub repo
4. Set **Main file path** to `app.py`
5. Click **Deploy!**

The app auto-initializes the database from the bundled question bank on every cold start.
