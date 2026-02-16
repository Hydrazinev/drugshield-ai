# pdf_report.py
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas


PAGE_W, PAGE_H = letter
MARGIN_X = 0.65 * inch
CONTENT_W = PAGE_W - (2 * MARGIN_X)
BOTTOM_Y = 0.8 * inch


def _wrap(text: str, font: str, size: int, width: float) -> List[str]:
    if not text:
        return []
    return simpleSplit(str(text), font, size, width)


def _new_page(c: canvas.Canvas) -> float:
    c.setFillColorRGB(0.96, 0.98, 0.99)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    c.setFillColorRGB(0.08, 0.26, 0.42)
    c.roundRect(MARGIN_X, PAGE_H - 1.0 * inch, CONTENT_W, 0.5 * inch, 10, fill=1, stroke=0)

    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(MARGIN_X + 0.14 * inch, PAGE_H - 0.72 * inch, "DrugShield AI Report")
    c.setFont("Helvetica", 9)
    c.drawRightString(PAGE_W - MARGIN_X - 0.12 * inch, PAGE_H - 0.71 * inch, f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    return PAGE_H - 1.22 * inch


def _section_title(c: canvas.Canvas, y: float, title: str) -> float:
    c.setFillColorRGB(0.10, 0.24, 0.36)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(MARGIN_X, y, title)
    c.setStrokeColorRGB(0.80, 0.85, 0.90)
    c.setLineWidth(0.8)
    c.line(MARGIN_X, y - 0.05 * inch, PAGE_W - MARGIN_X, y - 0.05 * inch)
    return y - 0.2 * inch


def _card_height(title_lines: List[str], body_lines: List[str]) -> float:
    title_h = max(1, len(title_lines)) * 12
    body_h = max(1, len(body_lines)) * 11
    return max(0.78 * inch, 0.18 * inch + title_h + body_h + 0.10 * inch)


def _draw_card(
    c: canvas.Canvas,
    y: float,
    title: str,
    body: str,
    accent_rgb: tuple[float, float, float],
) -> float:
    title_lines = _wrap(title, "Helvetica-Bold", 10, CONTENT_W - 0.34 * inch)
    body_lines = _wrap(body, "Helvetica", 9.5, CONTENT_W - 0.34 * inch)
    h = _card_height(title_lines, body_lines)

    c.setFillColorRGB(1, 1, 1)
    c.setStrokeColorRGB(0.83, 0.88, 0.92)
    c.roundRect(MARGIN_X, y - h, CONTENT_W, h, 9, fill=1, stroke=1)

    c.setFillColorRGB(*accent_rgb)
    c.roundRect(MARGIN_X + 0.06 * inch, y - h + 0.06 * inch, 0.08 * inch, h - 0.12 * inch, 4, fill=1, stroke=0)

    tx = MARGIN_X + 0.20 * inch
    ty = y - 0.12 * inch

    c.setFillColorRGB(0.12, 0.18, 0.24)
    c.setFont("Helvetica-Bold", 10)
    for ln in title_lines:
        c.drawString(tx, ty, ln)
        ty -= 12

    c.setFillColorRGB(0.20, 0.27, 0.34)
    c.setFont("Helvetica", 9.5)
    for ln in body_lines:
        c.drawString(tx, ty, ln)
        ty -= 11

    return y - h - 0.10 * inch


def _urgency_chip_colors(urgency: str) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    u = str(urgency).lower()
    if "red" in u or "high" in u:
        return (0.99, 0.89, 0.89), (0.67, 0.08, 0.08)
    if "yellow" in u or "moderate" in u:
        return (0.99, 0.95, 0.84), (0.66, 0.45, 0.06)
    return (0.89, 0.97, 0.90), (0.09, 0.45, 0.24)


def _ensure_space(c: canvas.Canvas, y: float, needed_height: float) -> float:
    if y - needed_height >= BOTTOM_Y:
        return y
    c.showPage()
    return _new_page(c)


def render_report_bytes(bundle: Dict[str, Any]) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = _new_page(c)

    patient_name = (bundle.get("patient_name") or "").strip()
    score = bundle.get("score", {}).get("final_score", "N/A")
    urgency = str(bundle.get("score", {}).get("urgency", "GREEN_MONITOR"))

    if patient_name:
        y = _section_title(c, y, "Greeting")
        y = _ensure_space(c, y, 1.0 * inch)
        y = _draw_card(c, y, f"Hi {patient_name}!", "Here is your personalized medication safety summary.", (0.93, 0.49, 0.17))

    y = _section_title(c, y, "Risk Summary")
    y = _ensure_space(c, y, 0.55 * inch)
    chip_bg, chip_fg = _urgency_chip_colors(urgency)
    c.setFillColorRGB(*chip_bg)
    c.roundRect(MARGIN_X, y - 0.24 * inch, 2.3 * inch, 0.3 * inch, 7, fill=1, stroke=0)
    c.setFillColorRGB(*chip_fg)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(MARGIN_X + 0.1 * inch, y - 0.12 * inch, f"Urgency: {urgency}")
    c.setFillColorRGB(0.12, 0.18, 0.24)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(MARGIN_X + 2.45 * inch, y - 0.12 * inch, f"Score: {score} / 10")
    y -= 0.40 * inch

    y = _section_title(c, y, "Guidance")
    guidance = [
        ("Patient View", str(bundle.get("patient_summary_simple", "")), (0.12, 0.42, 0.62)),
        ("Caregiver View", str(bundle.get("caregiver_summary", "")), (0.19, 0.52, 0.34)),
        ("Doctor Note", str(bundle.get("doctor_note", "")), (0.43, 0.42, 0.56)),
    ]
    for title, body, accent in guidance:
        t_lines = _wrap(title, "Helvetica-Bold", 10, CONTENT_W - 0.34 * inch)
        b_lines = _wrap(body, "Helvetica", 9.5, CONTENT_W - 0.34 * inch)
        y = _ensure_space(c, y, _card_height(t_lines, b_lines) + 0.1 * inch)
        y = _draw_card(c, y, title, body, accent)

    y = _section_title(c, y, "Key Interactions")
    interactions = bundle.get("interaction_explanations", [])[:6]

    if not interactions:
        body = "No interaction pairs were included in the provided data. Continue monitoring and review the regimen with a clinician."
        t_lines = _wrap("No interaction pairs listed", "Helvetica-Bold", 10, CONTENT_W - 0.34 * inch)
        b_lines = _wrap(body, "Helvetica", 9.5, CONTENT_W - 0.34 * inch)
        y = _ensure_space(c, y, _card_height(t_lines, b_lines) + 0.1 * inch)
        y = _draw_card(c, y, "No interaction pairs listed", body, (0.45, 0.52, 0.60))

    for it in interactions:
        pair = it.get("pair", [])
        title = " + ".join(pair) if pair else "Unknown pair"
        sev = str(it.get("severity", "unknown")).upper()
        expl = str(it.get("simple_explanation", ""))
        watch = it.get("what_to_watch_for", "")
        if isinstance(watch, list):
            watch = ", ".join(str(x) for x in watch if str(x).strip())
        next_step = str(it.get("recommended_next_step", ""))
        body_parts = [expl]
        if watch:
            body_parts.append(f"Watch for: {watch}")
        if next_step:
            body_parts.append(f"Next step: {next_step}")
        body = "\n".join(body_parts)

        t = f"{title} ({sev})"
        t_lines = _wrap(t, "Helvetica-Bold", 10, CONTENT_W - 0.34 * inch)
        b_lines = _wrap(body, "Helvetica", 9.5, CONTENT_W - 0.34 * inch)
        y = _ensure_space(c, y, _card_height(t_lines, b_lines) + 0.1 * inch)

        if "HIGH" in sev or "RED" in sev:
            accent = (0.75, 0.20, 0.18)
        elif "MODERATE" in sev or "YELLOW" in sev:
            accent = (0.78, 0.53, 0.10)
        else:
            accent = (0.22, 0.53, 0.29)
        y = _draw_card(c, y, t, body, accent)

    footer = "Decision support only. Not medical advice. Bring this report to a licensed clinician."
    c.setFillColorRGB(0.36, 0.42, 0.48)
    c.setFont("Helvetica-Oblique", 8)
    fy = BOTTOM_Y - 0.1 * inch
    for ln in _wrap(footer, "Helvetica-Oblique", 8, CONTENT_W):
        c.drawString(MARGIN_X, fy, ln)
        fy -= 9

    c.showPage()
    c.save()
    out = buf.getvalue()
    buf.close()
    return out
