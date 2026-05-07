"""
utils/pdf_export.py — PDF Report Generator
--------------------------------------------
Generates a formal, print-ready evaluation report as a PDF.

The PDF contains:
  Page 1: Cover page (tender reference, officer name, date, CRPF branding)
  Page 2: Executive summary (metrics table + overall eligibility results)
  Page 3+: Criterion-level detail for every bidder
  Final page: Audit trail summary + officer declaration

This module is independent of Streamlit — call generate_pdf() from anywhere.
The export.py page calls it and pipes the bytes to st.download_button().

Library: ReportLab (open-source, pure Python, no external dependencies)
Install: pip install reportlab
"""

import io
import time
from typing import Optional

from reportlab.lib.pagesizes    import A4
from reportlab.lib              import colors
from reportlab.lib.units        import cm, mm
from reportlab.lib.styles       import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums        import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus         import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable, PageBreak, KeepTogether
)
from reportlab.platypus.flowables import HRFlowable


# ── Colour palette ─────────────────────────────────────────────────────────────
NAVY     = colors.HexColor("#1F4E79")
BLUE     = colors.HexColor("#2E75B6")
LIGHT    = colors.HexColor("#DEEAF1")
GREEN    = colors.HexColor("#375623")
GREEN_BG = colors.HexColor("#E2EFDA")
RED      = colors.HexColor("#C00000")
RED_BG   = colors.HexColor("#FCE4D6")
AMBER    = colors.HexColor("#7F6000")
AMBER_BG = colors.HexColor("#FFF2CC")
GREY_BG  = colors.HexColor("#F5F5F5")
WHITE    = colors.white
BLACK    = colors.black


# ── Build styles ───────────────────────────────────────────────────────────────
def _build_styles():
    base = getSampleStyleSheet()
    styles = {
        "cover_title": ParagraphStyle(
            "CoverTitle", parent=base["Title"],
            fontSize=26, textColor=WHITE,
            spaceAfter=8, alignment=TA_CENTER,
        ),
        "cover_sub": ParagraphStyle(
            "CoverSub", parent=base["Normal"],
            fontSize=13, textColor=colors.HexColor("#C5E8F5"),
            alignment=TA_CENTER, spaceAfter=6,
        ),
        "cover_meta": ParagraphStyle(
            "CoverMeta", parent=base["Normal"],
            fontSize=11, textColor=WHITE,
            alignment=TA_CENTER, spaceAfter=4,
        ),
        "section_heading": ParagraphStyle(
            "SectionHeading", parent=base["Heading2"],
            fontSize=13, textColor=NAVY,
            spaceBefore=14, spaceAfter=6,
        ),
        "bidder_heading": ParagraphStyle(
            "BidderHeading", parent=base["Heading3"],
            fontSize=11, textColor=BLUE,
            spaceBefore=10, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["Normal"],
            fontSize=9, textColor=BLACK,
            spaceAfter=4, leading=14,
        ),
        "body_small": ParagraphStyle(
            "BodySmall", parent=base["Normal"],
            fontSize=8, textColor=colors.HexColor("#404040"),
            spaceAfter=3, leading=12,
        ),
        "caption": ParagraphStyle(
            "Caption", parent=base["Normal"],
            fontSize=8, textColor=colors.HexColor("#888888"),
            italics=True, spaceAfter=2,
        ),
        "footer": ParagraphStyle(
            "Footer", parent=base["Normal"],
            fontSize=7.5, textColor=colors.HexColor("#888888"),
            alignment=TA_CENTER,
        ),
    }
    return styles


# ── Main generate function ─────────────────────────────────────────────────────

