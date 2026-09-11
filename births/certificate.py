"""
Birth certificate PDF (A4 landscape), drawn directly on a ReportLab canvas so
the guilloche border, watermark rosette and seal render identically on any
host — no WeasyPrint/native libraries required.
"""
import io
import math
import os

from django.utils import timezone
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from core.pdf_utils import SAGE_BLUE, SAGE_INK, SAGE_RED, SAGE_TEAL

HOSPITAL_NAME = "SAGE Medical Centre"

GOLD = colors.HexColor("#B8923A")
GOLD_LIGHT = colors.HexColor("#E6D3A0")
PAPER = colors.HexColor("#FBF8F1")
MUTED = colors.HexColor("#6E7A82")

SERIF = "Times-Roman"
SERIF_BOLD = "Times-Bold"
SERIF_ITALIC = "Times-Italic"
SERIF_BOLD_ITALIC = "Times-BoldItalic"
SANS = "Helvetica"
SANS_BOLD = "Helvetica-Bold"

PAGE_W, PAGE_H = landscape(A4)
CX = PAGE_W / 2

# Shorter labels than ANCRecord.DELIVERY_MODE_CHOICES so they fit a certificate cell.
DELIVERY_MODE_LABELS = {
    "svd": "Vaginal (SVD)",
    "assisted": "Assisted vaginal",
    "cs": "Caesarean section",
    "other": "Other",
}


# ── Text helpers ─────────────────────────────────────────────────

def _draw_fitted(c, x, y, text, font, size, max_width, align="centre", min_size=7):
    """Draw text shrunk (then ellipsised) to fit max_width. Returns the drawn width."""
    width = stringWidth(text, font, size)
    if width > max_width:
        size = max(min_size, size * max_width / width)
    # Tolerance absorbs float rounding from the proportional shrink above.
    while stringWidth(text, font, size) > max_width + 0.5 and len(text) > 1:
        text = text[:-2] + "…"
    c.setFont(font, size)
    draw = {"centre": c.drawCentredString, "left": c.drawString, "right": c.drawRightString}[align]
    draw(x, y, text)
    return stringWidth(text, font, size)


def _ordinal(n):
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _time_display(t):
    return t.strftime("%I:%M %p").lstrip("0")


def _draw_circular_text(c, text, cx, cy, radius, font, size, color):
    """Spread text evenly around a full circle, reading clockwise from the top."""
    circumference = 2 * math.pi * radius
    natural = stringWidth(text, font, 1)
    size = min(size, 0.92 * circumference / natural)
    widths = [stringWidth(ch, font, size) for ch in text]
    gap = (circumference - sum(widths)) / len(text)

    c.setFillColor(color)
    c.setFont(font, size)
    angle = math.pi / 2
    for ch, w in zip(text, widths):
        half_step = (w + gap) / 2 / radius
        angle -= half_step
        c.saveState()
        c.translate(cx + radius * math.cos(angle), cy + radius * math.sin(angle))
        c.rotate(math.degrees(angle) - 90)
        c.drawCentredString(0, 0, ch)
        c.restoreState()
        angle -= half_step


# ── Ornament ─────────────────────────────────────────────────────

def _inset_rect(c, inset):
    c.rect(inset, inset, PAGE_W - 2 * inset, PAGE_H - 2 * inset, stroke=1, fill=0)


def _wave(c, start, end, amplitude, wavelength, phase, offset=0.0, step=0.5 * mm):
    """Stroke a sine wave running from start to end along the segment."""
    (x0, y0), (x1, y1) = start, end
    length = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    nx, ny = -uy, ux
    n = max(2, int(length / step))
    path = c.beginPath()
    for i in range(n + 1):
        t = length * i / n
        off = amplitude * math.sin(2 * math.pi * (t + offset) / wavelength + phase)
        x, y = x0 + ux * t + nx * off, y0 + uy * t + ny * off
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    c.drawPath(path, stroke=1, fill=0)


