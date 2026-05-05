"""
PDF generation helpers using ReportLab.
All functions return a BytesIO buffer containing a PDF.
"""
import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Brand colours ─────────────────────────────────────────────
SAGE_INK   = colors.HexColor("#0B1E2D")
SAGE_BLUE  = colors.HexColor("#0F4C81")
SAGE_TEAL  = colors.HexColor("#1B998B")
SAGE_GREEN = colors.HexColor("#2E7D55")
SAGE_RED   = colors.HexColor("#B83A26")
SAGE_AMBER = colors.HexColor("#C9831D")
LIGHT_GREY = colors.HexColor("#F4F5F2")
LINE       = colors.HexColor("#DCDFD7")

styles = getSampleStyleSheet()

H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=16, textColor=SAGE_INK, spaceAfter=2)
H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11, textColor=SAGE_INK, spaceAfter=2)
BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=9, textColor=SAGE_INK, leading=13)
SMALL = ParagraphStyle("small", fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#6E7A82"), leading=11)
MONO = ParagraphStyle("mono", fontName="Courier", fontSize=9, textColor=SAGE_INK)
LABEL = ParagraphStyle("label", fontName="Helvetica-Bold", fontSize=7.5, textColor=colors.HexColor("#6E7A82"), leading=10)
RIGHT = ParagraphStyle("right", fontName="Helvetica", fontSize=9, alignment=TA_RIGHT)
RIGHT_BOLD = ParagraphStyle("right_bold", fontName="Helvetica-Bold", fontSize=9, alignment=TA_RIGHT, textColor=SAGE_INK)


def _page_header(canvas, doc, title, subtitle=""):
    """Draw page header on every page."""
    canvas.saveState()
    w, h = A4
    # Teal bar
    canvas.setFillColor(SAGE_INK)
    canvas.rect(0, h - 36*mm, w, 36*mm, fill=1, stroke=0)
    # Brand
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 18)
    canvas.drawString(18*mm, h - 16*mm, "SAGE")
    canvas.setFillColor(SAGE_TEAL)
    canvas.drawString(18*mm + canvas.stringWidth("SAGE", "Helvetica-Bold", 18), h - 16*mm, ".")
    # Title
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(18*mm, h - 25*mm, title)
    if subtitle:
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#A0B8CC"))
        canvas.drawString(18*mm, h - 31*mm, subtitle)
    # Footer
    canvas.setFillColor(colors.HexColor("#6E7A82"))
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(18*mm, 10*mm, "SAGE Medical Center · Confidential Medical Document")
    canvas.drawRightString(w - 18*mm, 10*mm, f"Page {doc.page}")
    canvas.restoreState()


def _kv_table(rows, col_widths=None):
    """Build a 2-column key-value table."""
    data = [[Paragraph(k, LABEL), Paragraph(v, BODY)] for k, v in rows]
    w = col_widths or [4*cm, 12*cm]
    t = Table(data, colWidths=w)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("LINEBEFORE", (1, 0), (1, -1), 0.3, LINE),
        ("LEFTPADDING", (1, 0), (1, -1), 6),
    ]))
    return t


