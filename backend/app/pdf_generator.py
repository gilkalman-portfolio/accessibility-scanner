"""
PDF Report Generator v2.0
Generates professional accessibility risk assessment reports in Hebrew.
Structure per pdf_creator.md:
  1. Cover – score, site name, date, risk level
  2. Legal overview – Israeli accessibility law + standard 5568
  3. Issues table – by severity
  4. Detailed issues – description, impact, fix (with code examples)
  5. Standards checklist – checked criteria
  6. Recommendations – prioritised action items
  7. Legal disclaimer
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from io import BytesIO
from datetime import datetime
from typing import Dict, Any, List
import logging
import os
import re

try:
    from bidi.algorithm import get_display as _bidi_display
    _HAS_BIDI = True
except ImportError:
    _HAS_BIDI = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BiDi helper – reorders Hebrew text for ReportLab's LTR renderer
# ---------------------------------------------------------------------------
_HEB_RE = re.compile(r'[\u0590-\u05FF]')  # Hebrew Unicode block


def _heb(text: str) -> str:
    """Apply BiDi algorithm to text containing Hebrew characters.

    Preserves HTML tags (<b>, <br/>, <pre>, etc.) by processing only the
    text segments between tags.  Skips text that has no Hebrew chars.
    """
    if not _HAS_BIDI or not text or not _HEB_RE.search(text):
        return text

    # Split on HTML tags, apply bidi only to non-tag segments
    parts = re.split(r'(<[^>]+>)', text)
    result = []
    for part in parts:
        if part.startswith('<'):
            result.append(part)
        elif _HEB_RE.search(part):
            result.append(_bidi_display(part))
        else:
            result.append(part)
    return ''.join(result)


# ---------------------------------------------------------------------------
# Font registration
# ---------------------------------------------------------------------------
_HEBREW_FONT_REGISTERED = False
_HEBREW_FONT_NAME = "Helvetica"
_HEBREW_FONT_BOLD = "Helvetica-Bold"


def _register_hebrew_font():
    """Attempt to register a Hebrew-capable font (DejaVu Sans)."""
    global _HEBREW_FONT_REGISTERED, _HEBREW_FONT_NAME, _HEBREW_FONT_BOLD

    if _HEBREW_FONT_REGISTERED:
        return

    # Common locations for DejaVu Sans
    search_paths = [
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        # Windows
        os.path.expandvars(r"%WINDIR%\Fonts\DejaVuSans.ttf"),
        os.path.expandvars(r"%WINDIR%\Fonts\DejaVuSans-Bold.ttf"),
        # Docker / playwright image
        "/usr/share/fonts/DejaVuSans.ttf",
        "/usr/share/fonts/DejaVuSans-Bold.ttf",
        # Bundled next to this file
        os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf"),
        os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans-Bold.ttf"),
    ]

    regular = None
    bold = None
    for p in search_paths:
        if os.path.isfile(p):
            if "Bold" in p:
                bold = p
            else:
                regular = p

    if regular:
        try:
            pdfmetrics.registerFont(TTFont("HebrewFont", regular))
            _HEBREW_FONT_NAME = "HebrewFont"
            if bold:
                pdfmetrics.registerFont(TTFont("HebrewFontBold", bold))
                _HEBREW_FONT_BOLD = "HebrewFontBold"
            else:
                _HEBREW_FONT_BOLD = "HebrewFont"
            logger.info(f"Registered Hebrew font: {regular}")
        except Exception as e:
            logger.warning(f"Could not register Hebrew font: {e}")

    _HEBREW_FONT_REGISTERED = True


# ---------------------------------------------------------------------------
# Hebrew copy
# ---------------------------------------------------------------------------
RISK_COPY = {
    "LOW": {
        "label": "נמוכה",
        "explanation": "מצב הנגישות טוב יחסית. מומלץ לבצע תחזוקה שוטפת.",
    },
    "MEDIUM": {
        "label": "בינונית",
        "explanation": "קיימים ליקויי נגישות הדורשים טיפול כדי להפחית חשיפה.",
    },
    "HIGH": {
        "label": "גבוהה",
        "explanation": "נמצאו ליקויי נגישות חמורים העלולים לחשוף אותך לתביעה או קנס.",
    },
    "CRITICAL": {
        "label": "גבוהה מאוד",
        "explanation": "רמת סיכון גבוהה מאוד. האתר חשוף באופן משמעותי להליכים משפטיים.",
    },
}

CHECKED_KEYS_MAP = {
    "ALT_MISSING": "תמונות ללא תיאור חלופי",
    "COLOR_CONTRAST": "ניגודיות צבעים",
    "ARIA": "תגיות ARIA",
    "FORM_LABELS": "תוויות טפסים",
    "KEYBOARD_ACCESS": "ניווט מקלדת",
    "FOCUS_VISIBLE": "נראות פוקוס",
}

SEVERITY_LABELS = {
    "critical": "קריטי",
    "serious": "חמור",
    "moderate": "בינוני",
    "minor": "קל",
}

SEVERITY_COLORS = {
    "critical": colors.HexColor("#dc2626"),
    "serious": colors.HexColor("#d97706"),
    "moderate": colors.HexColor("#0891b2"),
    "minor": colors.HexColor("#6b7280"),
}


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
def _get_styles():
    _register_hebrew_font()
    base = getSampleStyleSheet()

    heading = ParagraphStyle(
        "HebHeading",
        parent=base["Heading1"],
        fontName=_HEBREW_FONT_BOLD,
        fontSize=18,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#111827"),
        spaceAfter=8,
    )

    subheading = ParagraphStyle(
        "HebSubheading",
        parent=base["Heading2"],
        fontName=_HEBREW_FONT_BOLD,
        fontSize=14,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#1a56db"),
        spaceAfter=6,
    )

    body = ParagraphStyle(
        "HebBody",
        parent=base["Normal"],
        fontName=_HEBREW_FONT_NAME,
        fontSize=10,
        alignment=TA_RIGHT,
        leading=15,
    )

    body_small = ParagraphStyle(
        "HebBodySmall",
        parent=body,
        fontSize=9,
        leading=13,
    )

    centered = ParagraphStyle(
        "HebCentered",
        parent=body,
        alignment=TA_CENTER,
    )

    centered_large = ParagraphStyle(
        "HebCenteredLarge",
        parent=centered,
        fontName=_HEBREW_FONT_BOLD,
        fontSize=28,
        spaceAfter=10,
    )

    code_style = ParagraphStyle(
        "CodeStyle",
        parent=base["Code"],
        fontName="Courier",
        fontSize=8,
        alignment=TA_LEFT,
        leading=11,
        backColor=colors.HexColor("#f3f4f6"),
    )

    return {
        "heading": heading,
        "subheading": subheading,
        "body": body,
        "body_small": body_small,
        "centered": centered,
        "centered_large": centered_large,
        "code": code_style,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate_pdf_report(results: Dict[str, Any]) -> bytes:
    """Generate a complete Hebrew PDF accessibility report."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=_heb(f"דוח הערכת סיכון נגישות – {results.get('url', '')}"),
    )

    elements: list = []
    s = _get_styles()

    # 1. Cover
    elements += _build_cover(results, s)
    elements.append(PageBreak())

    # 2. Legal overview
    elements += _build_legal_overview(s)
    elements.append(Spacer(1, 0.5 * cm))

    # 3. Issues table
    elements += _build_issues_table(results, s)
    elements.append(PageBreak())

    # 4. Detailed issues
    elements += _build_detailed_issues(results, s)
    elements.append(PageBreak())

    # 5. Standards checklist
    elements += _build_standards_checklist(results, s)
    elements.append(Spacer(1, 0.5 * cm))

    # 6. Recommendations
    elements += _build_recommendations(results, s)
    elements.append(Spacer(1, 0.5 * cm))

    # 7. Disclaimer + footer
    elements += _build_disclaimer(s)

    doc.build(elements)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def _fmt_date(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return ts


def _build_cover(results: Dict, s) -> list:
    """Cover page: score, site URL, date, risk level."""
    elems: list = []

    elems.append(Paragraph(_heb("דוח הערכת סיכון נגישות"), s["centered_large"]))
    elems.append(Spacer(1, 0.4 * cm))

    # Metadata
    meta = [
        [_heb("כתובת אתר:"), results.get("url", "")],
        [_heb("תאריך סריקה:"), _fmt_date(results.get("timestamp", ""))],
        [_heb("מזהה:"), results.get("scan_id", "")],
        [_heb("תקן:"), _heb("תקן ישראלי 5568 / WCAG 2.2 AA")],
    ]
    t = Table(meta, colWidths=[4 * cm, 12 * cm])
    t.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (0, -1), _HEBREW_FONT_BOLD),
        ("FONTNAME", (1, 0), (1, -1), _HEBREW_FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elems.append(t)
    elems.append(Spacer(1, 0.8 * cm))

    # Score
    score = results.get("score", 0)
    score_color = (
        colors.HexColor("#059669") if score >= 80
        else colors.HexColor("#d97706") if score >= 60
        else colors.HexColor("#dc2626")
    )
    elems.append(Paragraph(_heb("ציון נגישות"), s["subheading"]))
    score_tbl = Table([[f"{score} / 100"]], colWidths=[16 * cm])
    score_tbl.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, -1), _HEBREW_FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, -1), 36),
        ("TEXTCOLOR", (0, 0), (-1, -1), score_color),
        ("BOX", (0, 0), (-1, -1), 2, colors.HexColor("#e5e7eb")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f9fafb")),
        ("TOPPADDING", (0, 0), (-1, -1), 20),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
    ]))
    elems.append(score_tbl)
    elems.append(Spacer(1, 0.6 * cm))

    # Risk level
    risk = results.get("risk", {})
    level = risk.get("level", "MEDIUM")
    risk_data = RISK_COPY.get(level, RISK_COPY["MEDIUM"])
    risk_color = {
        "LOW": colors.HexColor("#059669"),
        "MEDIUM": colors.HexColor("#d97706"),
        "HIGH": colors.HexColor("#dc2626"),
        "CRITICAL": colors.HexColor("#880000"),
    }.get(level, colors.HexColor("#d97706"))

    elems.append(Paragraph(_heb("רמת סיכון משפטי"), s["subheading"]))
    risk_tbl = Table([[_heb(risk_data["label"])]], colWidths=[16 * cm])
    risk_tbl.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, -1), _HEBREW_FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, -1), 24),
        ("TEXTCOLOR", (0, 0), (-1, -1), risk_color),
        ("BOX", (0, 0), (-1, -1), 3, risk_color),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fafafa")),
        ("TOPPADDING", (0, 0), (-1, -1), 18),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
    ]))
    elems.append(risk_tbl)
    elems.append(Spacer(1, 0.3 * cm))
    elems.append(Paragraph(_heb(risk_data["explanation"]), s["body"]))

    if risk.get("estimated_fine"):
        elems.append(Spacer(1, 0.2 * cm))
        elems.append(Paragraph(
            _heb(f"<b>טווח קנסות משוער:</b> {risk['estimated_fine']}"), s["body"]
        ))

    return elems


