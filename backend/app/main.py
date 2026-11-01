from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.api.deps import get_current_user


from app.api.patient import router as patient_router
from app.api.visit import router as visit_router
from app.api.medical_report import router as medical_report_router
from app.api.timeline import router as timeline_router
from app.api.clinical_copilot import router as clinical_copilot_router
from app.api.clinical_trend import router as clinical_trend_router
from app.api.clinical_measurement import (
    router as clinical_measurement_router,
)
from app.api.longitudinal_insights import (
    router as longitudinal_insights_router,
)
from app.api.clinical_alerts import (
    router as clinical_alerts_router,
    alerts_router as clinical_alerts_overview_router,
)
from app.api.health_radar import router as health_radar_router
from app.api.health_trajectory import router as health_trajectory_router
from app.api.clinical_translation import router as clinical_translation_router
from app.api.rag import router as rag_router
from app.api.auth import router as auth_router


app = FastAPI(
    title="AI Longitudinal Healthcare Platform",
    description=(
        "AI-powered longitudinal healthcare decision-support "
        "platform for traveling doctors."
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://care-track-ai-five.vercel.app",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(patient_router, dependencies=[Depends(get_current_user)])
app.include_router(visit_router, dependencies=[Depends(get_current_user)])
app.include_router(medical_report_router, dependencies=[Depends(get_current_user)])
app.include_router(timeline_router, dependencies=[Depends(get_current_user)])
app.include_router(clinical_trend_router, dependencies=[Depends(get_current_user)])
app.include_router(clinical_measurement_router, dependencies=[Depends(get_current_user)])
app.include_router(longitudinal_insights_router, dependencies=[Depends(get_current_user)])
app.include_router(clinical_alerts_router, dependencies=[Depends(get_current_user)])
app.include_router(clinical_alerts_overview_router, dependencies=[Depends(get_current_user)])
app.include_router(clinical_copilot_router, dependencies=[Depends(get_current_user)])
app.include_router(health_radar_router, dependencies=[Depends(get_current_user)])
app.include_router(health_trajectory_router, dependencies=[Depends(get_current_user)])
app.include_router(clinical_translation_router, dependencies=[Depends(get_current_user)])
app.include_router(rag_router, dependencies=[Depends(get_current_user)])
app.include_router(auth_router)


@app.get("/")
def root():
    return {
        "message": "AI Longitudinal Healthcare Platform API is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "project": "AI Longitudinal Healthcare Platform",
    }
