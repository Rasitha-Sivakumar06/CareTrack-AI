from datetime import date
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class RAGQuestionRequest(BaseModel):
    """Request payload for asking a question about a patient's medical history."""
    patient_id: int = Field(gt=0, description="Positive numeric ID of the selected patient.")
    question: str = Field(min_length=3, max_length=2000, description="Clinical query submitted by the doctor.")


class RAGSourceRecord(BaseModel):
    """Structured citation metadata for an evidence chunk retrieved from patient records."""
    model_config = ConfigDict(from_attributes=True)

    source_id: str = Field(description="Deterministic source identifier, e.g., 'S1', 'S2'.")
    record_type: str = Field(description="Type of record: 'Clinical Encounter', 'Clinical Measurement', or 'Medical Report'.")
    visit_id: int | None = Field(default=None, description="Database ID of the associated visit.")
    visit_date: date | str | None = Field(default=None, description="Recorded date of the clinical visit.")
    summary: str = Field(description="Human-readable summary of the recorded clinical findings.")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Structured clinical parameters extracted from the record.")


class DataSummary(BaseModel):
    """Longitudinal data metrics and gap indicators for the selected patient."""
    model_config = ConfigDict(from_attributes=True)

    total_visits_retrieved: int = Field(default=0, description="Total number of visits retrieved for this patient.")
    total_measurements_retrieved: int = Field(default=0, description="Total number of clinical measurements retrieved.")
    total_reports_retrieved: int = Field(default=0, description="Total number of medical reports retrieved.")
    has_sufficient_history: bool = Field(default=False, description="True if patient has >= 2 visits for longitudinal trend comparison.")
    earliest_visit_date: date | str | None = Field(default=None, description="Date of the earliest recorded visit.")
    latest_visit_date: date | str | None = Field(default=None, description="Date of the latest recorded visit.")
    data_gap_warnings: list[str] = Field(default_factory=list, description="Data-quality notes or missing parameters detected.")


class RAGQueryResponse(BaseModel):
    """Complete response returned by the Patient History RAG Assistant."""
    model_config = ConfigDict(from_attributes=True)

    patient_id: int = Field(description="ID of the queried patient.")
    patient_code: str = Field(description="Unique patient code, e.g. DEMO-ARUN-001.")
    patient_name: str = Field(description="Full name of the patient.")
    question: str = Field(description="The original clinical question.")
    answer: str = Field(description="Grounded AI response citing source IDs such as [S1], [S2].")
    sources: list[RAGSourceRecord] = Field(default_factory=list, description="List of structured source citations used in the answer.")
    retrieval_method: str = Field(
        default="structured_longitudinal_retrieval",
        description="Explicit identifier of the retrieval mechanism employed."
    )
    data_summary: DataSummary = Field(description="Summary metrics of the patient's retrieved longitudinal records.")
    disclaimer: str = Field(
        default=(
            "CareTrack AI is a clinical decision-support prototype, not an autonomous diagnostic system. "
            "Answers are grounded exclusively in retrieved patient records. "
            "All clinical judgments, diagnoses, and treatment decisions remain the responsibility of the licensed healthcare professional."
        ),
        description="Mandatory healthcare decision-support and safety disclaimer."
    )
