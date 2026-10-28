
"""Core investigation logic for TraceGuard AI.

This is an illustrative baseline, not a production-validated AI model.
Use predictions and retrieved runbooks to support human investigation.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics.pairwise import cosine_similarity


MIN_DESCRIPTION_LENGTH = 12
MIN_CLASS_CONFIDENCE = 0.50
MIN_CONFIDENCE_MARGIN = 0.10
MIN_EVIDENCE_SIMILARITY = 0.20
MAX_EVIDENCE_RESULTS = 3


TRAINING_DATA = [
    ("cannot log in authentication failed", "Authentication"),
    ("password rejected and account locked", "Authentication"),
    ("single sign on login failure", "Authentication"),
    ("unauthorized 401 error during login", "Authentication"),
    ("password reset is not working", "Authentication"),
    ("identity provider login failure", "Authentication"),
    ("user authentication token expired", "Authentication"),
    ("login fails after identity configuration change", "Authentication"),
    ("database connection timeout", "Database"),
    ("SQL database is unavailable", "Database"),
    ("connection pool exhausted", "Database"),
    ("application cannot connect to PostgreSQL", "Database"),
    ("database connection refused", "Database"),
    ("database query is very slow", "Database"),
    ("database server is unreachable", "Database"),
    ("queries fail because database is overloaded", "Database"),
    ("application returns HTTP 500 after deployment", "Deployment"),
    ("new release caused application errors", "Deployment"),
    ("deployment pipeline failed", "Deployment"),
    ("service crashes after configuration change", "Deployment"),
    ("latest application version will not start", "Deployment"),
    ("rollback needed after failed release", "Deployment"),
    ("application broken after software update", "Deployment"),
    ("release failed during production deployment", "Deployment"),
    ("API request times out due to network issue", "Network"),
    ("DNS lookup fails for application server", "Network"),
    ("service is unreachable from client network", "Network"),
    ("high packet loss between servers", "Network"),
    ("connection timed out to remote host", "Network"),
    ("network latency is unusually high", "Network"),
    ("cannot reach remote host over the network", "Network"),
    ("DNS resolution failure causes service outage", "Network"),
]


RUNBOOKS = [
    {
        "id": "RB-001",
        "title": "Authentication troubleshooting",
        "category": "Authentication",
        "content": (
            "For login failures, check identity provider availability, "
            "account status, authentication logs, and recent identity "
            "configuration changes. Never request a user's password."
        ),
    },
    {
        "id": "RB-002",
        "title": "Database connectivity",
        "category": "Database",
        "content": (
            "For database connection failures, inspect database health, "
            "connection pool usage, network reachability, and recent "
            "configuration changes. Never expose database credentials."
        ),
    },
    {
        "id": "RB-003",
        "title": "Deployment investigation",
        "category": "Deployment",
        "content": (
            "After a failed deployment, compare release timestamps with "
            "application errors, inspect deployment logs and configuration "
            "changes, and follow the approved rollback procedure."
        ),
    },
    {
        "id": "RB-004",
        "title": "Network troubleshooting",
        "category": "Network",
        "content": (
            "For timeouts and unreachable services, check DNS resolution, "
            "service reachability, network errors, and latency."
        ),
    },
]


def validate_description(description: str) -> str:
    """Normalize and validate the incident description."""
    if not isinstance(description, str):
        raise ValueError("Incident description must be text.")

    cleaned = " ".join(description.split())

    if len(cleaned) < MIN_DESCRIPTION_LENGTH:
        raise ValueError(
            f"Please provide at least {MIN_DESCRIPTION_LENGTH} characters "
            "describing the incident."
        )

    if not any(character.isalpha() for character in cleaned):
        raise ValueError("Include words describing the incident.")

    return cleaned


def build_classifier():
    """Train the illustrative TF-IDF and logistic-regression baseline."""
    texts = [text for text, _ in TRAINING_DATA]
    labels = [label for _, label in TRAINING_DATA]

    vectorizer = TfidfVectorizer(ngram_range=(1, 2))
    features = vectorizer.fit_transform(texts)

    model = LogisticRegression(max_iter=1000)
    model.fit(features, labels)

    return vectorizer, model


def classify_incident(description: str, vectorizer, model) -> dict:
    """Return ranked category scores and reasons for human review."""
    cleaned = validate_description(description)
    features = vectorizer.transform([cleaned])
    probabilities = model.predict_proba(features)[0]

    ranked_indices = probabilities.argsort()[::-1]
    best_index = int(ranked_indices[0])

    category = str(model.classes_[best_index])
    confidence = float(probabilities[best_index])

    second_confidence = (
        float(probabilities[ranked_indices[1]])
        if len(ranked_indices) > 1
        else 0.0
    )

    confidence_margin = confidence - second_confidence

    top_predictions = [
        {
            "category": str(model.classes_[int(index)]),
            "confidence": float(probabilities[int(index)]),
        }
        for index in ranked_indices[:3]
    ]

    review_reasons = []

    if confidence < MIN_CLASS_CONFIDENCE:
        review_reasons.append(
            "Top prediction is below the configured confidence threshold."
        )

    if confidence_margin < MIN_CONFIDENCE_MARGIN:
        review_reasons.append(
            "The top two categories have similar confidence scores."
        )

    return {
        "description": cleaned,
        "category": category,
        "confidence": confidence,
        "confidence_margin": confidence_margin,
        "top_predictions": top_predictions,
        "needs_review": bool(review_reasons),
        "review_reason": " ".join(review_reasons),
        "model_status": "illustrative_baseline",
    }


def retrieve_evidence(description: str, runbooks=None) -> list:
    """Retrieve relevant runbooks using TF-IDF cosine similarity."""
    cleaned = validate_description(description)
    documents = RUNBOOKS if runbooks is None else runbooks

    if not documents:
        return []

    valid_documents = [
        doc
        for doc in documents
        if isinstance(doc, dict)
        and all(
            key in doc
            for key in ("id", "title", "category", "content")
        )
    ]

    if not valid_documents:
        return []

    texts = [
        f"{doc['title']} {doc['category']} {doc['content']}"
        for doc in valid_documents
    ]

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        stop_words="english",
    )

    try:
        document_vectors = vectorizer.fit_transform(texts)
        query_vector = vectorizer.transform([cleaned])
    except ValueError:
        return []

    scores = cosine_similarity(query_vector, document_vectors)[0]
    ranked_indices = scores.argsort()[::-1]

    evidence = []

    for index in ranked_indices:
        score = float(scores[index])

        if score < MIN_EVIDENCE_SIMILARITY:
            continue

        doc = valid_documents[int(index)]

        evidence.append(
            {
                "id": str(doc["id"]),
                "title": str(doc["title"]),
                "category": str(doc["category"]),
                "content": str(doc["content"]),
                "similarity": score,
            }
        )

        if len(evidence) >= MAX_EVIDENCE_RESULTS:
            break

    return evidence
