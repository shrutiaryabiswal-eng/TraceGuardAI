
import pytest

from src.investigation import (
    build_classifier,
    classify_incident,
    retrieve_evidence,
    validate_description,
)


@pytest.fixture
def classifier():
    return build_classifier()


def test_rejects_empty_description():
    with pytest.raises(ValueError):
        validate_description("   ")


def test_rejects_short_description():
    with pytest.raises(ValueError):
        validate_description("error")


def test_normalizes_whitespace():
    assert validate_description(
        "  Database   connection failed  "
    ) == "Database connection failed"


def test_classifier_returns_expected_fields(classifier):
    vectorizer, model = classifier

    result = classify_incident(
        "The database connection is failing with timeouts.",
        vectorizer,
        model,
    )

    assert result["category"] in model.classes_
    assert 0.0 <= result["confidence"] <= 1.0
    assert isinstance(result["needs_review"], bool)
    assert "review_reason" in result


def test_classifier_includes_review_reason_for_low_confidence(classifier):
    vectorizer, model = classifier

    result = classify_incident(
        "The office printer is making an unusual sound",
        vectorizer,
        model,
    )

    assert isinstance(result["review_reason"], str)

    if result["needs_review"]:
        assert result["review_reason"]


def test_retrieval_returns_source_ids():
    evidence = retrieve_evidence(
        "Database connection timeout and connection pool exhausted"
    )

    assert evidence
    assert all(item["id"].startswith("RB-") for item in evidence)


def test_unrelated_description_has_no_evidence():
    evidence = retrieve_evidence(
        "The office printer is making an unusual sound"
    )

    assert evidence == []
