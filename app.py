
"""TraceGuard AI — cybersecurity incident investigation dashboard."""

import streamlit as st
import pandas as pd

from src.database import (
    initialize_database,
    save_incident,
    get_incident_history,
    get_incident_by_id,
    get_review_status,
    save_review,
    get_review_history,
    get_all_review_statuses,
)
from src.investigation import (
    build_classifier,
    classify_incident,
    retrieve_evidence,
)

# --------------------------------------------------
# TraceGuard AI: Human-in-the-loop safety settings
# --------------------------------------------------

LOW_CONFIDENCE_THRESHOLD = 0.60  # 60%



# --------------------------------------------------
# 1. Page configuration
# --------------------------------------------------

st.set_page_config(
    page_title="TraceGuard AI | Security Operations",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------
# 2. Custom styling
# --------------------------------------------------

st.markdown(
    """
    <style>
    :root {
        --tg-bg: #08111f;
        --tg-panel: #101d30;
        --tg-border: #203650;
        --tg-cyan: #43d9f5;
        --tg-text: #e7f0fc;
        --tg-muted: #96aac2;
    }

    .stApp {
        background: radial-gradient(
            ellipse at top right,
            #102b42 0%,
            #08111f 48%
        );
        color: var(--tg-text);
    }

    [data-testid="stHeader"] {
        background: rgba(8, 17, 31, 0.88);
    }

    [data-testid="stSidebar"] {
        background: #0b1728;
        border-right: 1px solid #203650;
    }

    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #13253b, #0d192a);
        border: 1px solid #203650;
        border-radius: 14px;
        padding: 16px 14px;
    }

    [data-testid="stMetricLabel"] {
        color: #a8bdd5;
    }

    [data-testid="stMetricValue"] {
        color: #43d9f5;
    }

    h1, h2, h3 {
        color: #e7f0fc !important;
        letter-spacing: -0.3px;
    }

    p, label, [data-testid="stMarkdownContainer"] {
        color: #d4e1f1;
    }

    .tg-hero {
        padding: 24px 26px;
        border: 1px solid #24435c;
        border-radius: 18px;
        background: linear-gradient(
            115deg,
            #112840 0%,
            #0d1b2e 60%,
            #102d40 100%
        );
        margin-bottom: 18px;
    }

    .tg-eyebrow {
        color: #43d9f5;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 2px;
        text-transform: uppercase;
    }

    .tg-title {
        color: #f1f7ff;
        font-size: 34px;
        font-weight: 800;
        margin: 7px 0 8px;
    }

    .tg-subtitle {
        color: #afc3da;
        font-size: 15px;
        line-height: 1.6;
    }

    div.stButton > button[kind="primary"],
    div.stFormSubmitButton > button[kind="primary"] {
        background: #12b8d5;
        color: #061321;
        border: 0;
        border-radius: 9px;
        font-weight: 750;
        min-height: 44px;
    }

    div.stButton > button[kind="primary"]:hover,
    div.stFormSubmitButton > button[kind="primary"]:hover {
        background: #65e5f7;
        color: #061321;
    }

    div[data-testid="stExpander"] {
        background: #101d30;
        border: 1px solid #203650;
        border-radius: 10px;
    }

    div[data-testid="stAlert"] {
        border-radius: 10px;
    }

    [data-testid="stDataFrame"] {
        border: 1px solid #203650;
        border-radius: 10px;
    }

    .tg-footer {
        color: #7890aa;
        font-size: 12px;
        text-align: center;
        padding: 20px 0 8px;
    }

    @media (max-width: 900px) {
        .tg-title {
            font-size: 28px;
        }

        .tg-hero {
            padding: 18px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# 3. Initialize database
# --------------------------------------------------

initialize_database()


# --------------------------------------------------
# 4. Sidebar navigation
# --------------------------------------------------

with st.sidebar:
    st.markdown("## 🛡️ TraceGuard AI")
    st.caption("SECURITY OPERATIONS CONSOLE")
    st.divider()

    page = st.radio(
        "NAVIGATION",
        [
            "Overview",
            "Investigate Incident",
            "Incident History",
            "Human Review",
        ],
    )

    st.divider()

    st.markdown("### System status")
    st.markdown("🟢 **Application:** Running")
    st.markdown("🔵 **Storage:** SQLite")
    st.markdown("🟡 **AI model:** Illustrative baseline")

    st.divider()

    st.caption(
        "Prototype only. Predictions and sample runbooks "
        "are not validated for production incident response."
    )


# --------------------------------------------------
# 5. Load classifier
# --------------------------------------------------

@st.cache_resource
def load_classifier():
    return build_classifier()


vectorizer, model = load_classifier()



# --------------------------------------------------
# 6. Load existing incident history
# --------------------------------------------------

try:
    history = get_incident_history(limit=1000)
except Exception as error:
    st.error("Unable to read incident history from SQLite.")
    st.exception(error)
    st.stop()


history_df = pd.DataFrame(history)

if not history_df.empty:
    # Ensure review-related columns exist.
    if "review_reason" not in history_df.columns:
        history_df["review_reason"] = ""

    if "needs_review" not in history_df.columns:
        history_df["needs_review"] = pd.NA

    # Convert review flags to numeric values.
    history_df["needs_review"] = pd.to_numeric(
        history_df["needs_review"],
        errors="coerce",
    )

    # Convert classifier scores to numeric values.
    history_df["confidence"] = pd.to_numeric(
        history_df.get(
            "confidence",
            pd.Series(index=history_df.index, dtype=float),
        ),
        errors="coerce",
    )

    # Ensure text columns exist and contain no null values.
    for column in [
        "evidence_ids",
        "description",
        "review_reason",
    ]:
        if column not in history_df.columns:
            history_df[column] = ""

        history_df[column] = (
            history_df[column].fillna("").astype(str)
        )

    if "category" not in history_df.columns:
        history_df["category"] = "Unknown"

    # Flag historical incidents below the confidence threshold.
    if "LOW_CONFIDENCE_THRESHOLD" in globals():
        low_confidence = (
            history_df["confidence"] < LOW_CONFIDENCE_THRESHOLD
        )

        history_df.loc[low_confidence, "needs_review"] = 1

        # Add the low-confidence reason without discarding
        # any existing review reason.
        for index in history_df.index[low_confidence]:
            existing_reason = history_df.at[index, "review_reason"]
            low_reason = (
                f"Low classifier confidence "
                f"({history_df.at[index, 'confidence']:.1%})"
            )

            if low_reason not in existing_reason:
                history_df.at[index, "review_reason"] = (
                    f"{existing_reason}; {low_reason}"
                    if existing_reason.strip()
                    else low_reason
                )


# --------------------------------------------------
# 7. Shared helper: show hero banner
# --------------------------------------------------

def show_hero():
    st.markdown(
        """
        <div class="tg-hero">
            <div class="tg-eyebrow">
                ◈ SECURITY INTELLIGENCE · INCIDENT RESPONSE
            </div>
            <div class="tg-title">TraceGuard AI</div>
            <div class="tg-subtitle">
                Evidence-grounded IT incident investigation.
                Explore likely incident categories, retrieve relevant
                example runbooks, and identify cases requiring human review.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(
        "DEMO ENVIRONMENT · Sample classifier · Example runbooks · "
        "Human oversight required"
    )


show_hero()


# --------------------------------------------------
# 8. Dashboard metrics
# --------------------------------------------------

total_incidents = len(history_df)

if total_incidents:
    known_flags = history_df["needs_review"].dropna()
    pending_review_flags = int((known_flags == 1).sum())
    unknown_flags = int(history_df["needs_review"].isna().sum())

    with_evidence = int(
        history_df["evidence_ids"]
        .astype(str)
        .str.strip()
        .ne("")
        .sum()
    )

    evidence_coverage = with_evidence / total_incidents
else:
    pending_review_flags = 0
    unknown_flags = 0
    with_evidence = 0
    evidence_coverage = 0.0


# Load actual human-review statuses separately from AI flags.

try:
    review_rows = get_all_review_statuses()

    review_statuses = {
        int(row["id"]): row.get("status", "Pending")
        for row in review_rows
    }

except Exception as error:
    st.error("Unable to load human-review statuses.")
    st.exception(error)
    review_statuses = {}

human_pending = sum(
    status == "Pending" for status in review_statuses.values()
)
human_reviewed = sum(
    status == "Reviewed" for status in review_statuses.values()
)
human_escalated = sum(
    status == "Escalated" for status in review_statuses.values()
)

metric1, metric2, metric3, metric4 = st.columns(4)

with metric1:
    st.metric("Investigations", total_incidents)

with metric2:
    st.metric("AI review flags", pending_review_flags)

with metric3:
    st.metric("With evidence", with_evidence)

with metric4:
    st.metric("Evidence coverage", f"{evidence_coverage:.0%}")

if unknown_flags:
    st.caption(
        f"{unknown_flags} historical record(s) have an unknown "
        "automatic review flag."
    )

if review_statuses:
    st.caption(
        f"Human review workflow: {human_pending} Pending · "
        f"{human_reviewed} Reviewed · {human_escalated} Escalated"
    )

st.divider()


# --------------------------------------------------
# 9. Incident investigation function
# --------------------------------------------------

def investigate_incident():
    """Analyze an incident and save its result to SQLite."""

    description = st.session_state.get(
        "incident_description", ""
    )

    try:
        result = classify_incident(
            description,
            vectorizer,
            model,
        )

        
        evidence = retrieve_evidence(description)
        reasons = []

        original_reason = result.get("review_reason", "").strip()

        if result.get("needs_review") and original_reason:
            reasons.append(original_reason)

        confidence_value = float(result.get("confidence", 0.0))

        if confidence_value < LOW_CONFIDENCE_THRESHOLD:
            confidence_reason = (
                "Low classifier confidence "
                f"({confidence_value:.1%})"
            )

            if not any(
                "confidence" in reason.lower()
                or "threshold" in reason.lower()
                for reason in reasons
            ):
                reasons.append(confidence_reason)

        if not evidence:
            no_evidence_reason = "No relevant runbook evidence found."

            if no_evidence_reason not in reasons:
                reasons.append(no_evidence_reason)

        result["needs_review"] = bool(reasons)

        review_reason = (
            "; ".join(reasons)
            if reasons
            else "No automatic review trigger detected."
        )

        result["review_reason"] = review_reason

        incident_id = save_incident(
            result,
            evidence,
            review_reason=review_reason,
        )

        st.session_state["latest_investigation"] = {
            "result": result,
            "evidence": evidence,
            "incident_id": incident_id,
            "review_reason": review_reason,
        }

        st.session_state.pop("incident_error", None)

    except ValueError as error:
        st.session_state["incident_error"] = str(error)
        st.session_state.pop("latest_investigation", None)

    except Exception as error:
        st.session_state["incident_error"] = (
            f"Investigation failed: {error}"
        )
        st.session_state.pop("latest_investigation", None)


# --------------------------------------------------
# 10. Investigation page
# --------------------------------------------------

if page in ["Overview", "Investigate Incident"]:
    st.subheader("🔎 Investigate an incident")

    st.write(
        "Describe the observed symptoms. TraceGuard will classify "
        "the incident, search example runbooks, and flag uncertainty."
    )

    with st.form("incident_form", clear_on_submit=False):
        st.text_area(
            "Incident description",
            key="incident_description",
            height=130,
            placeholder=(
                "Example: After the latest deployment, "
                "the application returns HTTP 500 errors."
            ),
            help=(
                "Include symptoms, error messages, affected services, "
                "and recent changes. Do not enter passwords or secrets."
            ),
        )

        submitted = st.form_submit_button(
            "Analyze incident →",
            type="primary",
            width="stretch",
        )

    if submitted:
        investigate_incident()

    if st.session_state.get("incident_error"):
        st.error(st.session_state["incident_error"])

    latest = st.session_state.get("latest_investigation")

    if latest:
        result = latest["result"]
        evidence = latest["evidence"]
        incident_id = latest["incident_id"]
        review_reason = latest["review_reason"]

        st.divider()
        st.subheader("Investigation result")
        st.caption(f"Saved investigation · Record ID {incident_id}")

        result1, result2, result3 = st.columns(3)

        with result1:
            st.metric("Predicted category", result["category"])

        with result2:
            st.metric(
                "Classifier score",
                f"{result['confidence']:.1%}",
            )

        with result3:
            st.metric("Evidence matches", len(evidence))

        if result["needs_review"]:
            st.warning(
                f"Human review recommended: {review_reason} "
                "Do not rely on the predicted category alone."
            )
        else:
            st.success(
                "No configured review trigger was detected. "
                "This does not mean the prediction is verified."
            )

        st.markdown("### Alternative category predictions")
        st.caption(
            "Ranked scores from the illustrative classifier. "
            "These are not validated probabilities of correctness."
        )

        predictions = result.get("top_predictions", [])

        if predictions:
            for rank, prediction in enumerate(predictions, start=1):
                st.write(
                    f"**{rank}. {prediction['category']}** — "
                    f"{prediction['confidence']:.1%}"
                )
                st.progress(
                    min(max(prediction["confidence"], 0.0), 1.0)
                )
        else:
            st.info("Alternative predictions are unavailable.")

        st.markdown("### Evidence matches")

        if evidence:
            for item in evidence:
                with st.expander(
                    f"{item['id']} · {item['title']} · "
                    f"Similarity {item['similarity']:.3f}"
                ):
                    st.write(f"**Category:** {item['category']}")
                    st.write(item["content"])
                    st.caption(
                        "Example runbook only. Verify against "
                        "approved organizational procedures."
                    )
        else:
            st.warning(
                "No runbook met the evidence threshold. "
                "Human investigation is recommended."
            )

        st.markdown("### Investigation details")
        st.markdown("**Incident description**")
        st.code(result["description"], language=None)
        st.write(
            "**Model status:**",
            result.get("model_status", "Unknown"),
        )
        st.write("**Automatic review reason:**", review_reason)

        st.info(
            "To record a reviewer decision, open the Human Review "
            "page from the sidebar."
        )


# --------------------------------------------------
# 11. Human Review Workflow
# --------------------------------------------------

if page == "Human Review":
    st.subheader("🧑‍💻 Human Review Workflow")

    st.write(
        "Review investigated incidents, record decisions, "
        "and maintain an audit trail of human review activity."
    )

    # Load incident history
    try:
        incidents = get_incident_history(limit=1000)
    except Exception as error:
        st.error("Unable to load incident history.")
        st.exception(error)
        incidents = []

    if not incidents:
        st.info(
            "No incidents are available yet. "
            "Investigate and save an incident first."
        )

    else:
        # Create incident dropdown options
        incident_options = {}

        for item in incidents:
            incident_id_value = int(item["id"])

            description = (
                item.get("description")
                or item.get("incident_description")
                or "No description available"
            )

            incident_options[
                f"Incident #{incident_id_value} — {description[:80]}"
            ] = incident_id_value

        selected_label = st.selectbox(
            "Select an incident to review",
            options=list(incident_options.keys()),
        )

        incident_id = incident_options[selected_label]

        try:
            incident = get_incident_by_id(incident_id)
            current_review = get_review_status(incident_id) or {}

            if not incident:
                st.warning("The selected incident could not be found.")

            else:
                # Current review information
                current_status = current_review.get(
                    "status", "Pending"
                )

                reviewer = current_review.get(
                    "reviewer_name", "Not assigned"
                )

                st.divider()
                st.markdown("### Incident details")

                col1, col2 = st.columns(2)

                with col1:
                    st.metric("Incident ID", incident_id)
                    st.metric("Review status", current_status)

                with col2:
                    st.write("**Current reviewer**")
                    st.write(reviewer)

                description = (
                    incident.get("description")
                    or incident.get("incident_description")
                    or "No description available."
                )

                st.write("**Incident description**")
                st.write(description)

                # Review form
                st.divider()
                st.markdown("### Submit human review")

                with st.form("human_review_form"):
                    status = st.selectbox(
                        "Review decision",
                        options=[
                            "Pending",
                            "Reviewed",
                            "Escalated",
                            "Resolved",
                            "False Positive",
                        ],
                        index=(
                            [
                                "Pending",
                                "Reviewed",
                                "Escalated",
                                "Resolved",
                                "False Positive",
                            ].index(current_status)
                            if current_status in [
                                "Pending",
                                "Reviewed",
                                "Escalated",
                                "Resolved",
                                "False Positive",
                            ]
                            else 0
                        ),
                    )

                    reviewer_name = st.text_input(
                        "Reviewer name",
                        value=(
                            ""
                            if reviewer == "Not assigned"
                            else reviewer
                        ),
                        placeholder="Enter your name",
                    )

                    notes = st.text_area(
                        "Review notes",
                        placeholder=(
                            "Describe what you checked, "
                            "the evidence considered, and "
                            "any follow-up required."
                        ),
                    )

                    save_clicked = st.form_submit_button(
                        "Save Review",
                        use_container_width=True,
                    )

                if save_clicked:
                    if not reviewer_name.strip():
                        st.error("Please enter the reviewer name.")

                    else:
                        try:
                            save_review(
                                incident_id=incident_id,
                                status=status,
                                reviewer_name=reviewer_name.strip(),
                                notes=notes.strip(),
                            )

                            st.success(
                                "Review saved successfully."
                            )

                            st.rerun()

                        except Exception as error:
                            st.error("Unable to save the review.")
                            st.exception(error)

                # Review audit trail
                st.divider()
                st.markdown("### Review audit trail")

                try:
                    audit_entries = get_review_history(incident_id)

                    if not audit_entries:
                        st.info(
                            "No audit records are available "
                            "for this incident yet."
                        )

                    else:
                        for entry in audit_entries:
                            timestamp = (
                                entry.get("recorded_at")
                                or entry.get("created_at")
                                or entry.get("reviewed_at")
                                or entry.get("timestamp")
                                or "Time unavailable"
                            )

                            status_text = entry.get(
                                "status", "Unknown"
                            )

                            reviewer_text = entry.get(
                                "reviewer_name", "Unknown reviewer"
                            )

                            notes_text = (
                                entry.get("notes")
                                or "No notes provided."
                            )

                            with st.expander(
                                f"{status_text} · "
                                f"{reviewer_text} · "
                                f"{timestamp}"
                            ):
                                st.write(
                                    "**Review status:**",
                                    status_text,
                                )

                                st.write(
                                    "**Reviewer:**",
                                    reviewer_text,
                                )

                                st.write(
                                    "**Recorded at:**",
                                    timestamp,
                                )

                                st.write(
                                    "**Review notes:**",
                                    notes_text,
                                )

                except Exception as error:
                    st.error(
                        "Unable to load the review audit trail."
                    )
                    st.exception(error)

        except Exception as error:
            st.error(
                "Unable to load the selected incident review."
            )
            st.exception(error)

# --------------------------------------------------
# 12. Category and review overview
# --------------------------------------------------

if page == "Overview":
    st.divider()
    st.subheader("Incident landscape")

    if history_df.empty:
        st.info(
            "No saved investigations yet. Analyze an incident "
            "to begin building your dashboard."
        )
    else:
        left, right = st.columns(2)

        with left:
            st.markdown("#### Incidents by category")

            category_counts = (
                history_df["category"]
                .fillna("Unknown")
                .value_counts()
                .rename_axis("Category")
                .reset_index(name="Incidents")
            )

            st.bar_chart(
                category_counts.set_index("Category"),
                color="#43d9f5",
            )

        with right:
            st.markdown("#### Automatic review flags")

            known_flags = history_df["needs_review"].dropna()
            flagged_count = int((known_flags == 1).sum())
            no_flag_count = int((known_flags == 0).sum())
            unknown_count = int(history_df["needs_review"].isna().sum())

            review_counts = pd.DataFrame({
                "Status": [
                    "Flagged for review",
                    "No automatic flag",
                    "Unknown",
                ],
                "Incidents": [
                    flagged_count,
                    no_flag_count,
                    unknown_count,
                ],
            })

            review_counts = review_counts[
                review_counts["Incidents"] > 0
            ]

            st.bar_chart(
                review_counts.set_index("Status"),
                color="#43d9f5",
            )

            st.caption(
                "Automatic flags are not proof that a human has "
                "reviewed an incident."
            )

        # Human review status chart.
        if review_statuses:
            st.markdown("#### Human review status")

            human_status_df = pd.DataFrame({
                "Status": ["Pending", "Reviewed", "Escalated"],
                "Incidents": [
                    human_pending,
                    human_reviewed,
                    human_escalated,
                ],
            })

            human_status_df = human_status_df[
                human_status_df["Incidents"] > 0
            ]

            st.bar_chart(
                human_status_df.set_index("Status"),
                color="#43d9f5",
            )



# --------------------------------------------------
# 13. Searchable incident history
# --------------------------------------------------

if page in ["Overview", "Incident History"]:
    st.divider()
    st.subheader("📋 Incident history")

    st.caption(
        "Records are loaded from your existing SQLite database. "
        "Saved investigations are not deleted or reset."
    )

    if history_df.empty:
        st.info("No incident history is available yet.")

    else:
        filter_col1, filter_col2 = st.columns(2)

        with filter_col1:
            review_filter = st.selectbox(
                "Automatic review flag",
                [
                    "All incidents",
                    "Flagged for review",
                    "No automatic flag",
                    "Unknown flag",
                ],
            )

        with filter_col2:
            categories = ["All categories"] + sorted(
                history_df["category"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

            category_filter = st.selectbox(
                "Incident category",
                categories,
            )

        search_text = st.text_input(
            "Search incident descriptions",
            placeholder="Search error message, service, or keyword...",
        )

        # Apply filters to the saved incident history.
        filtered_df = history_df.copy()

        if review_filter == "Flagged for review":
            filtered_df = filtered_df[
                filtered_df["needs_review"] == 1
            ]

        elif review_filter == "No automatic flag":
            filtered_df = filtered_df[
                filtered_df["needs_review"] == 0
            ]

        elif review_filter == "Unknown flag":
            filtered_df = filtered_df[
                filtered_df["needs_review"].isna()
            ]

        if category_filter != "All categories":
            filtered_df = filtered_df[
                filtered_df["category"].astype(str)
                == category_filter
            ]

        if search_text.strip():
            filtered_df = filtered_df[
                filtered_df["description"].str.contains(
                    search_text.strip(),
                    case=False,
                    na=False,
                    regex=False,
                )
            ]

        st.caption(
            f"Showing {len(filtered_df)} of "
            f"{len(history_df)} saved investigations."
        )

        # Create a separate display copy of the filtered records.
        display_df = filtered_df.copy()

        # Add each incident's saved human-review status.
        display_df["human_review_status"] = (
            display_df["id"]
            .map(review_statuses)
            .fillna("Pending")
        )

        # Format classifier confidence as a percentage.
        if "confidence" in display_df.columns:
            display_df["confidence"] = display_df["confidence"].apply(
                lambda value: (
                    f"{value:.1%}"
                    if pd.notna(value)
                    else "Unknown"
                )
            )

        # Format automatic review flags.
        display_df["needs_review"] = (
            display_df["needs_review"]
            .map({
                1: "Flagged",
                0: "No automatic flag",
            })
            .fillna("Unknown")
        )

        # Rename columns to make the table easier to read.
        display_df = display_df.rename(
            columns={
                "id": "Incident ID",
                "created_at": "Created At",
                "description": "Description",
                "category": "Category",
                "confidence": "Confidence",
                "needs_review": "Automatic Review",
                "human_review_status": "Human Review",
                "review_reason": "Review Reason",
                "evidence_ids": "Evidence IDs",
            }
        )

        # Display only the columns that exist.
        display_columns = [
            column
            for column in [
                "Incident ID",
                "Created At",
                "Description",
                "Category",
                "Confidence",
                "Automatic Review",
                "Human Review",
                "Review Reason",
                "Evidence IDs",
            ]
            if column in display_df.columns
        ]

        st.dataframe(
            display_df[display_columns],
            width="stretch",
            hide_index=True,
            height=420,
        )


# --------------------------------------------------
# 14. Footer
# --------------------------------------------------

st.markdown(
    """
    <div class="tg-footer">
        TRACEGUARD AI · EVIDENCE FIRST · HUMAN OVERSIGHT
        <br>
        Educational prototype — not validated for production use.
    </div>
    """,
    unsafe_allow_html=True,
)