def _draw_guilloche_band(c, inset, amplitude):
    """Interlaced teal/gold waves running round the page, like banknote borders."""
    corners = [
        (inset, inset), (PAGE_W - inset, inset),
        (PAGE_W - inset, PAGE_H - inset), (inset, PAGE_H - inset),
    ]
    sides = list(zip(corners, corners[1:] + corners[:1]))
    strands = [
        # (colour, wavelength, amplitude factor, phase count)
        (SAGE_TEAL, 6 * mm, 1.0, 4),
        (GOLD, 12 * mm, 0.8, 2),
    ]
    c.setLineWidth(0.35)
    for colour, wavelength, amp_factor, count in strands:
        c.setStrokeColor(colour)
        for k in range(count):
            phase = k * 2 * math.pi / count
            travelled = 0.0  # keeps the wave continuous around each corner
            for start, end in sides:
                _wave(c, start, end, amplitude * amp_factor, wavelength, phase, travelled)
                travelled += math.hypot(end[0] - start[0], end[1] - start[1])


def _draw_corner_rosette(c, cx, cy):
    c.setFillColor(PAPER)
    c.setStrokeColor(SAGE_INK)
    c.setLineWidth(0.8)
    c.circle(cx, cy, 5.4 * mm, stroke=1, fill=1)
    c.setStrokeColor(GOLD)
    c.setLineWidth(0.4)
    for i in range(8):
        c.saveState()
        c.translate(cx, cy)
        c.rotate(i * 22.5)
        c.ellipse(-4.2 * mm, -1.2 * mm, 4.2 * mm, 1.2 * mm, stroke=1, fill=0)
        c.restoreState()
    c.setFillColor(SAGE_INK)
    c.circle(cx, cy, 1.1 * mm, stroke=0, fill=1)


def _draw_border(c):
    c.setFillColor(PAPER)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)

    c.setStrokeColor(SAGE_INK)
    c.setLineWidth(2.4)
    _inset_rect(c, 6 * mm)
    c.setLineWidth(0.6)
    _inset_rect(c, 8.4 * mm)

    _draw_guilloche_band(c, inset=12.6 * mm, amplitude=2.7 * mm)

    c.setStrokeColor(SAGE_INK)
    c.setLineWidth(0.6)
    _inset_rect(c, 16.8 * mm)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.1)
    _inset_rect(c, 18.6 * mm)
    c.setLineWidth(0.3)
    _inset_rect(c, 19.8 * mm)

    inset = 12.6 * mm
    for cx, cy in [(inset, inset), (PAGE_W - inset, inset),
                   (inset, PAGE_H - inset), (PAGE_W - inset, PAGE_H - inset)]:
        _draw_corner_rosette(c, cx, cy)


def _draw_watermark(c, cx, cy, radius):
    """Faint guilloche rosette behind the body text."""
    c.saveState()
    c.setStrokeColor(SAGE_TEAL)
    c.setStrokeAlpha(0.10)
    c.setLineWidth(0.45)
    rings = [
        # (base radius, amplitude, lobes, strands)
        (0.74 * radius, 0.22 * radius, 24, 6),
        (0.36 * radius, 0.12 * radius, 12, 4),
    ]
    steps = 720
    for base, amp, lobes, strands in rings:
        for k in range(strands):
            phase = k * 2 * math.pi / strands
            path = c.beginPath()
            for i in range(steps + 1):
                theta = 2 * math.pi * i / steps
                rho = base + amp * math.sin(lobes * theta + phase)
                x, y = cx + rho * math.cos(theta), cy + rho * math.sin(theta)
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            c.drawPath(path, stroke=1, fill=0)
    c.circle(cx, cy, radius * 1.0, stroke=1, fill=0)
    c.circle(cx, cy, radius * 1.03, stroke=1, fill=0)
    c.restoreState()


