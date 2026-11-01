from sqlalchemy import Column, Integer, Date, Text, DateTime, func
from app.database import Base


class Visit(Base):
    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, autoincrement=True)

    patient_id = Column(Integer, nullable=False, index=True)
    visit_date = Column(Date, nullable=False)

    symptoms = Column(Text, nullable=True)
    clinical_notes = Column(Text, nullable=True)
    follow_up_notes = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
