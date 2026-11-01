import io
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.patient import Patient
from app.models.visit import Visit
from app.models.clinical_measurement import ClinicalMeasurement
from app.models.medical_report import MedicalReport


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and draw total page count
    and persistent running header/footer on every page.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#71849a"))

        # Footer
        footer_text = f"CareTrack AI · Longitudinal Patient History · Page {self._pageNumber} of {page_count}"
        self.drawString(36, 24, footer_text)
        confidential_text = "CONFIDENTIAL MEDICAL RECORD — NOT A DIAGNOSIS"
        self.drawRightString(letter[0] - 36, 24, confidential_text)

        # Subtle footer separator
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(36, 34, letter[0] - 36, 34)

        self.restoreState()


def format_value(val: Optional[float], unit: str) -> str:
    if val is None:
        return "— (Not recorded)"
    # Format nicely without trailing zeros if integer
    if val == int(val):
        return f"{int(val)} {unit}"
    return f"{val:.1f} {unit}"


def generate_patient_history_pdf(
    patient: Patient,
    visits: list[Visit],
    measurements: list[ClinicalMeasurement],
    reports: list[MedicalReport],
    radar_data: Optional[dict] = None,
) -> bytes:
    """
    Compiles a comprehensive, professional clinical history PDF
    for the specified patient using stored database records.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=45,
    )

    styles = getSampleStyleSheet()

    # Custom typography matching CareTrack AI brand
    brand_primary = colors.HexColor("#087f8c")
    brand_dark = colors.HexColor("#17324d")
    text_muted = colors.HexColor("#475569")
    bg_surface = colors.HexColor("#f8fafc")
    border_color = colors.HexColor("#cbd5e1")
    alert_red = colors.HexColor("#b91c1c")
    alert_amber = colors.HexColor("#92400e")
    alert_green = colors.HexColor("#047857")

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=brand_dark,
        spaceAfter=2,
    )

    eyebrow_style = ParagraphStyle(
        "Eyebrow",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=brand_primary,
        textTransform="uppercase",
        spaceAfter=4,
    )

    h2_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=brand_dark,
        spaceBefore=14,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        "DocBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=brand_dark,
    )

    muted_style = ParagraphStyle(
        "DocMuted",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8.5,
        leading=12,
        textColor=text_muted,
    )

    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10.5,
        textColor=text_muted,
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
    )

    table_cell_style = ParagraphStyle(
        "TableCell",
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=brand_dark,
    )

    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=brand_dark,
    )

    story = []

    # ---------------------------------------------------------
    # 1. HEADER & BRANDING
    # ---------------------------------------------------------
    header_data = [
        [
            Paragraph("CARETRACK AI · LONGITUDINAL HEALTHCARE PLATFORM", eyebrow_style),
            Paragraph(f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}", muted_style),
        ],
        [
            Paragraph("Patient Clinical History & Longitudinal Trajectory", title_style),
            Paragraph(f"Patient ID: <b>#{patient.id}</b> | Code: <b>{patient.patient_code}</b>", body_style),
        ],
    ]
    header_table = Table(header_data, colWidths=[4.2 * inch, 3.1 * inch])
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=brand_primary, spaceBefore=4, spaceAfter=10))

    # ---------------------------------------------------------
    # 2. PATIENT DEMOGRAPHICS SUMMARY
    # ---------------------------------------------------------
    demo_data = [
        [
            Paragraph("<b>Full Name:</b>", body_style),
            Paragraph(patient.name or "Unknown", body_style),
            Paragraph("<b>Patient Code:</b>", body_style),
            Paragraph(patient.patient_code, body_style),
        ],
        [
            Paragraph("<b>Age / Gender:</b>", body_style),
            Paragraph(
                f"{patient.age} yrs" if patient.age is not None else "Age unrecorded"
                + f" · {patient.gender or 'Unspecified'}",
                body_style,
            ),
            Paragraph("<b>Phone Contact:</b>", body_style),
            Paragraph(patient.phone or "Not on file", body_style),
        ],
        [
            Paragraph("<b>Registered Location:</b>", body_style),
            Paragraph(patient.location or "Unspecified Location", body_style),
            Paragraph("<b>Recorded Visits:</b>", body_style),
            Paragraph(f"<b>{len(visits)}</b> visits on record", body_style),
        ],
    ]
    demo_table = Table(demo_data, colWidths=[1.4 * inch, 2.35 * inch, 1.4 * inch, 2.15 * inch])
    demo_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), bg_surface),
                ("BOX", (0, 0), (-1, -1), 0.5, border_color),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(demo_table)
    story.append(Spacer(1, 10))

    # ---------------------------------------------------------
    # 3. HEALTH CHANGE RADAR / LONGITUDINAL TRAJECTORY SUMMARY
    # ---------------------------------------------------------
    if radar_data and radar_data.get("summary"):
        r_sum = radar_data["summary"]
        r_metrics = radar_data.get("radar_metrics", [])

        story.append(Paragraph("Longitudinal Health Change Radar & Trajectory", h2_style))

        # Narrative block
        narrative_p = Paragraph(
            f"<b>Longitudinal Summary ({r_sum.get('overall_status', '').replace('_', ' ')}):</b> "
            f"{r_sum.get('evidence_narrative', 'No longitudinal narrative available.')}",
            body_style,
        )
        narrative_table = Table([[narrative_p]], colWidths=[7.3 * inch])
        narrative_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0fdfa")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#99f6e4")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(narrative_table)
        story.append(Spacer(1, 8))

        # Radar Metrics Table
        if r_metrics:
            radar_table_data = [
                [
                    Paragraph("Physiological Dimension", table_header_style),
                    Paragraph("Baseline Visit", table_header_style),
                    Paragraph("Current Visit", table_header_style),
                    Paragraph("Longitudinal Change", table_header_style),
                    Paragraph("Status / Decision Support", table_header_style),
                ]
            ]

            for rm in r_metrics:
                b_str = (
                    f"{rm['baseline_value']} {rm['unit']}<br/><font size=7 color='#64748b'>({rm.get('baseline_date') or 'Initial'})</font>"
                    if rm.get("baseline_value") is not None
                    else "<font color='#94a3b8'>— (Not recorded)</font>"
                )
                c_str = (
                    f"{rm['current_value']} {rm['unit']}<br/><font size=7 color='#64748b'>({rm.get('current_date') or 'Latest'})</font>"
                    if rm.get("current_value") is not None
                    else "<font color='#dc2626'><b>Missing at check-in</b></font>"
                )

                if rm.get("delta") is not None:
                    delta_val = rm["delta"]
                    pct_val = rm.get("percent_change", 0.0)
                    sign = "+" if delta_val > 0 else ""
                    d_color = "#b91c1c" if abs(pct_val) >= 10 else "#0f766e"
                    change_str = f"<font color='{d_color}'><b>{sign}{delta_val} {rm['unit']}</b> ({sign}{pct_val}%)</font>"
                else:
                    change_str = "<font color='#64748b'>N/A (Data Gap)</font>"

                # Status pill
                status_label = rm.get("alert_level", "STABLE").replace("_", " ")
                if rm.get("alert_level") == "HIGH_ATTENTION":
                    status_str = f"<font color='#b91c1c'><b>{status_label}</b></font>"
                elif rm.get("alert_level") == "MODERATE_ATTENTION":
                    status_str = f"<font color='#92400e'><b>{status_label}</b></font>"
                elif rm.get("alert_level") == "DATA_GAP":
                    status_str = f"<font color='#64748b'><b>DATA GAP</b></font>"
                else:
                    status_str = f"<font color='#047857'><b>STABLE</b></font>"

                radar_table_data.append(
                    [
                        Paragraph(f"<b>{rm['label']}</b>", table_cell_bold),
                        Paragraph(b_str, table_cell_style),
                        Paragraph(c_str, table_cell_style),
                        Paragraph(change_str, table_cell_style),
                        Paragraph(status_str, table_cell_style),
                    ]
                )

            rt = Table(radar_table_data, colWidths=[1.6 * inch, 1.4 * inch, 1.4 * inch, 1.4 * inch, 1.5 * inch])
            rt.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), brand_dark),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("BOX", (0, 0), (-1, -1), 0.5, border_color),
                        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, bg_surface]),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(rt)
            story.append(Spacer(1, 12))

    # ---------------------------------------------------------
    # 4. CHRONOLOGICAL VISIT & MEASUREMENT LOGS
    # ---------------------------------------------------------
    story.append(Paragraph("Chronological Visit Records & Vitals", h2_style))

    if not visits:
        story.append(
            Paragraph("No clinical visits have been registered for this patient yet.", muted_style)
        )
    else:
        # Map measurements and reports by visit_id
        meas_map: dict[int, list[ClinicalMeasurement]] = {}
        for m in measurements:
            meas_map.setdefault(m.visit_id, []).append(m)

        report_map: dict[int, list[MedicalReport]] = {}
        for r in reports:
            report_map.setdefault(r.visit_id, []).append(r)

        for idx, visit in enumerate(visits, 1):
            visit_elements = []

            # Visit Header Pill
            v_date_str = visit.visit_date.strftime("%d %B %Y") if hasattr(visit.visit_date, "strftime") else str(visit.visit_date)
            v_header_text = f"Visit #{visit.id} · {v_date_str}"
            v_header_data = [[
                Paragraph(f"<b>{v_header_text}</b>", ParagraphStyle("VH", fontName="Helvetica-Bold", fontSize=9.5, textColor=brand_primary)),
                Paragraph(f"Visit ID: #{visit.id}", ParagraphStyle("VHR", fontName="Helvetica", fontSize=8.5, textColor=text_muted, alignment=2)),
            ]]
            v_ht = Table(v_header_data, colWidths=[4.8 * inch, 2.5 * inch])
            v_ht.setStyle(TableStyle([
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]))
            visit_elements.append(v_ht)
            visit_elements.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#e2e8f0"), spaceBefore=2, spaceAfter=5))

            # Clinical Observations / Notes
            notes_rows = []
            if visit.symptoms:
                notes_rows.append([
                    Paragraph("<b>Presenting Symptoms:</b>", table_cell_bold),
                    Paragraph(visit.symptoms, table_cell_style),
                ])
            else:
                notes_rows.append([
                    Paragraph("<b>Presenting Symptoms:</b>", table_cell_bold),
                    Paragraph("<i>None documented</i>", muted_style),
                ])

            if visit.clinical_notes:
                notes_rows.append([
                    Paragraph("<b>Clinical Notes:</b>", table_cell_bold),
                    Paragraph(visit.clinical_notes, table_cell_style),
                ])

            if visit.follow_up_notes:
                notes_rows.append([
                    Paragraph("<b>Follow-up Plan:</b>", table_cell_bold),
                    Paragraph(visit.follow_up_notes, table_cell_style),
                ])

            notes_table = Table(notes_rows, colWidths=[1.6 * inch, 5.7 * inch])
            notes_table.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                        ("LEFTPADDING", (0, 0), (-1, -1), 2),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ]
                )
            )
            visit_elements.append(notes_table)
            visit_elements.append(Spacer(1, 5))

            # Measurements Table for this visit
            v_measurements = meas_map.get(visit.id, [])
            if v_measurements:
                latest_m = v_measurements[-1]
                bp_display = latest_m.blood_pressure or (
                    f"{latest_m.systolic_bp}/{latest_m.diastolic_bp} mmHg"
                    if latest_m.systolic_bp and latest_m.diastolic_bp
                    else "— (Not recorded)"
                )

                vitals_grid = [
                    [
                        Paragraph("<b>Blood Pressure:</b>", table_cell_style),
                        Paragraph(bp_display, table_cell_style),
                        Paragraph("<b>Blood Glucose:</b>", table_cell_style),
                        Paragraph(format_value(latest_m.blood_glucose, "mg/dL"), table_cell_style),
                    ],
                    [
                        Paragraph("<b>Heart Rate:</b>", table_cell_style),
                        Paragraph(format_value(latest_m.heart_rate, "bpm"), table_cell_style),
                        Paragraph("<b>Oxygen Saturation:</b>", table_cell_style),
                        Paragraph(format_value(latest_m.oxygen_saturation, "%"), table_cell_style),
                    ],
                    [
                        Paragraph("<b>Body Temperature:</b>", table_cell_style),
                        Paragraph(format_value(latest_m.temperature, "°C"), table_cell_style),
                        Paragraph("<b>Hemoglobin:</b>", table_cell_style),
                        Paragraph(format_value(latest_m.hemoglobin, "g/dL"), table_cell_style),
                    ],
                    [
                        Paragraph("<b>Body Weight:</b>", table_cell_style),
                        Paragraph(format_value(latest_m.weight, "kg"), table_cell_style),
                        Paragraph("<b>Recorded At:</b>", table_cell_style),
                        Paragraph(
                            latest_m.measured_at.strftime("%H:%M") if latest_m.measured_at else "Standard intake",
                            muted_style,
                        ),
                    ],
                ]
                vt = Table(vitals_grid, colWidths=[1.5 * inch, 2.15 * inch, 1.5 * inch, 2.15 * inch])
                vt.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, -1), bg_surface),
                            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#f1f5f9")),
                            ("TOPPADDING", (0, 0), (-1, -1), 3),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                            ("LEFTPADDING", (0, 0), (-1, -1), 6),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ]
                    )
                )
                visit_elements.append(vt)
            else:
                visit_elements.append(
                    Paragraph("<i>No physical vitals or measurements recorded during this visit.</i>", muted_style)
                )

            # Attached Medical Reports
            v_reports = report_map.get(visit.id, [])
            if v_reports:
                visit_elements.append(Spacer(1, 4))
                report_texts = [f"<b>Attached Reports ({len(v_reports)}):</b> "]
                for rpt in v_reports:
                    report_texts.append(f"{rpt.file_name or 'Report #' + str(rpt.id)} ({rpt.file_type or 'PDF'})")
                visit_elements.append(Paragraph(" · ".join(report_texts), muted_style))

            visit_elements.append(Spacer(1, 10))
            story.append(KeepTogether(visit_elements))

    # ---------------------------------------------------------
    # 5. REGULATORY & CLINICAL RESPONSIBLE AI DISCLAIMER
    # ---------------------------------------------------------
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=border_color, spaceBefore=4, spaceAfter=8))
    disclaimer_text = (
        "<b>CLINICAL DECISION SUPPORT NOTICE:</b> This document is an informational compilation of historical "
        "patient health records generated for licensed medical practitioner decision support. It does not "
        "constitute an automated diagnosis, triage score, or treatment plan. Unmeasured, omitted, or stale vital "
        "signs must never be assumed normal or stable without direct clinical examination. All observations "
        "must be reviewed and confirmed by a qualified healthcare professional."
    )
    story.append(Paragraph(disclaimer_text, disclaimer_style))

    # Build the document using the two-pass NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    return buffer.getvalue()