def _draw_divider(c, y, half_width):
    c.setStrokeColor(GOLD)
    c.setFillColor(GOLD)
    c.setLineWidth(0.8)
    c.line(CX - half_width, y, CX - 5 * mm, y)
    c.line(CX + 5 * mm, y, CX + half_width, y)
    d = 2.4 * mm
    path = c.beginPath()
    path.moveTo(CX - d, y)
    path.lineTo(CX, y + d)
    path.lineTo(CX + d, y)
    path.lineTo(CX, y - d)
    path.close()
    c.drawPath(path, stroke=0, fill=1)
    for x in (CX - half_width, CX + half_width):
        c.circle(x, y, 0.8 * mm, stroke=0, fill=1)


def _draw_seal(c, cx, cy, r, year):
    points = 36
    path = c.beginPath()
    for i in range(points * 2):
        ang = math.pi * i / points
        rr = r if i % 2 == 0 else r * 0.9
        x, y = cx + rr * math.cos(ang), cy + rr * math.sin(ang)
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    path.close()
    c.setFillColor(GOLD)
    c.drawPath(path, stroke=0, fill=1)

    c.setFillColor(SAGE_INK)
    c.circle(cx, cy, r * 0.8, stroke=0, fill=1)
    c.setStrokeColor(GOLD_LIGHT)
    c.setLineWidth(0.5)
    c.circle(cx, cy, r * 0.75, stroke=1, fill=0)
    c.circle(cx, cy, r * 0.47, stroke=1, fill=0)

    _draw_circular_text(
        c, "SAGE MEDICAL CENTRE • CERTIFIED BIRTH RECORD • ",
        cx, cy, r * 0.56, SANS_BOLD, 5.2, GOLD_LIGHT,
    )

    c.setFillColor(colors.white)
    c.setFont(SERIF_BOLD, 10)
    c.drawCentredString(cx, cy - 0.4 * mm, "SAGE")
    c.setFillColor(GOLD_LIGHT)
    c.setFont(SANS_BOLD, 5)
    c.drawCentredString(cx, cy - 3.6 * mm, str(year), charSpace=0.8)


def _draw_qr(c, x, y, size, payload):
    widget = QrCodeWidget(payload, barLevel="M", barBorder=2)
    widget.barFillColor = SAGE_INK
    x0, y0, x1, y1 = widget.getBounds()
    drawing = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
    drawing.add(widget)
    c.setFillColor(colors.white)
    c.rect(x, y, size, size, stroke=0, fill=1)
    renderPDF.draw(drawing, c, x, y)


# ── Content ──────────────────────────────────────────────────────

def _site_settings():
    try:
        from core.models import SiteSettings
        return SiteSettings.get()
    except Exception:
        return None  # table may not exist yet — print without contact details/logo


def _logo_path(site):
    logo = getattr(site, "doc_logo", None)
    if not logo:
        return None
    try:
        path = logo.path
    except (ValueError, NotImplementedError):
        return None
    return path if os.path.exists(path) else None


