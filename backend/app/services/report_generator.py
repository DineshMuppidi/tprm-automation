"""Assessment report generation (Phase 1 §5) — PDF via reportlab (pure
Python, no system font/rendering libraries required, so it runs the same
in CI, a laptop, or the air-gapped on-prem deployment target)."""

import io
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

_STYLES = getSampleStyleSheet()
_TITLE = ParagraphStyle("TPRMTitle", parent=_STYLES["Title"], textColor=colors.HexColor("#1f3864"))
_H2 = ParagraphStyle("TPRMH2", parent=_STYLES["Heading2"], textColor=colors.HexColor("#1f3864"))
_BODY = _STYLES["BodyText"]

_TIER_LABELS = {
    "tier_1_critical": "Tier 1 — Critical",
    "tier_2_high": "Tier 2 — High",
    "tier_3_medium": "Tier 3 — Medium",
    "tier_4_low": "Tier 4 — Low",
}

_STATUS_LABELS = {
    "in_progress": "In Progress",
    "completed": "Completed",
    "expired": "Expired",
}

_CLASSIFICATION_HEX = {
    "strong": "#2e7d32",
    "adequate": "#f9a825",
    "weak": "#ef6c00",
    "missing": "#c62828",
    "contradictory": "#b71c1c",
    "unanalyzed": "#757575",
}


def _risk_band(vendor_risk_score: float) -> str:
    if vendor_risk_score < 40:
        return "Low"
    if vendor_risk_score <= 70:
        return "Medium"
    return "High"


def generate_assessment_report_pdf(
    *,
    vendor_name: str,
    tier: str,
    template_name: str,
    status: str,
    completed_at: datetime | None,
    overall_score: float | None,
    vendor_risk_score: float | None,
    classification_counts: dict[str, int],
    control_scores: list[dict],
    responses: list[dict],   # {section, prompt, raw_answer, classification, confidence_score, follow_up_question}
    evidence: list[dict],    # {original_filename, document_type, uploaded_at}
    reviewer_name: str | None = None,
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    )
    story = []

    story.append(Paragraph("Third-Party Risk Assessment Report", _TITLE))
    story.append(Paragraph(vendor_name, _H2))
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    tier_label = _TIER_LABELS.get(tier, tier)
    status_label = _STATUS_LABELS.get(status, status.replace("_", " ").title())
    story.append(Paragraph(
        f"Template: {template_name} &nbsp;|&nbsp; Tier: {tier_label} &nbsp;|&nbsp; "
        f"Status: {status_label} &nbsp;|&nbsp; Report generated: {generated}", _BODY,
    ))
    story.append(Spacer(1, 0.25 * inch))

    # --- Executive summary -------------------------------------------------
    story.append(Paragraph("Executive Summary", _H2))
    if overall_score is not None and vendor_risk_score is not None:
        band = _risk_band(vendor_risk_score)
        story.append(Paragraph(
            f"Compliance strength score: <b>{overall_score:.0f}/100</b>. "
            f"Vendor risk exposure: <b>{vendor_risk_score:.0f}/100 ({band})</b>.", _BODY,
        ))
    gaps = [r for r in responses if r.get("classification") in ("weak", "missing", "contradictory")]
    if gaps:
        story.append(Paragraph(f"{len(gaps)} response(s) flagged as weak, missing, or contradictory:", _BODY))
        gap_rows = [[Paragraph(g["prompt"], _BODY), Paragraph((g.get("classification") or "").title(), _BODY)] for g in gaps[:15]]
        t = Table([[Paragraph("<b>Question</b>", _BODY), Paragraph("<b>Finding</b>", _BODY)]] + gap_rows,
                   colWidths=[4.3 * inch, 1.5 * inch])
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No weak, missing, or contradictory responses identified.", _BODY))
    story.append(Spacer(1, 0.2 * inch))

    # --- Response classification breakdown ---------------------------------
    story.append(Paragraph("Response Classification Breakdown", _H2))
    breakdown_rows = [[k.title(), str(v)] for k, v in sorted(classification_counts.items())]
    t = Table([["Classification", "Count"]] + breakdown_rows, colWidths=[2.5 * inch, 1 * inch])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.2 * inch))

    # --- Control mapping coverage ------------------------------------------
    story.append(Paragraph("Control Coverage", _H2))
    if control_scores:
        rows = [[Paragraph("<b>Framework</b>", _BODY), Paragraph("<b>Control</b>", _BODY),
                 Paragraph("<b>Score</b>", _BODY)]]
        for c in control_scores:
            rows.append([
                Paragraph(c.get("framework_code") or "—", _BODY),
                Paragraph(f"{c.get('control_ref', '')} — {c.get('control_title', '')}", _BODY),
                Paragraph(f"{c['score']:.0f}", _BODY),
            ])
        t = Table(rows, colWidths=[1.1 * inch, 3.7 * inch, 1 * inch])
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No questions in this template were mapped to a control.", _BODY))
    story.append(PageBreak())

    # --- Detailed Q&A ---------------------------------------------------
    story.append(Paragraph("Detailed Responses", _H2))
    current_section = None
    for r in responses:
        if r["section"] != current_section:
            current_section = r["section"]
            story.append(Paragraph(current_section, ParagraphStyle(
                "Section", parent=_H2, fontSize=12, spaceBefore=10,
            )))
        classification = r.get("classification") or "unanalyzed"
        color_hex = _CLASSIFICATION_HEX.get(classification, "#757575")
        story.append(Paragraph(f"<b>Q:</b> {r['prompt']}", _BODY))
        story.append(Paragraph(f"<b>A:</b> {r.get('raw_answer') or '<i>(no answer)</i>'}", _BODY))
        story.append(Paragraph(
            f'<font color="{color_hex}"><b>{classification.title()}</b></font>'
            f" (confidence: {r.get('confidence_score') if r.get('confidence_score') is not None else '—'})",
            _BODY,
        ))
        if r.get("follow_up_question"):
            story.append(Paragraph(f"<i>Follow-up requested: {r['follow_up_question']}</i>", _BODY))
        story.append(Spacer(1, 0.12 * inch))

    # --- Evidence appendix ---------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("Evidence Appendix", _H2))
    if evidence:
        rows = [["File", "Type", "Uploaded"]]
        for e in evidence:
            uploaded = e["uploaded_at"].strftime("%Y-%m-%d") if e.get("uploaded_at") else "—"
            rows.append([e["original_filename"], e["document_type"], uploaded])
        t = Table(rows, colWidths=[3 * inch, 1.7 * inch, 1.3 * inch])
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No evidence files were uploaded.", _BODY))

    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(
        f"Audit trail: report generated {generated}"
        + (f", reviewed by {reviewer_name}" if reviewer_name else " — pending reviewer sign-off")
        + ".", _BODY,
    ))

    doc.build(story)
    return buf.getvalue()
