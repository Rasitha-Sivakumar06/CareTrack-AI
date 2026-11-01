from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class MedicalReportCreate(BaseModel):
    visit_id: int
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_path: Optional[str] = None
    extracted_text: Optional[str] = None


class MedicalReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_id: int
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    extracted_text: Optional[str] = None
    extracted_measurements: Optional[dict[str, Any]] = None