def _draw_header(c, record, site):
    top = PAGE_H - 19.8 * mm

    # Serial number, banknote-style
    c.setFillColor(MUTED)
    c.setFont(SANS_BOLD, 5.5)
    c.drawRightString(PAGE_W - 27 * mm, top - 7 * mm, "CERTIFICATE NO.", charSpace=1.2)
    c.setFillColor(SAGE_RED)
    c.setFont("Courier-Bold", 10.5)
    c.drawRightString(PAGE_W - 27 * mm, top - 11.5 * mm, record.certificate_number)

    logo_path = _logo_path(site)
    if logo_path:
        try:
            c.drawImage(
                logo_path, 27 * mm, top - 22 * mm, width=34 * mm, height=17 * mm,
                preserveAspectRatio=True, anchor="w", mask="auto",
            )
        except Exception:
            pass  # a bad logo upload must never block printing a certificate

    c.setFillColor(SAGE_INK)
    c.setFont(SERIF_BOLD, 25)
    c.drawCentredString(CX, 174 * mm, HOSPITAL_NAME.upper(), charSpace=2.5)

    if site:
        address = " ".join(line.strip() for line in (site.address or "").splitlines() if line.strip())
        contact = "  ·  ".join(p for p in [address, site.phone, site.email] if p)
        if contact:
            c.setFillColor(MUTED)
            _draw_fitted(c, CX, 168.5 * mm, contact, SANS, 7.5, 150 * mm)

    _draw_divider(c, 163 * mm, 62 * mm)

    c.setFillColor(SAGE_BLUE)
    c.setFont(SERIF_BOLD_ITALIC, 40)
    c.drawCentredString(CX, 147 * mm, "Certificate of Birth")

    c.setFillColor(SAGE_TEAL)
    c.setFont(SANS_BOLD, 7.5)
    c.drawCentredString(CX, 140 * mm, "HOSPITAL RECORD OF A LIVE BIRTH", charSpace=3)


def _draw_statement(c, record):
    c.setFillColor(MUTED)
    c.setFont(SERIF_ITALIC, 14)
    c.drawCentredString(CX, 129 * mm, "This is to certify that")

    c.setFillColor(SAGE_INK)
    name_width = _draw_fitted(c, CX, 115.5 * mm, record.child_full_name, SERIF_BOLD, 32, 210 * mm, min_size=16)
    rule = min(220 * mm, max(120 * mm, name_width + 26 * mm))
    c.setStrokeColor(GOLD)
    c.setLineWidth(0.9)
    c.line(CX - rule / 2, 111.5 * mm, CX + rule / 2, 111.5 * mm)

    dob = record.date_of_birth
    sentence = (
        f"was born at {HOSPITAL_NAME} on {dob:%A}, the {_ordinal(dob.day)} day of "
        f"{dob:%B %Y}, at {_time_display(record.time_of_birth)}"
    )
    c.setFillColor(SAGE_INK)
    _draw_fitted(c, CX, 102.5 * mm, sentence, SERIF_ITALIC, 14, 235 * mm)


def _draw_cell(c, x_centre, top, width, label, value, sub=""):
    c.setFillColor(SAGE_TEAL)
    c.setFont(SANS_BOLD, 6)
    c.drawCentredString(x_centre, top - 4.6 * mm, label.upper(), charSpace=1.1)
    c.setFillColor(SAGE_INK)
    _draw_fitted(c, x_centre, top - 10.4 * mm, value or "—", SERIF_BOLD, 13, width - 4 * mm)
    if sub:
        c.setFillColor(MUTED)
        _draw_fitted(c, x_centre, top - 14.4 * mm, sub, SANS, 7, width - 4 * mm)


def _draw_details(c, record):
    left, right = 32 * mm, PAGE_W - 32 * mm
    span = right - left
    row1_top, row2_top, bottom = 96 * mm, 81 * mm, 63 * mm

    row1 = [
        ("Sex", record.get_sex_display()),
        ("Birth weight", f"{record.weight_kg:.2f} kg"),
        ("Length", f"{record.length_cm:.1f} cm" if record.length_cm else ""),
        ("Gestation at birth", f"{record.gestational_age_weeks} weeks" if record.gestational_age_weeks else ""),
        ("Mode of delivery", DELIVERY_MODE_LABELS.get(record.delivery_mode, "")),
        ("Birth type", record.birth_type_display),
    ]
    attendant = record.attended_by
    row2 = [
        ("Mother", record.mother.full_name, f"Hospital No. {record.mother.hospital_number}"),
        ("Father", record.father_name, ""),
        ("Attended by", attendant.display_name if attendant else "",
         attendant.get_role_display() if attendant else ""),
    ]

    c.setStrokeColor(GOLD)
    c.setLineWidth(0.6)
    c.line(left, row1_top, right, row1_top)
    c.line(left, bottom, right, bottom)
    c.setLineWidth(0.3)
    c.line(left, row2_top, right, row2_top)

    for top, height, cells in [(row1_top, row1_top - row2_top, row1), (row2_top, row2_top - bottom, row2)]:
        cell_w = span / len(cells)
        for i, cell in enumerate(cells):
            x = left + i * cell_w
            if i:
                c.line(x, top - 2.5 * mm, x, top - height + 2.5 * mm)
            _draw_cell(c, x + cell_w / 2, top, cell_w, *cell)


