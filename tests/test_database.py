
import src.database as database


def test_initialize_database_creates_table(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")

    database.initialize_database()

    with database.get_connection() as connection:
        row = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'incidents'
            """
        ).fetchone()

    assert row is not None


def test_save_and_retrieve_incident(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")

    database.initialize_database()

    result = {
        "description": "Database connections are timing out",
        "category": "Database",
        "confidence": 0.82,
        "needs_review": False,
    }

    evidence = [{"id": "DB-01"}]

    record_id = database.save_incident(result, evidence)
    history = database.get_incident_history()

    assert record_id == 1
    assert len(history) == 1
    assert history[0]["description"] == result["description"]
    assert history[0]["category"] == "Database"
    assert history[0]["evidence_ids"] == "DB-01"
    assert history[0]["needs_review"] == 0