def _build_legal_overview(s) -> list:
    """Section 2: short explanation of the law and standard 5568."""
    elems: list = []
    elems.append(Paragraph(_heb("סקירה משפטית"), s["heading"]))
    elems.append(Spacer(1, 0.2 * cm))

    text = (
        "חוק שוויון זכויות לאנשים עם מוגבלות (תיקון מס' 15) מחייב כל גוף "
        "להנגיש את שירותי האינטרנט שלו בהתאם לתקן הישראלי 5568. "
        "התקן מבוסס על הנחיות WCAG 2.2 ברמה AA. "
        "אי-עמידה בתקן עלולה להוביל לתביעות אזרחיות, קנסות מנהליים "
        "ופגיעה במוניטין."
    )
    elems.append(Paragraph(_heb(text), s["body"]))
    elems.append(Spacer(1, 0.2 * cm))

    obligations = [
        "הנגשת האתר לפי WCAG 2.2 AA.",
        "פרסום הצהרת נגישות באתר.",
        "מינוי רכז/ת נגישות.",
        "ביצוע סקר נגישות תקופתי.",
    ]
    for item in obligations:
        elems.append(Paragraph(_heb(f"• {item}"), s["body"]))

    return elems


def _build_issues_table(results: Dict, s) -> list:
    """Section 3: issues summary table by severity."""
    elems: list = []
    elems.append(Paragraph(_heb("סיכום ממצאים לפי חומרה"), s["heading"]))
    elems.append(Spacer(1, 0.2 * cm))

    summary = results.get("summary", {})
    data = [
        [_heb("סוג ליקוי"), _heb("כמות")],
        [_heb("קריטי"), str(summary.get("critical", 0))],
        [_heb("חמור"), str(summary.get("serious", 0))],
        [_heb("בינוני"), str(summary.get("moderate", 0))],
        [_heb("קל"), str(summary.get("minor", 0))],
        [_heb('סה"כ'), str(summary.get("total", 0))],
    ]

    tbl = Table(data, colWidths=[8 * cm, 8 * cm])

    style_cmds = [
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), _HEBREW_FONT_BOLD),
        ("FONTNAME", (0, -1), (-1, -1), _HEBREW_FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -2), _HEBREW_FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#d1d5db")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e5e7eb")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f9fafb")]),
    ]

    # Color the severity count cells
    severity_row_colors = [
        (1, colors.HexColor("#dc2626")),  # critical
        (2, colors.HexColor("#d97706")),  # serious
        (3, colors.HexColor("#0891b2")),  # moderate
        (4, colors.HexColor("#6b7280")),  # minor
    ]
    for row, clr in severity_row_colors:
        style_cmds.append(("TEXTCOLOR", (1, row), (1, row), clr))

    tbl.setStyle(TableStyle(style_cmds))
    elems.append(tbl)
    return elems


