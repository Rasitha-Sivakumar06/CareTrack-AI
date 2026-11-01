from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func

from app.database import Base


class MedicalReport(Base):
    __tablename__ = "medical_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    visit_id = Column(Integer, nullable=False, index=True)
    file_name = Column(String, nullable=True)
    file_type = Column(String, nullable=True)
    file_path = Column(Text, nullable=True)
    extracted_text = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