def generate_pdf(
    all_verdicts: list,
    criteria:     list,
    meta:         dict,
    audit_entries: Optional[list] = None,
) -> bytes:
    """
    Generate a complete PDF evaluation report.

    Args:
        all_verdicts:  List of bidder verdict dicts from verdict.py
        criteria:      List of criterion dicts from criteria_llm.py
        meta: {
            "tender_ref":   "CRPF/HQ/2024/087",
            "tender_name":  "tender.pdf",
            "eval_date":    "01 January 2025",
            "department":   "CRPF Procurement Directorate",
            "prepared_by":  "Priya Sharma",
        }
        audit_entries: Optional list of audit log dicts to include

    Returns:
        PDF as bytes (pass directly to st.download_button)
    """
    buffer = io.BytesIO()
    S = _build_styles()

    doc = SimpleDocTemplate(
        buffer,
        pagesize      = A4,
        rightMargin   = 2.0 * cm,
        leftMargin    = 2.0 * cm,
        topMargin     = 2.0 * cm,
        bottomMargin  = 2.0 * cm,
        title         = f"Tendra AI — {meta.get('tender_ref', 'Evaluation Report')}",
        author        = meta.get("prepared_by", ""),
    )

    story = []

    # ── Cover page ─────────────────────────────────────────────────────────────
    story.extend(_build_cover(S, meta))
    story.append(PageBreak())

    # ── Executive summary ──────────────────────────────────────────────────────
    story.extend(_build_summary(S, all_verdicts, meta))
    story.append(PageBreak())

    # ── Per-bidder criterion detail ────────────────────────────────────────────
    story.append(Paragraph("Criterion-Level Evaluation Detail", S["section_heading"]))
    story.append(_rule())
    story.append(Spacer(1, 0.3 * cm))

    for verdict in all_verdicts:
        story.extend(_build_bidder_section(S, verdict))
        story.append(Spacer(1, 0.5 * cm))

    # ── Audit trail ────────────────────────────────────────────────────────────
    if audit_entries:
        story.append(PageBreak())
        story.extend(_build_audit_section(S, audit_entries))

    # ── Officer declaration ────────────────────────────────────────────────────
    story.append(PageBreak())
    story.extend(_build_declaration(S, meta, all_verdicts))

    doc.build(story)
    return buffer.getvalue()


# ── Section builders ───────────────────────────────────────────────────────────