def _build_detailed_issues(results: Dict, s) -> list:
    """Section 4: detailed issue descriptions with fix instructions."""
    elems: list = []
    elems.append(Paragraph(_heb("פירוט ממצאים"), s["heading"]))
    elems.append(Spacer(1, 0.2 * cm))

    issues = results.get("issues", {})
    all_issues: List[Dict] = []

    # axe-core violations
    for v in issues.get("axe_core", []):
        nodes = v.get("nodes", [])
        all_issues.append({
            "title": v.get("description", v.get("id", "Unknown")),
            "severity": v.get("impact", "moderate"),
            "wcag": ", ".join(t for t in v.get("tags", []) if t.startswith("wcag")),
            "nodes_count": len(nodes),
            "help": v.get("help", ""),
            "help_url": v.get("helpUrl", ""),
        })

    # Playwright checks
    for c in issues.get("playwright", []):
        all_issues.append({
            "title": c.get("title_he", c.get("rule", "")),
            "severity": c.get("severity", "moderate"),
            "wcag": c.get("wcag", ""),
            "nodes_count": 1,
            "help": c.get("description_he", ""),
            "fix": c.get("how_to_fix", {}),
        })

    if not all_issues:
        elems.append(Paragraph(_heb("לא נמצאו ליקויים בסריקה האוטומטית."), s["body"]))
        return elems

    # Sort: critical first
    severity_order = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}
    all_issues.sort(key=lambda x: severity_order.get(x["severity"], 9))

    for i, issue in enumerate(all_issues, 1):
        sev = issue["severity"]
        sev_label = SEVERITY_LABELS.get(sev, sev)
        sev_color = SEVERITY_COLORS.get(sev, colors.grey)

        # Issue header
        header_data = [[_heb(f"{i}. {issue['title']}"), _heb(sev_label)]]
        header_tbl = Table(header_data, colWidths=[12 * cm, 4 * cm])
        header_tbl.setStyle(TableStyle([
            ("ALIGN", (0, 0), (0, 0), "RIGHT"),
            ("ALIGN", (1, 0), (1, 0), "CENTER"),
            ("FONTNAME", (0, 0), (0, 0), _HEBREW_FONT_BOLD),
            ("FONTNAME", (1, 0), (1, 0), _HEBREW_FONT_BOLD),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TEXTCOLOR", (1, 0), (1, 0), colors.white),
            ("BACKGROUND", (1, 0), (1, 0), sev_color),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elems.append(header_tbl)

        # Description
        if issue.get("help"):
            elems.append(Paragraph(_heb(issue["help"]), s["body_small"]))

        if issue.get("wcag"):
            elems.append(Paragraph(f"WCAG: {issue['wcag']}", s["body_small"]))

        # Fix instructions
        fix = issue.get("fix", {})
        if fix:
            if fix.get("summary_he"):
                elems.append(Paragraph(
                    _heb(f"<b>כיצד לתקן:</b> {fix['summary_he']}"), s["body_small"]
                ))
            if fix.get("impact"):
                elems.append(Paragraph(
                    _heb(f"<b>השפעה:</b> {fix['impact']}"), s["body_small"]
                ))
            if fix.get("code_example"):
                code = fix["code_example"].strip().replace("<", "&lt;").replace(">", "&gt;")
                elems.append(Spacer(1, 0.1 * cm))
                elems.append(Paragraph(f"<pre>{code}</pre>", s["code"]))

        elems.append(Spacer(1, 0.4 * cm))

    return elems


def _build_standards_checklist(results: Dict, s) -> list:
    """Section 5: what was checked vs what requires manual review."""
    elems: list = []
    elems.append(Paragraph(_heb("עמידה בתקן – רשימת בדיקות"), s["heading"]))
    elems.append(Spacer(1, 0.2 * cm))

    coverage = results.get("coverage", {})
    checked_keys = coverage.get("checked_keys", [])

    auto_pct = int(coverage.get("automated_estimate", 0.77) * 100)
    elems.append(Paragraph(
        _heb(f"<b>כיסוי אוטומטי כולל: {auto_pct}%</b>"), s["body"]
    ))
    elems.append(Spacer(1, 0.2 * cm))

    # Checked items
    elems.append(Paragraph(_heb("<b>נבדק אוטומטית:</b>"), s["body"]))
    for key in checked_keys:
        label = CHECKED_KEYS_MAP.get(key, key)
        elems.append(Paragraph(_heb(f"  ✔ {label}"), s["body_small"]))

    elems.append(Spacer(1, 0.3 * cm))

    # Manual items
    elems.append(Paragraph(_heb("<b>דורש בדיקה ידנית:</b>"), s["body"]))
    manual_items = [
        "איכות תיאורים חלופיים",
        "כתוביות לוידאו",
        "חווית קורא מסך",
        "בהירות תוכן וקישורים",
    ]
    for item in manual_items:
        elems.append(Paragraph(_heb(f"  ✖ {item}"), s["body_small"]))

    return elems


def _build_recommendations(results: Dict, s) -> list:
    """Section 6: prioritised recommendations."""
    elems: list = []
    elems.append(Paragraph(_heb("המלצות לצעדים הבאים"), s["heading"]))
    elems.append(Spacer(1, 0.2 * cm))

    risk = results.get("risk", {})
    level = risk.get("level", "MEDIUM")

    recs = {
        "CRITICAL": [
            "פנה מיידית לבודק נגישות מוסמך לבדיקה מקיפה.",
            "טפל בליקויים הקריטיים בהקדם האפשרי.",
            "שקול התייעצות משפטית בנושא חשיפה לתביעות.",
            "הכן תוכנית תיקון עם לוחות זמנים ברורים.",
        ],
        "HIGH": [
            "טפל בליקויים הקריטיים והחמורים בהקדם.",
            "בצע בדיקה ידנית מקצועית.",
            "הכן תוכנית תיקון עם לוחות זמנים.",
            "שקול הכשרת צוות בנושאי נגישות.",
        ],
        "MEDIUM": [
            "טפל בליקויים שנמצאו כדי להפחית חשיפה.",
            "בצע בדיקה ידנית להשלמת הכיסוי.",
            "שלב בדיקות נגישות בתהליך הפיתוח.",
        ],
        "LOW": [
            "המשך לתחזק את רמת הנגישות הקיימת.",
            "בצע בדיקות תקופתיות.",
            "שלב בדיקות נגישות אוטומטיות ב-CI/CD.",
        ],
    }

    for i, step in enumerate(recs.get(level, recs["MEDIUM"]), 1):
        elems.append(Paragraph(_heb(f"{i}. {step}"), s["body"]))
        elems.append(Spacer(1, 0.1 * cm))

    return elems


def _build_disclaimer(s) -> list:
    """Section 7: legal disclaimer and footer."""
    elems: list = []
    elems.append(Spacer(1, 0.5 * cm))

    disclaimer = (
        "<b>הצהרת אחריות:</b><br/>"
        "דוח זה מבוסס על סריקה אוטומטית ומזהה בממוצע 77% מבעיות הנגישות. "
        "נגישות מלאה דורשת גם בדיקה ידנית מקצועית. "
        "השימוש בדוח אינו מהווה ייעוץ משפטי. "
        "להתייעצות משפטית, פנה לעורך דין מוסמך."
    )
    elems.append(Paragraph(_heb(disclaimer), s["body_small"]))
    elems.append(Spacer(1, 0.5 * cm))

    footer = (
        f"נוצר על ידי Israeli Accessibility Scanner | "
        f"{datetime.now().strftime('%d/%m/%Y')}"
    )
    elems.append(Paragraph(_heb(footer), s["centered"]))

    return elems