def build_invoice_pdf(invoice):
    """
    Generate a PDF invoice. Returns a BytesIO buffer.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=44*mm, bottomMargin=20*mm,
    )

    def _header(canvas, doc):
        _page_header(canvas, doc, "INVOICE", invoice.invoice_number)

    story = []

    # Patient info block
    patient = invoice.patient
    story.append(Paragraph("Patient", H2))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LINE, spaceAfter=6))
    story.append(_kv_table([
        ("Name", patient.full_name),
        ("Hospital No.", patient.hospital_number),
        ("Date of Birth", str(patient.date_of_birth) if patient.date_of_birth else "—"),
        ("Sex", patient.get_sex_display() if patient.sex else "—"),
    ]))
    story.append(Spacer(1, 10))

    # Invoice meta
    story.append(Paragraph("Invoice Details", H2))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LINE, spaceAfter=6))
    story.append(_kv_table([
        ("Invoice No.", invoice.invoice_number),
        ("Date", invoice.created_at.strftime("%d %B %Y")),
        ("Status", invoice.get_status_display()),
    ]))
    story.append(Spacer(1, 14))

    # Line items
    story.append(Paragraph("Items", H2))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LINE, spaceAfter=6))

    header_row = [
        Paragraph("Description", LABEL),
        Paragraph("Qty", LABEL),
        Paragraph("Unit Price", LABEL),
        Paragraph("Total", LABEL),
    ]
    table_data = [header_row]
    for item in invoice.items.select_related("service").all():
        table_data.append([
            Paragraph(item.description or (item.service.name if item.service else "—"), BODY),
            Paragraph(str(item.quantity), MONO),
            Paragraph(f"₦{item.unit_price:,.2f}", RIGHT),
            Paragraph(f"₦{item.total:,.2f}", RIGHT),
        ])

    col_w = [9*cm, 1.8*cm, 3.5*cm, 3.5*cm]
    t = Table(table_data, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT_GREY),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, LINE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    # Totals
    totals_data = [
        [Paragraph("Subtotal", BODY), Paragraph(f"₦{invoice.total:,.2f}", RIGHT)],
        [Paragraph("Paid", BODY), Paragraph(f"₦{invoice.amount_paid:,.2f}", RIGHT)],
        [Paragraph("Balance Due", H2), Paragraph(f"₦{invoice.balance:,.2f}", RIGHT_BOLD)],
    ]
    t2 = Table(totals_data, colWidths=[14*cm, 3.5*cm])
    t2.setStyle(TableStyle([
        ("LINEABOVE", (0, 2), (-1, 2), 1, SAGE_INK),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t2)

    if invoice.notes:
        story.append(Spacer(1, 10))
        story.append(Paragraph("Notes", LABEL))
        story.append(Paragraph(invoice.notes, SMALL))

    doc.build(story, onFirstPage=_header, onLaterPages=_header)
    buf.seek(0)
    return buf


def build_lab_result_pdf(lab_order):
    """
    Generate a PDF for a lab result. Returns a BytesIO buffer.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=44*mm, bottomMargin=20*mm,
    )
    result = getattr(lab_order, "result", None)

    def _header(canvas, doc):
        _page_header(
            canvas, doc,
            "LABORATORY RESULT",
            f"{lab_order.test.name} · {lab_order.patient.hospital_number}",
        )

    story = []

    # Patient block
    patient = lab_order.patient
    story.append(Paragraph("Patient", H2))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LINE, spaceAfter=6))
    story.append(_kv_table([
        ("Name", patient.full_name),
        ("Hospital No.", patient.hospital_number),
        ("Date of Birth", str(patient.date_of_birth) if patient.date_of_birth else "—"),
        ("Sex", patient.get_sex_display() if patient.sex else "—"),
    ]))
    story.append(Spacer(1, 10))

    # Order block
    story.append(Paragraph("Order Details", H2))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LINE, spaceAfter=6))
    story.append(_kv_table([
        ("Test", lab_order.test.name),
        ("Ordered", lab_order.created_at.strftime("%d %B %Y %H:%M")),
        ("Status", lab_order.get_status_display()),
        ("Priority", lab_order.get_priority_display()),
    ]))
    story.append(Spacer(1, 14))

    if result:
        # Result value — large display
        value_str = f"{result.numeric_value}" if result.numeric_value is not None else result.text_value or "—"
        unit_str = lab_order.test.unit or ""
        story.append(Paragraph("Result", H2))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LINE, spaceAfter=8))

        val_color = SAGE_INK
        if result.flag in ("critical_high", "critical_low"):
            val_color = SAGE_RED
        elif result.flag in ("high", "low"):
            val_color = SAGE_AMBER

        val_style = ParagraphStyle("val", fontName="Helvetica-Bold", fontSize=26,
                                   textColor=val_color, spaceAfter=4)
        story.append(Paragraph(f"{value_str} {unit_str}", val_style))

        ref_range = lab_order.test.reference_range or ""
        if ref_range:
            story.append(Paragraph(f"Reference range: {ref_range}", SMALL))

        if result.flag and result.flag != "normal":
            flag_map = {
                "high": "HIGH", "low": "LOW",
                "critical_high": "CRITICAL HIGH", "critical_low": "CRITICAL LOW",
            }
            story.append(Spacer(1, 6))
            story.append(Paragraph(f"⚠ {flag_map.get(result.flag, result.flag.upper())}", BODY))

        story.append(Spacer(1, 14))
        story.append(_kv_table([
            ("Entered by", result.entered_by.get_full_name() if result.entered_by else "—"),
            ("Released at", result.released_at.strftime("%d %B %Y %H:%M") if result.released_at else "—"),
            ("Verified by", result.verified_by.get_full_name() if result.verified_by else "—"),
        ]))

        if result.notes:
            story.append(Spacer(1, 10))
            story.append(Paragraph("Pathologist Notes", LABEL))
            story.append(Paragraph(result.notes, BODY))
    else:
        story.append(Paragraph("Result not yet available.", BODY))

    doc.build(story, onFirstPage=_header, onLaterPages=_header)
    buf.seek(0)
    return buf
