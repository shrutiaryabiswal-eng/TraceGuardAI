
"""SQLite storage for TraceGuard AI incident history and human reviews."""

import sqlite3
from pathlib import Path


# --------------------------------------------------
# Database configuration
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "traceguard.db"

REVIEW_STATUSES = {"Pending", "Reviewed", "Escalated"}


# --------------------------------------------------
# Database connection
# --------------------------------------------------

def get_connection():
    """Open a database connection and ensure its folder exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


# --------------------------------------------------
# Database initialization and safe migrations
# --------------------------------------------------

def initialize_database():
    """Create tables and safely upgrade existing databases."""

    with get_connection() as connection:

        # Existing incident table: preserve all existing records.
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                confidence REAL NOT NULL,
                needs_review INTEGER NOT NULL,
                evidence_ids TEXT NOT NULL,
                review_reason TEXT NOT NULL DEFAULT ''
            )
            """
        )

        # Safely add review_reason to older installations.
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(incidents)"
            ).fetchall()
        }

        if "review_reason" not in columns:
            connection.execute(
                """
                ALTER TABLE incidents
                ADD COLUMN review_reason TEXT NOT NULL DEFAULT ''
                """
            )

        # Stores the current review state for each incident.
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS incident_reviews (
                incident_id INTEGER PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'Pending'
                    CHECK(status IN ('Pending', 'Reviewed', 'Escalated')),
                reviewer_name TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (incident_id)
                    REFERENCES incidents(id)
                    ON DELETE CASCADE
            )
            """
        )

        # Append-only history of review decisions.
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS review_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER NOT NULL,
                status TEXT NOT NULL
                    CHECK(status IN ('Pending', 'Reviewed', 'Escalated')),
                reviewer_name TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (incident_id)
                    REFERENCES incidents(id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_review_audit_incident
            ON review_audit_log(incident_id, id DESC)
            """
        )


# --------------------------------------------------
# Save an incident investigation
# --------------------------------------------------

def save_incident(result, evidence, review_reason=""):
    """Save an investigation and return its database ID."""

    evidence_ids = ", ".join(
        item["id"] for item in evidence
    )

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO incidents (
                description,
                category,
                confidence,
                needs_review,
                evidence_ids,
                review_reason
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                result["description"],
                result["category"],
                result["confidence"],
                int(result["needs_review"]),
                evidence_ids,
                review_reason,
            ),
        )

        return cursor.lastrowid


# --------------------------------------------------
# Retrieve incident history
# --------------------------------------------------

def get_incident_history(limit=100):
    """Return the most recent incidents first."""

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM incidents
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def get_incident_by_id(incident_id):
    """Return one incident, or None if it does not exist."""

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM incidents
            WHERE id = ?
            """,
            (incident_id,),
        ).fetchone()

    return dict(row) if row else None


# --------------------------------------------------
# Human review workflow
# --------------------------------------------------

def save_review(
    incident_id,
    status,
    reviewer_name,
    notes="",
):
    """
    Save the current review state and append an audit entry.

    Valid statuses: Pending, Reviewed, Escalated.
    Each save creates a separate audit record.
    """

    if status not in REVIEW_STATUSES:
        raise ValueError(
            f"Invalid status. Choose one of: "
            f"{', '.join(sorted(REVIEW_STATUSES))}"
        )

    reviewer_name = str(reviewer_name).strip()
    notes = str(notes).strip()

    if not reviewer_name:
        raise ValueError("Please enter the reviewer's name.")

    if len(reviewer_name) > 100:
        raise ValueError("Reviewer name must be 100 characters or fewer.")

    if len(notes) > 5000:
        raise ValueError("Review notes must be 5000 characters or fewer.")

    with get_connection() as connection:

        # Validate that the incident exists.
        incident = connection.execute(
            "SELECT id FROM incidents WHERE id = ?",
            (incident_id,),
        ).fetchone()

        if incident is None:
            raise ValueError(
                f"Incident ID {incident_id} does not exist."
            )

        # Update the latest review state.
        connection.execute(
            """
            INSERT INTO incident_reviews (
                incident_id,
                status,
                reviewer_name,
                notes,
                updated_at
            )
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(incident_id) DO UPDATE SET
                status = excluded.status,
                reviewer_name = excluded.reviewer_name,
                notes = excluded.notes,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                incident_id,
                status,
                reviewer_name,
                notes,
            ),
        )

        # Append a separate audit event.
        connection.execute(
            """
            INSERT INTO review_audit_log (
                incident_id,
                status,
                reviewer_name,
                notes
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                incident_id,
                status,
                reviewer_name,
                notes,
            ),
        )


def get_review_status(incident_id):
    """Get the latest review state, defaulting to Pending."""

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM incident_reviews
            WHERE incident_id = ?
            """,
            (incident_id,),
        ).fetchone()

    if row:
        return dict(row)

    return {
        "incident_id": incident_id,
        "status": "Pending",
        "reviewer_name": "",
        "notes": "",
        "updated_at": None,
    }



def get_all_review_statuses():
    """Return every incident with its current human-review status."""
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT
                i.id AS id,
                i.category AS category,
                i.description AS description,
                COALESCE(r.status, 'Pending') AS status,
                COALESCE(r.reviewer_name, '') AS reviewer_name,
                COALESCE(r.notes, '') AS notes
            FROM incidents AS i
            LEFT JOIN incident_reviews AS r
                ON i.id = r.incident_id
            ORDER BY i.id DESC
        """).fetchall()

    return [dict(row) for row in rows]



def get_review_history(incident_id):
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                id,
                incident_id,
                status,
                reviewer_name,
                notes,
                recorded_at
            FROM review_audit_log
            WHERE incident_id = ?
            ORDER BY recorded_at DESC, id DESC
            """,
            (incident_id,),
        )

        rows = cursor.fetchall()
        columns = [
            column[0] for column in cursor.description
        ]

        return [
            dict(zip(columns, row))
            for row in rows
        ]

    finally:
        conn.close()

    return [dict(row) for row in rows]
