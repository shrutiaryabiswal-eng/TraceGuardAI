# TraceGuard AI

**TraceGuard AI** is an evidence-grounded IT incident investigation prototype that helps organize incident reports, predict a likely incident category, retrieve related runbook evidence, and flag uncertain results for human review.

> **Prototype notice:** This project is an educational prototype. Its classifier and sample runbooks are not production-validated. It does not autonomously remediate incidents or replace a qualified incident responder.

## Features

- **Incident classification:** Predicts a likely incident category from the incident description.
- **Evidence retrieval:** Surfaces potentially relevant runbook references to support investigation.
- **Confidence-aware workflow:** Flags lower-confidence predictions for human review.
- **Incident history:** Saves investigation records in a local SQLite database.
- **Human review:** Allows a reviewer to record a review status and notes.
- **Automated tests:** Includes tests for investigation logic, database behavior, and the review workflow.

## How it works

1. Enter an IT incident description.
2. The text classifier predicts a likely category and confidence score.
3. The application retrieves related runbook evidence.
4. Lower-confidence results can be flagged for review.
5. The investigation is stored locally so it can be viewed in incident history and reviewed by a human.

## Technology stack

- Python
- Streamlit
- pandas
- scikit-learn
- SQLite
- pytest

## Project structure

```text
TraceGuardAI/
├── app.py
├── src/
│   ├── __init__.py
│   ├── database.py
│   └── investigation.py
├── tests/
│   ├── test_database.py
│   ├── test_investigation.py
│   └── test_review_workflow.py
├── data/              # Local data/database; database files are ignored by Git
├── docs/              # Project documentation, if present
├── models/            # Model artifacts, if present
├── .gitignore
├── README.md
└── requirements.txt
```

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/shrutiaryabiswal-eng/TraceGuardAI.git
cd TraceGuardAI
```

### 2. Create and activate a virtual environment

**Windows PowerShell:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Git Bash:**

```bash
python -m venv .venv
source .venv/Scripts/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run the app

```bash
python -m streamlit run app.py
```

Streamlit will print a local URL, usually `http://localhost:8501`, which you can open in your browser.

## Run tests

From the project root, run:

```bash
PYTHONPATH=. python -m pytest -q
```

The latest recorded test result during development was **14 passed**. Run the tests on your current checkout to confirm its present status.

## Data and security notes

- The local SQLite database is intentionally excluded from Git so personal/test incident records are not committed.
- Do not commit passwords, API keys, tokens, `.env` files, or real sensitive incident data.
- Use synthetic or sanitized incident descriptions for demonstrations.
- Treat model predictions and retrieved runbook matches as decision support, not authoritative conclusions.
- Human review is important, especially when confidence is low or evidence is incomplete.

## Author

**Shrutiarya Biswal**

GitHub: [@shrutiaryabiswal-eng](https://github.com/shrutiaryabiswal-eng)

Repository: [TraceGuardAI](https://github.com/shrutiaryabiswal-eng/TraceGuardAI)