def _build_cover(S, meta) -> list:
    """Build the cover page as a blue banner with metadata."""
    elements = []

    # Navy banner
    banner_data = [[
        Paragraph("Tendra AI", S["cover_title"]),
    ]]
    banner_sub = [[
        Paragraph("Tender Eligibility Evaluation Report", S["cover_sub"]),
    ]]
    meta_rows = [
        [Paragraph(f"Tender Reference: {meta.get('tender_ref', '—')}", S["cover_meta"])],
        [Paragraph(f"Organisation: {meta.get('department', '—')}", S["cover_meta"])],
        [Paragraph(f"Evaluation Date: {meta.get('eval_date', '—')}", S["cover_meta"])],
        [Paragraph(f"Prepared by: {meta.get('prepared_by', '—')}", S["cover_meta"])],
        [Paragraph(f"Generated: {time.strftime('%d %B %Y at %H:%M')}", S["cover_meta"])],
    ]

    cover_content = banner_data + banner_sub + [[""], [""], [""], [""]] + meta_rows

    cover_table = Table(cover_content, colWidths=[17 * cm])
    cover_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), NAVY),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("LEFTPADDING",  (0, 0), (-1, -1), 20),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20),
    ]))

    elements.append(Spacer(1, 3 * cm))
    elements.append(cover_table)
    elements.append(Spacer(1, 2 * cm))

    # Disclaimer box
    disc_table = Table([[
        Paragraph(
            "CONFIDENTIAL — For official use only. This document contains the "
            "results of an AI-assisted eligibility evaluation conducted under "
            "General Financial Rules 2017. All AI verdicts marked 'REVIEW' have "
            "been confirmed by the signing officer. Officer overrides are logged "
            "with names and timestamps in the audit trail.",
            S["body_small"]
        )
    ]], colWidths=[17 * cm])
    disc_table.setStyle(TableStyle([
        ("BOX",          (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("BACKGROUND",   (0, 0), (-1, -1), GREY_BG),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("LEFTPADDING",  (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    elements.append(disc_table)

    return elements


def _build_summary(S, all_verdicts, meta) -> list:
    """Build the executive summary page."""
    elements = []

    elements.append(Paragraph("Executive Summary", S["section_heading"]))
    elements.append(_rule())
    elements.append(Spacer(1, 0.3 * cm))

    # Metrics
    total      = len(all_verdicts)
    eligible   = sum(1 for v in all_verdicts if v["overall_verdict"] == "eligible")
    ineligible = sum(1 for v in all_verdicts if v["overall_verdict"] == "ineligible")
    review     = sum(1 for v in all_verdicts if v["overall_verdict"] == "review")
    avg_conf   = (
        sum(v["overall_confidence"] for v in all_verdicts) / total
        if total else 0
    )

    metric_data = [
        ["Total Bidders", "Eligible", "Ineligible", "Needs Review", "Avg Confidence"],
        [str(total), str(eligible), str(ineligible), str(review), f"{avg_conf:.0%}"],
    ]
    metric_table = Table(metric_data, colWidths=[3.4 * cm] * 5)
    metric_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR",    (0, 0), (-1, 0), WHITE),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND",   (0, 1), (-1, 1), LIGHT),
        ("FONTNAME",     (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 9),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("BOX",          (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("INNERGRID",    (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))
    elements.append(metric_table)
    elements.append(Spacer(1, 0.5 * cm))

    # Bidder summary table
    elements.append(Paragraph("Bidder Eligibility Summary", S["section_heading"]))
    elements.append(_rule())

    header = [["#", "Bidder Name", "Overall Verdict", "Passed",
               "Failed", "Review", "Confidence"]]
    rows   = []
    for i, v in enumerate(all_verdicts, start=1):
        rows.append([
            str(i),
            v["bidder_name"],
            v["overall_verdict"].upper(),
            str(v["passed"]),
            str(v["failed"]),
            str(v["review_needed"]),
            f"{v['overall_confidence']:.0%}",
        ])

    summary_table = Table(
        header + rows,
        colWidths=[0.7*cm, 5.5*cm, 3*cm, 1.5*cm, 1.5*cm, 1.5*cm, 2.3*cm]
    )

    row_styles = [
        ("BACKGROUND",  (0, 0), (-1, 0),  BLUE),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  WHITE),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8.5),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("ALIGN",       (1, 0), (1, -1),  "LEFT"),
        ("GRID",        (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, GREY_BG]),
    ]
    for i, v in enumerate(all_verdicts, start=1):
        ov = v["overall_verdict"]
        col = GREEN if ov == "eligible" else RED if ov == "ineligible" else AMBER
        bg  = GREEN_BG if ov == "eligible" else RED_BG if ov == "ineligible" else AMBER_BG
        row_styles.append(("TEXTCOLOR",  (2, i), (2, i), col))
        row_styles.append(("BACKGROUND", (2, i), (2, i), bg))

    summary_table.setStyle(TableStyle(row_styles))
    elements.append(summary_table)

    return elements


def _build_bidder_section(S, verdict: dict) -> list:
    """Build the criterion-level detail section for one bidder."""
    elements = []

    bname  = verdict["bidder_name"]
    ov     = verdict["overall_verdict"]
    ov_col = GREEN if ov == "eligible" else RED if ov == "ineligible" else AMBER

    with_colour = ParagraphStyle(
        "BidderColour", parent=S["bidder_heading"],
        textColor=ov_col,
    )

    heading = KeepTogether([
        Paragraph(
            f"{bname}   —   {ov.upper()}  "
            f"({verdict['overall_confidence']:.0%} confidence)",
            with_colour
        ),
        Paragraph(verdict.get("summary", ""), S["body_small"]),
        Spacer(1, 0.2 * cm),
    ])
    elements.append(heading)

    # Criterion detail table
    header = [["ID", "Criterion", "Cat", "Verdict", "Evidence / Reasoning"]]
    rows   = []

    for r in verdict.get("criteria_results", []):
        v_text = r.get("verdict", "review").upper()
        overridden = "officer_override" in r
        if overridden:
            v_text += " ✏"

        evidence_text = (
            f"{r.get('evidence', '')[:80]}... "
            f"| {r.get('reasoning', '')[:80]}"
        )

        rows.append([
            r.get("criterion_id", ""),
            Paragraph(r.get("criterion_text", "")[:100], S["body_small"]),
            r.get("category", "")[:4],
            v_text,
            Paragraph(evidence_text, S["body_small"]),
        ])

    crit_table = Table(
        header + rows,
        colWidths=[1*cm, 5*cm, 1.2*cm, 1.5*cm, 7.3*cm]
    )

    crit_styles = [
        ("BACKGROUND",   (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR",    (0, 0), (-1, 0), WHITE),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 7.5),
        ("ALIGN",        (0, 0), (-1, -1), "LEFT"),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("GRID",         (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("TOPPADDING",   (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, GREY_BG]),
    ]
    for i, r in enumerate(verdict.get("criteria_results", []), start=1):
        vt = r.get("verdict", "review")
        col = GREEN if vt == "pass" else RED if vt == "fail" else AMBER
        crit_styles.append(("TEXTCOLOR", (3, i), (3, i), col))

    crit_table.setStyle(TableStyle(crit_styles))
    elements.append(crit_table)

    return elements


def _build_audit_section(S, audit_entries: list) -> list:
    """Build the audit trail page."""
    elements = []
    elements.append(Paragraph("Audit Trail", S["section_heading"]))
    elements.append(_rule())

    header = [["Timestamp", "User", "Event", "Detail"]]
    rows   = [
        [
            str(e.get("timestamp", ""))[:19],
            e.get("user", ""),
            e.get("event", ""),
            str(e.get("detail", ""))[:80],
        ]
        for e in audit_entries[:50]  # max 50 entries in PDF
    ]

    audit_table = Table(
        header + rows,
        colWidths=[3.5*cm, 3.5*cm, 3*cm, 7*cm]
    )
    audit_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR",    (0, 0), (-1, 0), WHITE),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 7),
        ("GRID",         (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("TOPPADDING",   (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, GREY_BG]),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(audit_table)
    return elements


def _build_declaration(S, meta, all_verdicts) -> list:
    """Build the officer sign-off declaration page."""
    elements = []
    elements.append(Paragraph("Officer Declaration", S["section_heading"]))
    elements.append(_rule())
    elements.append(Spacer(1, 0.5 * cm))

    eligible   = sum(1 for v in all_verdicts if v["overall_verdict"] == "eligible")
    ineligible = sum(1 for v in all_verdicts if v["overall_verdict"] == "ineligible")
    review     = sum(1 for v in all_verdicts if v["overall_verdict"] == "review")

    declaration_text = (
        f"I, {meta.get('prepared_by', '________________')}, "
        f"Procurement Officer at {meta.get('department', '________________')}, "
        f"hereby certify that the eligibility evaluation for tender reference "
        f"{meta.get('tender_ref', '________________')} has been conducted in "
        f"accordance with the eligibility criteria specified in the tender "
        f"document, and the results are as follows:\n\n"
        f"Total bidders evaluated: {len(all_verdicts)}\n"
        f"Eligible: {eligible}   |   Ineligible: {ineligible}   |   "
        f"Flagged for review: {review}\n\n"
        f"All AI-assisted verdicts have been reviewed and any necessary "
        f"overrides have been recorded with reasons in the audit trail. "
        f"This evaluation report is submitted for approval and record."
    )

    elements.append(Paragraph(declaration_text, S["body"]))
    elements.append(Spacer(1, 2 * cm))

    # Signature block
    sig_data = [
        ["Signature:", "________________________"],
        ["Name:",      meta.get("prepared_by", "")],
        ["Date:",      meta.get("eval_date", "")],
        ["Place:",     ""],
    ]
    sig_table = Table(sig_data, colWidths=[3 * cm, 8 * cm])
    sig_table.setStyle(TableStyle([
        ("FONTNAME",  (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE",  (0, 0), (-1, -1), 9),
        ("TOPPADDING",(0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(sig_table)

    elements.append(Spacer(1, 1 * cm))
    elements.append(
        Paragraph(
            "Generated by Tendra AI — open-source AI-assisted procurement "
            "evaluation system. This report and its audit trail are maintained "
            "for CVC compliance and RTI purposes.",
            S["footer"]
        )
    )
    return elements


def _rule():
    return HRFlowable(
        width="100%", thickness=1,
        color=BLUE, spaceAfter=6
    )


# ── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Generate a test PDF with dummy data
    sample_verdicts = [{
        "bidder_name":        "Test Bidder Pvt Ltd",
        "overall_verdict":    "eligible",
        "overall_confidence": 0.91,
        "passed":             12, "failed": 0, "review_needed": 0,
        "total_criteria":     12,
        "summary":            "All criteria met.",
        "criteria_results": [{
            "criterion_id":   "C001",
            "criterion_text": "Annual turnover ≥ ₹2 Crore for 3 years",
            "category":       "Financial",
            "mandatory":      True,
            "verdict":        "pass",
            "confidence":     0.92,
            "evidence":       "FY2023-24: ₹3.4 Cr found in Balance Sheet",
            "reasoning":      "Exceeds threshold in all 3 years",
            "layer_used":     "numeric",
        }],
    }]

    pdf_bytes = generate_pdf(
        all_verdicts=sample_verdicts,
        criteria=[],
        meta={
            "tender_ref":  "CRPF/TEST/2024/001",
            "tender_name": "test_tender.pdf",
            "eval_date":   "01 January 2025",
            "department":  "CRPF Procurement Directorate",
            "prepared_by": "Test Officer",
        }
    )

    with open("test_report.pdf", "wb") as f:
        f.write(pdf_bytes)
    print(f"Test PDF generated: test_report.pdf ({len(pdf_bytes):,} bytes)")