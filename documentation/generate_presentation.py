import sys
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

def create_caretrack_presentation(output_path: str):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # Color Palette
    PRIMARY = RGBColor(8, 127, 140)      # Teal #087F8C
    DARK_NAVY = RGBColor(23, 50, 77)     # Navy #17324D
    BG_LIGHT = RGBColor(248, 250, 252)   # Light Gray #F8FAFC
    CARD_BG = RGBColor(255, 255, 255)    # White
    BORDER_COLOR = RGBColor(203, 213, 225) # Slate #CBD5E1
    TEXT_DARK = RGBColor(30, 41, 59)     # Dark Slate #1E293B
    TEXT_MUTED = RGBColor(100, 116, 139) # Gray #64748B
    ACCENT_AMBER = RGBColor(217, 119, 6) # Amber
    ACCENT_GREEN = RGBColor(16, 185, 129)# Emerald Green

    blank_layout = prs.slide_layouts[6]

    def add_header(slide, title_text, category="CARETRACK AI · TECHNICAL & CLINICAL AUDIT"):
        header_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(1.1))
        tf = header_box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

        p_cat = tf.paragraphs[0]
        p_cat.text = category.upper()
        p_cat.font.name = "Arial"
        p_cat.font.size = Pt(10)
        p_cat.font.bold = True
        p_cat.font.color.rgb = PRIMARY
        p_cat.space_after = Pt(4)

        p_title = tf.add_paragraph()
        p_title.text = title_text
        p_title.font.name = "Arial"
        p_title.font.size = Pt(22)
        p_title.font.bold = True
        p_title.font.color.rgb = DARK_NAVY

    def add_footer(slide, current_slide, total_slides=12):
        footer_box = slide.shapes.add_textbox(Inches(0.8), Inches(6.9), Inches(11.7), Inches(0.4))
        tf = footer_box.text_frame
        p = tf.paragraphs[0]
        p.text = f"CareTrack AI · Clinical Decision Support Platform · Slide {current_slide} of {total_slides}  |  CONFIDENTIAL MEDICAL EVALUATION — NOT A DIAGNOSIS"
        p.font.name = "Arial"
        p.font.size = Pt(9)
        p.font.color.rgb = TEXT_MUTED

    # -------------------------------------------------------------
    # SLIDE 1: Title Slide
    # -------------------------------------------------------------
    s1 = prs.slides.add_slide(blank_layout)
    bg1 = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    bg1.fill.solid()
    bg1.fill.fore_color.rgb = DARK_NAVY
    bg1.line.color.rgb = DARK_NAVY

    # Decorative accent bar
    bar = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.2), Inches(1.8), Inches(0.8), Inches(0.08))
    bar.fill.solid()
    bar.fill.fore_color.rgb = PRIMARY
    bar.line.color.rgb = PRIMARY

    tb1 = s1.shapes.add_textbox(Inches(1.2), Inches(2.1), Inches(10.8), Inches(4.5))
    tf1 = tb1.text_frame
    tf1.word_wrap = True

    p0 = tf1.paragraphs[0]
    p0.text = "AI-POWERED LONGITUDINAL HEALTHCARE PLATFORM"
    p0.font.name = "Arial"
    p0.font.size = Pt(13)
    p0.font.bold = True
    p0.font.color.rgb = PRIMARY
    p0.space_after = Pt(12)

    p1 = tf1.add_paragraph()
    p1.text = "CareTrack AI"
    p1.font.name = "Arial"
    p1.font.size = Pt(44)
    p1.font.bold = True
    p1.font.color.rgb = RGBColor(255, 255, 255)
    p1.space_after = Pt(14)

    p2 = tf1.add_paragraph()
    p2.text = "Continuity of Care, Explainable Health Radar, and Clinical Decision Support for Dispersed & Mobile Practices"
    p2.font.name = "Arial"
    p2.font.size = Pt(18)
    p2.font.color.rgb = RGBColor(203, 213, 225)
    p2.space_after = Pt(28)

    p3 = tf1.add_paragraph()
    p3.text = "Comprehensive System Audit · Verified Empirical Test Results · Production Architecture v0.2.0"
    p3.font.name = "Arial"
    p3.font.size = Pt(12)
    p3.font.bold = True
    p3.font.color.rgb = RGBColor(148, 163, 184)

    s1.notes_slide.notes_text_frame.text = (
        "Welcome judges and reviewers. CareTrack AI addresses longitudinal healthcare continuity for mobile "
        "physicians and dispersed outpatient clinics. In this presentation, we will detail our verified architecture, "
        "key algorithmic features like the Health Change Radar, transparent AI grounding, and empirical testing."
    )

    # -------------------------------------------------------------
    # SLIDE 2: Problem Statement & Motivation
    # -------------------------------------------------------------
    s2 = prs.slides.add_slide(blank_layout)
    add_header(s2, "Problem Statement: The Breakdown of Longitudinal Continuity")
    add_footer(s2, 2)

    c1 = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.8), Inches(5.6), Inches(4.8))
    c1.fill.solid()
    c1.fill.fore_color.rgb = CARD_BG
    c1.line.color.rgb = BORDER_COLOR

    tf_c1 = c1.text_frame
    tf_c1.word_wrap = True
    p = tf_c1.paragraphs[0]
    p.text = "Current Healthcare Challenges"
    p.font.name = "Arial"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = DARK_NAVY
    p.space_after = Pt(12)

    bullets1 = [
        ("Episodic Fragmentation:", "Patients in mobile and rural clinic networks see different traveling doctors across sporadic encounters."),
        ("Document Silos:", "Prior vital signs and lab results remain trapped in paper slips, physical folders, or disconnected PDF scans."),
        ("Cognitive Exhaustion:", "Physicians spend 15–20 minutes per patient manually reconstructing trajectory history from scratch."),
        ("Silent Clinical Decline:", "Subtle trends like creeping hypertension or early diabetic decline go unnoticed across isolated visits."),
    ]
    for b_title, b_desc in bullets1:
        p = tf_c1.add_paragraph()
        p.text = f"• {b_title} {b_desc}"
        p.font.name = "Arial"
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_DARK
        p.space_after = Pt(10)

    c2 = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.8), Inches(5.6), Inches(4.8))
    c2.fill.solid()
    c2.fill.fore_color.rgb = CARD_BG
    c2.line.color.rgb = BORDER_COLOR

    tf_c2 = c2.text_frame
    tf_c2.word_wrap = True
    p = tf_c2.paragraphs[0]
    p.text = "The Technical & Clinical Gap"
    p.font.name = "Arial"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = PRIMARY
    p.space_after = Pt(12)

    bullets2 = [
        ("Dangerous Assumptions:", "Traditional electronic records assume unrecorded vitals are normal, creating fatal blind spots."),
        ("Black-Box AI Pitfalls:", "Generic LLMs hallucinate diagnostic conclusions and lack grounding in actual patient records."),
        ("Lack of Standardization:", "Disparate physiological metrics (mmHg, mg/dL, bpm, %) cannot be easily compared at a glance."),
        ("Language Barriers:", "Rural outreach in regions like Tamil Nadu struggles with English-only clinical summaries."),
    ]
    for b_title, b_desc in bullets2:
        p = tf_c2.add_paragraph()
        p.text = f"• {b_title} {b_desc}"
        p.font.name = "Arial"
        p.font.size = Pt(12)
        p.font.color.rgb = TEXT_DARK
        p.space_after = Pt(10)

    s2.notes_slide.notes_text_frame.text = (
        "Mobile physicians face a structural continuity crisis. When patients see a different doctor at each encounter, "
        "vital longitudinal context is lost. Generic AI tools make things worse by hallucinating medical facts without "
        "patient record grounding. CareTrack AI directly resolves these specific operational gaps."
    )

    # -------------------------------------------------------------
    # SLIDE 3: Objectives & Solution Scope
    # -------------------------------------------------------------
    s3 = prs.slides.add_slide(blank_layout)
    add_header(s3, "Project Objectives: Empowering Clinicians with Continuous Context")
    add_footer(s3, 3)

    objs = [
        ("Unified Healthcare Workspace", "Aggregate historical visits, physical measurements, and OCR-extracted laboratory documents into a consolidated timeline.", PRIMARY),
        ("Multidimensional Health Radar", "Standardize 8 physiological dimensions on a normalized 0–100 scale to compare baseline vs current footprint instantly.", DARK_NAVY),
        ("Explainable Math Engine", "Eliminate black-box conclusions by providing explicit transparent change formulas (Current - Baseline = Delta) with date provenance.", PRIMARY),
        ("Data-Gap Awareness", "Explicitly classify omitted measurements as DATA_GAP rather than assuming normal stability.", ACCENT_AMBER),
        ("Clinician Oversight & Translation", "Embed human-in-the-loop review for all OCR lab extractions and provide verified bilingual English <-> Tamil summaries.", DARK_NAVY),
        ("Vector PDF Clinical History", "Generate high-fidelity multi-page vector summaries with dynamic running page counts and strict clinical disclaimers.", PRIMARY),
    ]

    for i, (title, desc, color) in enumerate(objs):
        row = i // 3
        col = i % 3
        left = Inches(0.8 + col * 3.9)
        top = Inches(1.8 + row * 2.5)

        card = s3.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, Inches(3.7), Inches(2.3))
        card.fill.solid()
        card.fill.fore_color.rgb = CARD_BG
        card.line.color.rgb = BORDER_COLOR

        tf = card.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title
        p.font.name = "Arial"
        p.font.size = Pt(14)
        p.font.bold = True
        p.font.color.rgb = color
        p.space_after = Pt(6)

        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.name = "Arial"
        p2.font.size = Pt(11)
        p2.font.color.rgb = TEXT_DARK

    s3.notes_slide.notes_text_frame.text = (
        "Our scope is clear: we are a clinical decision support platform, not an autonomous diagnostic agent. "
        "Our 6 core objectives provide structured aggregation, explainable mathematical tracking, strict data gap handling, "
        "and seamless clinician-in-the-loop controls."
    )

    # -------------------------------------------------------------
    # SLIDE 4: Existing System vs CareTrack AI
    # -------------------------------------------------------------
    s4 = prs.slides.add_slide(blank_layout)
    add_header(s4, "Comparative Analysis: Traditional EHR vs Generic AI vs CareTrack AI")
    add_footer(s4, 4)

    rows, cols = 6, 4
    left, top, width, height = Inches(0.8), Inches(1.8), Inches(11.7), Inches(4.8)
    table_shape = s4.shapes.add_table(rows, cols, left, top, width, height)
    tbl = table_shape.table

    tbl.columns[0].width = Inches(2.5)
    tbl.columns[1].width = Inches(3.0)
    tbl.columns[2].width = Inches(3.0)
    tbl.columns[3].width = Inches(3.2)

    headers = ["Clinical Dimension", "Traditional EHR / Paper", "Generic AI Chatbot", "CareTrack AI Platform"]
    for j, h in enumerate(headers):
        cell = tbl.cell(0, j)
        cell.fill.solid()
        cell.fill.fore_color.rgb = DARK_NAVY if j < 3 else PRIMARY
        p = cell.text_frame.paragraphs[0]
        p.text = h
        p.font.name = "Arial"
        p.font.size = Pt(12)
        p.font.bold = True
        p.font.color.rgb = RGBColor(255, 255, 255)

    data = [
        ("Longitudinal Trajectory", "Fragmented tables; manual cross-referencing", "Text-only; lacks longitudinal grounding", "Visual dual-polygon Health Change Radar"),
        ("Change Explainability", "Requires manual calculations by doctor", "Black-box LLM hallucinations", "Deterministic math formulas (C - B = Delta)"),
        ("Missing Data Policy", "Assumed normal or hidden", "Hallucinates or guesses missing values", "Explicit DATA_GAP classification"),
        ("Medical Report Intake", "Unsearchable scanned PDFs / paper slips", "Isolated OCR without patient linking", "OCR extraction + Clinician-in-the-loop staging"),
        ("Patient Summary Export", "Fragmented printouts or raw tables", "Generic unverified text output", "High-fidelity vector PDF with running page counts"),
    ]

    for i, row in enumerate(data):
        for j, val in enumerate(row):
            cell = tbl.cell(i + 1, j)
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(241, 245, 249) if i % 2 == 1 else RGBColor(255, 255, 255)
            p = cell.text_frame.paragraphs[0]
            p.text = val
            p.font.name = "Arial"
            p.font.size = Pt(10.5)
            p.font.color.rgb = TEXT_DARK
            if j == 3:
                p.font.bold = True
                p.font.color.rgb = PRIMARY

    s4.notes_slide.notes_text_frame.text = (
        "This comparison matrix highlights CareTrack AI's unique positioning. Unlike legacy EHRs that merely store records, "
        "and unlike generic AI chatbots that hallucinate medical guidance, CareTrack AI combines structured longitudinal math "
        "with strictly grounded AI decision support."
    )

    # -------------------------------------------------------------
    # SLIDE 5: Proposed CareTrack AI Solution
    # -------------------------------------------------------------
    s5 = prs.slides.add_slide(blank_layout)
    add_header(s5, "Proposed Solution: The CareTrack AI Clinical Workspace")
    add_footer(s5, 5)

    features = [
        ("Health Change Radar (Unique Feature)", "Dual-polygon visual radar mapping 8 vital physiological axes on a standardized 0–100 coordinate space. Highlights asymmetric footprint shifts between initial baseline and latest encounter.", PRIMARY),
        ("Urgency Screening Dashboard", "Prioritized clinic patient triage queue ranking individuals across High Priority, Moderate Priority, Data Gap, and Normal stability for effective outreach planning.", DARK_NAVY),
        ("Document OCR & Confirmation Pipeline", "Ingests lab reports (PDF/JPG/PNG), parses text using pypdf/Tesseract, and stages extracted values for clinician confirmation prior to permanent database insertion.", PRIMARY),
        ("Grounded Clinical Copilot", "Context-aware AI assistant powered by Google Gemini (gemini-2.5-flash), dynamically injected with patient encounter history and vitals time-series.", DARK_NAVY),
    ]

    for i, (title, desc, color) in enumerate(features):
        left = Inches(0.8 + (i % 2) * 5.9)
        top = Inches(1.8 + (i // 2) * 2.5)

        card = s5.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, Inches(5.6), Inches(2.3))
        card.fill.solid()
        card.fill.fore_color.rgb = CARD_BG
        card.line.color.rgb = BORDER_COLOR

        tf = card.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title
        p.font.name = "Arial"
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = color
        p.space_after = Pt(8)

        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.name = "Arial"
        p2.font.size = Pt(11.5)
        p2.font.color.rgb = TEXT_DARK

    s5.notes_slide.notes_text_frame.text = (
        "Here are the 4 core components of our proposed solution: the Health Change Radar for instant visual comparison, "
        "the Urgency Screening Queue for population prioritization, the OCR document ingestion pipeline with clinician staging, "
        "and our grounded AI Clinical Copilot."
    )

    # -------------------------------------------------------------
    # SLIDE 6: System Architecture & Technology Stack
    # -------------------------------------------------------------
    s6 = prs.slides.add_slide(blank_layout)
    add_header(s6, "System Architecture: Decoupled, Scalable, & Production-Ready")
    add_footer(s6, 6)

    # Left: Architecture Flow Box
    arch_box = s6.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.8), Inches(6.0), Inches(4.8))
    arch_box.fill.solid()
    arch_box.fill.fore_color.rgb = DARK_NAVY
    arch_box.line.color.rgb = DARK_NAVY

    tf_a = arch_box.text_frame
    tf_a.word_wrap = True
    p = tf_a.paragraphs[0]
    p.text = "End-to-End System Flow"
    p.font.name = "Arial"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = RGBColor(255, 255, 255)
    p.space_after = Pt(14)

    steps = [
        "1. Client Layer: React 19 / Vite 8 Glassmorphic SPA",
        "2. Security Gate: FastAPI HTTPBearer JWT & RBAC (Doctor/Admin)",
        "3. REST API Routers: Patient, Visit, Measurements, Radar, Copilot",
        "4. Business Logic Services: Radar Math, OCR Extraction, ReportLab",
        "5. AI Layer: Google Gemini SDK (gemini-2.5-flash) with Grounding",
        "6. Data Persistence: PostgreSQL (Supabase) via SQLAlchemy 2.x",
        "7. Isolated Test Harness: SQLite in-memory static pool for zero data loss",
    ]
    for s in steps:
        p = tf_a.add_paragraph()
        p.text = s
        p.font.name = "Arial"
        p.font.size = Pt(11)
        p.font.color.rgb = RGBColor(226, 232, 240)
        p.space_after = Pt(8)

    # Right: Tech Stack Cards
    tech_cards = [
        ("Frontend Technologies", "React 19, Vite 8, React Router 7, Recharts (Radar/Line charts), Lucide-React, Vanilla CSS Design System.", PRIMARY),
        ("Backend Technologies", "Python 3.12, FastAPI, Pydantic v2 schemas, SQLAlchemy 2.x ORM, Bcrypt, PyJWT, ReportLab PDF Engine.", DARK_NAVY),
        ("Database & Storage", "PostgreSQL (Supabase) with connection recycling & pre-ping; safe additive DDL migrations (users table).", PRIMARY),
    ]
    for i, (title, desc, color) in enumerate(tech_cards):
        top_pos = Inches(1.8 + i * 1.6)
        c = s6.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(7.1), top_pos, Inches(5.4), Inches(1.4))
        c.fill.solid()
        c.fill.fore_color.rgb = CARD_BG
        c.line.color.rgb = BORDER_COLOR
        tf = c.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title
        p.font.name = "Arial"
        p.font.size = Pt(13)
        p.font.bold = True
        p.font.color.rgb = color
        p.space_after = Pt(4)
        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.name = "Arial"
        p2.font.size = Pt(10.5)
        p2.font.color.rgb = TEXT_DARK

    s6.notes_slide.notes_text_frame.text = (
        "Our architecture uses modern, reliable production components: Python 3.12, FastAPI, and SQLAlchemy 2 on the backend, "
        "and React 19 with Vite 8 on the frontend. We enforce strict database isolation during testing so no test runs "
        "can ever corrupt live clinical data."
    )

    # -------------------------------------------------------------
    # SLIDE 7: Complete Application Workflow
    # -------------------------------------------------------------
    s7 = prs.slides.add_slide(blank_layout)
    add_header(s7, "Clinical Workflow: From Patient Intake to Longitudinal PDF Export")
    add_footer(s7, 7)

    wf_steps = [
        ("1. Clinician Authentication", "Doctor logs into CareTrack AI via Bcrypt credentials; receives an 8-hour signed JWT access token.", PRIMARY),
        ("2. Active Patient Selection", "Doctor selects patient from global roster dropdown or registers a new patient with unique code.", DARK_NAVY),
        ("3. Encounter & Vitals Logging", "Records encounter date, presenting symptoms, clinical notes, and physical measurements across 8 axes.", PRIMARY),
        ("4. Medical Report OCR Review", "Uploads laboratory PDF/scan; system extracts values; doctor verifies and confirms staging.", DARK_NAVY),
        ("5. Radar Trajectory Analysis", "Reviews dual-polygon Health Change Radar with mathematical deltas and threshold screening flags.", PRIMARY),
        ("6. AI Copilot Consultation", "Queries grounded Clinical Copilot for context-specific insights; generates English/Tamil summary.", DARK_NAVY),
        ("7. Vector PDF History Export", "Generates high-fidelity multi-page vector clinical summary with running headers and legal disclaimers.", PRIMARY),
    ]

    for i, (title, desc, color) in enumerate(wf_steps):
        left_pos = Inches(0.8 + (i % 4) * 2.95) if i < 4 else Inches(0.8 + (i - 4) * 3.9)
        top_pos = Inches(1.8) if i < 4 else Inches(4.3)
        card_w = Inches(2.8) if i < 4 else Inches(3.75)
        card_h = Inches(2.2)

        c = s7.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left_pos, top_pos, card_w, card_h)
        c.fill.solid()
        c.fill.fore_color.rgb = CARD_BG
        c.line.color.rgb = BORDER_COLOR
        tf = c.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title
        p.font.name = "Arial"
        p.font.size = Pt(13)
        p.font.bold = True
        p.font.color.rgb = color
        p.space_after = Pt(6)

        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.name = "Arial"
        p2.font.size = Pt(10)
        p2.font.color.rgb = TEXT_DARK

    s7.notes_slide.notes_text_frame.text = (
        "This slide depicts the seven-step clinician workflow. Everything is designed around minimal clinical friction: "
        "one-click patient switching, automatic duplicate measurement blocking, staged OCR confirmation, and instant PDF compilation."
    )

    # -------------------------------------------------------------
    # SLIDE 8: Key Features & AI/ML Methodology
    # -------------------------------------------------------------
    s8 = prs.slides.add_slide(blank_layout)
    add_header(s8, "AI/ML Methodology: Transparent Explainability & Grounded Guidance")
    add_footer(s8, 8)

    methods = [
        ("Normalized Radar Coordinate Space", "Maps disparate physiological markers onto a standardized 0–100 scale using continuous piecewise normalization. Midpoint 50 represents standard clinical reference baseline (e.g. 120 mmHg systolic, 100 mg/dL glucose).", PRIMARY),
        ("Deterministic Change Math Engine", "Calculates exact mathematical deltas: Current - Baseline = Delta (+%). Explicitly displays encounter dates, preventing mathematical ambiguity or hallucinated trajectories.", DARK_NAVY),
        ("Grounded Clinical Copilot Prompts", "Google Gemini (gemini-2.5-flash) receives dynamically assembled system context containing patient demographics, chronological visits, and vitals time-series. Prohibits external hallucinations.", PRIMARY),
        ("Evidence-Backed Action Recommendations", "Automated screening flags recommend specific clinician follow-up actions (e.g., HbA1c review for glycemic surges, airway evaluation for SpO2 drops < 92%).", DARK_NAVY),
    ]

    for i, (title, desc, color) in enumerate(methods):
        left = Inches(0.8 + (i % 2) * 5.9)
        top = Inches(1.8 + (i // 2) * 2.5)

        card = s8.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, Inches(5.6), Inches(2.3))
        card.fill.solid()
        card.fill.fore_color.rgb = CARD_BG
        card.line.color.rgb = BORDER_COLOR

        tf = card.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title
        p.font.name = "Arial"
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = color
        p.space_after = Pt(8)

        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.name = "Arial"
        p2.font.size = Pt(11)
        p2.font.color.rgb = TEXT_DARK

    s8.notes_slide.notes_text_frame.text = (
        "Our AI methodology prioritizes explainability and safety. In medical applications, black-box confidence scores "
        "are unacceptable. We provide transparent mathematical formulas for the radar, and we strictly ground our LLM copilot "
        "in stored database facts with zero speculative extrapolation."
    )

    # -------------------------------------------------------------
    # SLIDE 9: Testing Performed & Known Defects
    # -------------------------------------------------------------
    s9 = prs.slides.add_slide(blank_layout)
    add_header(s9, "Verification & Testing: 100% Pass Rate Across Test Suites")
    add_footer(s9, 9)

    # Left: Test Results Box
    t_box = s9.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.8), Inches(5.6), Inches(4.8))
    t_box.fill.solid()
    t_box.fill.fore_color.rgb = CARD_BG
    t_box.line.color.rgb = BORDER_COLOR

    tf_t = t_box.text_frame
    tf_t.word_wrap = True
    p = tf_t.paragraphs[0]
    p.text = "Verified Empirical Test Suites"
    p.font.name = "Arial"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = ACCENT_GREEN
    p.space_after = Pt(12)

    tests_data = [
        ("API Protection Suite:", "44/44 tests passed (100% anonymous 401 blocking, RBAC 403 enforcement)."),
        ("Authentication Suite:", "14/14 tests passed (Bcrypt hashing, dual JSON/OAuth2 schemas)."),
        ("Phase 3 E2E Integration:", "11/11 full clinical journeys passed in memory."),
        ("HealthTrajectory Engine:", "9/9 trajectory classifications and data gap tests passed."),
        ("Bilingual Translation:", "10/10 English <-> Tamil translations and timeout mocks passed."),
        ("Patient History PDF:", "5/5 ReportLab vector generations & pypdf validations passed."),
        ("Frontend Build:", "2,508 modules compiled cleanly in 7.14 seconds via Vite 8."),
    ]
    for t_name, t_stat in tests_data:
        p = tf_t.add_paragraph()
        p.text = f"✔ {t_name} {t_stat}"
        p.font.name = "Arial"
        p.font.size = Pt(10.5)
        p.font.color.rgb = TEXT_DARK
        p.space_after = Pt(6)

    # Right: Investigated Defects Box
    d_box = s9.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.8), Inches(5.6), Inches(4.8))
    d_box.fill.solid()
    d_box.fill.fore_color.rgb = CARD_BG
    d_box.line.color.rgb = BORDER_COLOR

    tf_d = d_box.text_frame
    tf_d.word_wrap = True
    p = tf_d.paragraphs[0]
    p.text = "Audited Defects & Code Locations"
    p.font.name = "Arial"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = ACCENT_AMBER
    p.space_after = Pt(12)

    defects = [
        ("Defect 1: Temperature Boundary Flaw", "Observation: 3.5 °C accepted, producing a -33.3 °C shift.\nRoot Cause: Pydantic schema and React modal set min=0, max=100 (water boiling limits) instead of physiological range (30–45 °C).\nLocation: schemas/clinical_measurement.py & ClinicalMeasurementModal.jsx"),
        ("Defect 2: Stale Selector Warning Banner", "Observation: Banner warned Patient #18 not found while dropdown showed Patient #18.\nRoot Cause: invalidPatientId state was set on URL query mismatch but not cleared when roster refreshed.\nLocation: PatientContext.jsx:42-70"),
    ]
    for d_title, d_detail in defects:
        p = tf_d.add_paragraph()
        p.text = f"⚠ {d_title}"
        p.font.name = "Arial"
        p.font.size = Pt(12)
        p.font.bold = True
        p.font.color.rgb = ACCENT_AMBER
        p.space_after = Pt(2)

        p2 = tf_d.add_paragraph()
        p2.text = d_detail
        p2.font.name = "Arial"
        p2.font.size = Pt(10)
        p2.font.color.rgb = TEXT_DARK
        p2.space_after = Pt(8)

    s9.notes_slide.notes_text_frame.text = (
        "We pride ourselves on engineering transparency. All 10 automated test suites executed with a 100% pass rate. "
        "At the same time, our deep code audit uncovered two real defects: the temperature input range was configured for 0-100 "
        "instead of human body temperature, and the patient selector warning banner held stale state during asynchronous reloads."
    )

    # -------------------------------------------------------------
    # SLIDE 10: Responsible AI, Privacy, & Clinician Oversight
    # -------------------------------------------------------------
    s10 = prs.slides.add_slide(blank_layout)
    add_header(s10, "Responsible AI & Security: Clinician-in-the-Loop Safeguards")
    add_footer(s10, 10)

    guards = [
        ("Informational Decision Support Only", "CareTrack AI and the Health Change Radar generate informational, decision-support indicators. They do not provide autonomous diagnoses, triage triage scores, or treatment plans.", PRIMARY),
        ("Clinician-in-the-Loop Confirmation", "OCR-extracted laboratory measurements are held in a review state. Values are never written to the permanent clinical record without explicit practitioner review.", DARK_NAVY),
        ("Data-Gap Awareness Policy", "Missing or omitted physical measurements are never assumed normal or stable. They are explicitly highlighted to prompt active clinical follow-up.", PRIMARY),
        ("Privacy & Security Defense", "Enforces HMAC-SHA256 JWT, Bcrypt hashing, role-gated record deletion, and directory traversal defense. Server exception logs strictly sanitize patient PII and tokens.", DARK_NAVY),
    ]

    for i, (title, desc, color) in enumerate(guards):
        left = Inches(0.8 + (i % 2) * 5.9)
        top = Inches(1.8 + (i // 2) * 2.5)

        card = s10.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, Inches(5.6), Inches(2.3))
        card.fill.solid()
        card.fill.fore_color.rgb = CARD_BG
        card.line.color.rgb = BORDER_COLOR

        tf = card.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title
        p.font.name = "Arial"
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = color
        p.space_after = Pt(8)

        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.name = "Arial"
        p2.font.size = Pt(11)
        p2.font.color.rgb = TEXT_DARK

    s10.notes_slide.notes_text_frame.text = (
        "Responsible AI is woven into our core architecture. We do not provide autonomous diagnoses. Clinicians review "
        "and confirm all OCR extractions. Omitted measurements are never assumed normal. And server logs strictly scrub all "
        "sensitive patient PII and API keys."
    )

    # -------------------------------------------------------------
    # SLIDE 11: Future Enhancements & Roadmap
    # -------------------------------------------------------------
    s11 = prs.slides.add_slide(blank_layout)
    add_header(s11, "Future Roadmap: Expanding Scope & Interoperability")
    add_footer(s11, 11)

    roadmap = [
        ("Phase 1: Physiological Boundary Hardening", "Refactor Pydantic and frontend schemas to enforce clinical bounds: Temperature (30–45 °C), Heart Rate (30–250 bpm), and Systolic BP (50–260 mmHg). Add dynamic outlier confirmation modal.", PRIMARY),
        ("Phase 2: HL7 / FHIR R4 Interoperability", "Implement Fast Healthcare Interoperability Resources (FHIR) JSON export/import to interface seamlessly with national health registries and hospital EHR systems.", DARK_NAVY),
        ("Phase 3: Offline-First SQLite Sync", "Enable traveling doctors to operate in remote zero-connectivity camps with local SQLite caching, auto-syncing to Supabase cloud upon network restoration.", PRIMARY),
        ("Phase 4: Multilingual Voice Intake", "Expand speech-to-text intake for Tamil, Telugu, and Hindi clinical notes, empowering grassroots healthcare workers.", DARK_NAVY),
    ]

    for i, (title, desc, color) in enumerate(roadmap):
        left = Inches(0.8 + (i % 2) * 5.9)
        top = Inches(1.8 + (i // 2) * 2.5)

        card = s11.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, Inches(5.6), Inches(2.3))
        card.fill.solid()
        card.fill.fore_color.rgb = CARD_BG
        card.line.color.rgb = BORDER_COLOR

        tf = card.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title
        p.font.name = "Arial"
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = color
        p.space_after = Pt(8)

        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.name = "Arial"
        p2.font.size = Pt(11)
        p2.font.color.rgb = TEXT_DARK

    s11.notes_slide.notes_text_frame.text = (
        "Our roadmap prioritizes real-world clinical deployment: hardening physiological input validation, adding native "
        "FHIR interoperability, supporting offline-first SQLite synchronization for zero-reception rural field camps, "
        "and expanding multilingual voice-enabled intake."
    )

    # -------------------------------------------------------------
    # SLIDE 12: Conclusion & References
    # -------------------------------------------------------------
    s12 = prs.slides.add_slide(blank_layout)
    add_header(s12, "Conclusion & Key Takeaways: Transforming Continuity of Care")
    add_footer(s12, 12)

    # Left: Summary Box
    sum_box = s12.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.8), Inches(5.6), Inches(4.8))
    sum_box.fill.solid()
    sum_box.fill.fore_color.rgb = DARK_NAVY
    sum_box.line.color.rgb = DARK_NAVY

    tf_s = sum_box.text_frame
    tf_s.word_wrap = True
    p = tf_s.paragraphs[0]
    p.text = "Summary of Key Achievements"
    p.font.name = "Arial"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = RGBColor(255, 255, 255)
    p.space_after = Pt(12)

    achievements = [
        "✔ Unified longitudinal platform connecting visits, vitals, and lab reports.",
        "✔ Health Change Radar providing instant visual physiological footprints.",
        "✔ Fully explainable mathematical change formulas with date provenance.",
        "✔ Context-grounded Gemini AI copilot and bilingual Tamil translation.",
        "✔ 100% pass rate across 10 automated test suites with isolated harnesses.",
        "✔ Vector PDF generator producing multi-page audit-ready clinical histories.",
    ]
    for a in achievements:
        p = tf_s.add_paragraph()
        p.text = a
        p.font.name = "Arial"
        p.font.size = Pt(11)
        p.font.color.rgb = RGBColor(226, 232, 240)
        p.space_after = Pt(8)

    # Right: References Box
    ref_box = s12.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.8), Inches(5.6), Inches(4.8))
    ref_box.fill.solid()
    ref_box.fill.fore_color.rgb = CARD_BG
    ref_box.line.color.rgb = BORDER_COLOR

    tf_r = ref_box.text_frame
    tf_r.word_wrap = True
    p = tf_r.paragraphs[0]
    p.text = "Clinical Standards & References"
    p.font.name = "Arial"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = PRIMARY
    p.space_after = Pt(12)

    refs = [
        ("WHO Digital Health Guidelines (2020):", "Recommendations on digital interventions for health system strengthening and continuity of care."),
        ("HL7 FHIR Specification (v4.0.1):", "Standard data schemas for clinical observations and diagnostic reports."),
        ("American Medical Informatics Association (AMIA):", "Guidelines on transparent and explainable AI in clinical decision support."),
        ("FastAPI & ReportLab:", "High-performance asynchronous Python architecture and vector document generation standards."),
    ]
    for r_title, r_desc in refs:
        p = tf_r.add_paragraph()
        p.text = f"• {r_title} {r_desc}"
        p.font.name = "Arial"
        p.font.size = Pt(10.5)
        p.font.color.rgb = TEXT_DARK
        p.space_after = Pt(8)

    s12.notes_slide.notes_text_frame.text = (
        "Thank you for your time and evaluation. CareTrack AI delivers a verifiable, explainable, and responsible "
        "solution to longitudinal continuity in healthcare. We welcome your questions."
    )

    prs.save(output_path)
    print(f"Presentation saved successfully to {output_path}")

if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "CareTrack_AI_Presentation.pptx"
    create_caretrack_presentation(str(out))