def _draw_signature(c, x_centre, title, name):
    y = 40 * mm
    c.setStrokeColor(SAGE_INK)
    c.setLineWidth(0.6)
    c.line(x_centre - 25 * mm, y, x_centre + 25 * mm, y)
    c.setFillColor(SAGE_INK)
    c.setFont(SERIF_BOLD, 10.5)
    c.drawCentredString(x_centre, y - 4.6 * mm, title)
    c.setFillColor(MUTED)
    _draw_fitted(c, x_centre, y - 8.4 * mm, name, SANS, 7, 50 * mm)


def _draw_footer(c, record):
    issued = timezone.localtime(record.created_at).date() if record.created_at else timezone.localdate()

    # Date of issue (left)
    c.setFillColor(MUTED)
    c.setFont(SANS_BOLD, 5.5)
    c.drawString(27 * mm, 40.5 * mm, "DATE OF ISSUE", charSpace=1.2)
    c.setFillColor(SAGE_INK)
    c.setFont(SERIF_BOLD, 10.5)
    c.drawString(27 * mm, 35.8 * mm, f"{issued.day} {issued:%B %Y}")

    attendant = record.attended_by
    _draw_signature(c, 92 * mm, "Attending Clinician / Midwife",
                    attendant.display_name if attendant else "Name & signature")
    _draw_signature(c, PAGE_W - 92 * mm, "Medical Director", "Signature & official stamp")
    _draw_seal(c, CX, 41 * mm, 15.5 * mm, issued.year)

    # QR code (right) — carries the key facts for quick verification
    qr_size = 20 * mm
    qr_x, qr_y = PAGE_W - 27 * mm - qr_size, 27 * mm
    payload = "\n".join([
        f"{HOSPITAL_NAME} - Certificate of Birth",
        f"No: {record.certificate_number}",
        f"Child: {record.child_full_name}",
        f"Sex: {record.get_sex_display()}",
        f"Born: {record.date_of_birth:%Y-%m-%d} {record.time_of_birth:%H:%M}",
        f"Mother: {record.mother.full_name} ({record.mother.hospital_number})",
    ])
    _draw_qr(c, qr_x, qr_y, qr_size, payload)
    c.setFillColor(MUTED)
    c.setFont(SANS_BOLD, 4.8)
    c.drawCentredString(qr_x + qr_size / 2, qr_y - 2.6 * mm, "SCAN FOR DETAILS", charSpace=0.8)

    c.setFillColor(MUTED)
    c.setFont(SANS, 6.2)
    c.drawCentredString(
        CX, 22.6 * mm,
        f"This certificate is issued by {HOSPITAL_NAME} from its delivery records and may be "
        "presented to the National Population Commission (NPC) for civil registration of birth.",
    )


def build_birth_certificate_pdf(record):
    """
    Render the birth certificate for a BirthRecord. Returns a BytesIO buffer.
    """
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=(PAGE_W, PAGE_H), pageCompression=1)
    c.setTitle(f"Certificate of Birth — {record.child_full_name}")
    c.setAuthor(HOSPITAL_NAME)
    c.setSubject(f"Birth certificate {record.certificate_number}")

    site = _site_settings()
    _draw_border(c)
    _draw_watermark(c, CX, 104 * mm, 58 * mm)
    _draw_header(c, record, site)
    _draw_statement(c, record)
    _draw_details(c, record)
    _draw_footer(c, record)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf
