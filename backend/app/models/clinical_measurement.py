
from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    String,
    Float,
    DateTime,
)
from sqlalchemy.sql import func

from app.database import Base


class ClinicalMeasurement(Base):
    __tablename__ = "clinical_measurements"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    patient_id = Column(BigInteger, nullable=False)
    visit_id = Column(BigInteger, nullable=False)

    blood_pressure = Column(String, nullable=True)
    systolic_bp = Column(Integer, nullable=True)
    diastolic_bp = Column(Integer, nullable=True)

    hemoglobin = Column(Float, nullable=True)
    blood_glucose = Column(Float, nullable=True)
    heart_rate = Column(Float, nullable=True)
    temperature = Column(Float, nullable=True)
    oxygen_saturation = Column(Float, nullable=True)
    weight = Column(Float, nullable=True)

    # When the measurement was actually taken.
    measured_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # When the record was created in the database.
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=True,
    )
