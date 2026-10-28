
import sqlite3

import pytest

from src.database import (
    get_connection,
    initialize_database,
    save_review,
    get_review_status,
    get_review_history,
)


@pytest.fixture
def test_incident():
    """Create a temporary test incident in the project database."""
    initialize_database()

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
                "Test incident for review workflow",
                "Database",
                0.40,
                1,
                "RB-002",
                "Low classifier score",
            ),
        )
        incident_id = cursor.lastrowid

    yield incident_id

    # Clean up only this test incident and its related review records.
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM review_audit_log WHERE incident_id = ?",
            (incident_id,),
        )
        connection.execute(
            "DELETE FROM incident_reviews WHERE incident_id = ?",
            (incident_id,),
        )
        connection.execute(
            "DELETE FROM incidents WHERE id = ?",
            (incident_id,),
        )


def test_review_defaults_to_pending(test_incident):
    review = get_review_status(test_incident)

    assert review["status"] == "Pending"
    assert review["reviewer_name"] == ""


def test_save_review_and_audit_history(test_incident):
    save_review(
        test_incident,
        "Reviewed",
        "Test Reviewer",
        "Checked the database runbook.",
    )

    review = get_review_status(test_incident)
    audit = get_review_history(test_incident)

    assert review["status"] == "Reviewed"
    assert review["reviewer_name"] == "Test Reviewer"
    assert len(audit) == 1
    assert audit[0]["notes"] == "Checked the database runbook."


def test_review_changes_are_audited(test_incident):
    save_review(
        test_incident,
        "Reviewed",
        "Test Reviewer",
        "Initial investigation completed.",
    )

    save_review(
        test_incident,
        "Escalated",
        "Test Reviewer",
        "Requires senior investigation.",
    )

    assert get_review_status(test_incident)["status"] == "Escalated"
    assert len(get_review_history(test_incident)) == 2


def test_invalid_status_is_rejected(test_incident):
    with pytest.raises(ValueError):
        save_review(
            test_incident,
            "Closed",
            "Test Reviewer",
            "Invalid status test.",
        )


def test_missing_reviewer_is_rejected(test_incident):
    with pytest.raises(ValueError):
        save_review(
            test_incident,
            "Reviewed",
            "",
            "Reviewer is missing.",
        )
