"""
PDF Report Generator v3.1 – WeasyPrint Edition (Polished)
Generates professional accessibility risk assessment reports in Hebrew.
Uses HTML/CSS with native RTL support via WeasyPrint.

Structure:
  1. Cover – logo, score, site name, date, risk level
  2. Legal overview – Israeli accessibility law + standard 5568
  3. Issues table – by severity
  4. Detailed issues – description, impact, fix (with code examples)
  5. Standards checklist – checked criteria
  6. Recommendations – prioritised action items
  7. Resources & links
  8. Legal disclaimer + signature
"""

from weasyprint import HTML
from io import BytesIO
from datetime import datetime
from typing import Dict, Any, List
import logging
import html as html_module

logger = logging.getLogger(__name__)

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
    "critical": "#dc2626",
    "serious": "#d97706",
    "moderate": "#0891b2",
    "minor": "#6b7280",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _esc(value) -> str:
    """Escape HTML special characters."""
    return html_module.escape(str(value))


def _fmt_date(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return ts


def _score_color(score: int) -> str:
    if score >= 80:
        return "#059669"
    if score >= 60:
        return "#d97706"
    return "#dc2626"


def _risk_color(level: str) -> str:
    return {
        "LOW": "#059669",
        "MEDIUM": "#d97706",
        "HIGH": "#dc2626",
        "CRITICAL": "#880000",
    }.get(level, "#d97706")


# ---------------------------------------------------------------------------
# Inline SVG logo
# ---------------------------------------------------------------------------
LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 120" width="320" height="80">
  <defs>
    <linearGradient id="tg" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#00D4AA"/>
      <stop offset="35%" stop-color="#00C9A7"/>
      <stop offset="65%" stop-color="#2196F3"/>
      <stop offset="100%" stop-color="#6C63FF"/>
    </linearGradient>
    <linearGradient id="rg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#E040FB"/>
      <stop offset="50%" stop-color="#7C4DFF"/>
      <stop offset="100%" stop-color="#448AFF"/>
    </linearGradient>
    <linearGradient id="ig" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#536DFE"/>
      <stop offset="100%" stop-color="#7C4DFF"/>
    </linearGradient>
  </defs>
  <text x="12" y="42" font-family="sans-serif" font-weight="800" font-size="22" letter-spacing="3" fill="url(#tg)">ISRAELI ACCESSIBILITY</text>
  <text x="12" y="95" font-family="sans-serif" font-weight="900" font-size="56" letter-spacing="2" fill="url(#tg)">SCANNER</text>
  <circle cx="430" cy="60" r="28" fill="none" stroke="url(#rg)" stroke-width="2.5"/>
  <circle cx="430" cy="60" r="22" fill="none" stroke="url(#ig)" stroke-width="1" opacity="0.4"/>
  <g transform="translate(430, 60)">
    <path d="M-14,0 Q-7,-10 0,-10 Q7,-10 14,0 Q7,10 0,10 Q-7,10 -14,0 Z" fill="none" stroke="url(#ig)" stroke-width="1.5" opacity="0.8"/>
    <circle cx="0" cy="0" r="4" fill="url(#ig)" opacity="0.9"/>
    <circle cx="-1" cy="-1" r="1.3" fill="white" opacity="0.5"/>
    <line x1="-15" y1="15" x2="15" y2="-15" stroke="url(#rg)" stroke-width="2" stroke-linecap="round" opacity="0.65"/>
  </g>
</svg>"""


# ---------------------------------------------------------------------------
# Section builders (return HTML strings)
# ---------------------------------------------------------------------------

def _build_cover_html(results: Dict) -> str:
    score = int(results.get("score", 0))
    risk = results.get("risk", {})
    level = risk.get("level", "MEDIUM")
    risk_data = RISK_COPY.get(level, RISK_COPY["MEDIUM"])

    fine_html = ""
    if risk.get("estimated_fine"):
        fine_html = f'<p class="fine-note"><strong>טווח קנסות משוער:</strong> {_esc(risk["estimated_fine"])}</p>'

    return f"""
    <div class="logo-container">{LOGO_SVG}</div>

    <h1 class="title">דו"ח הערכת סיכון נגישות</h1>

    <table class="meta-table">
      <tr><td class="meta-label">כתובת אתר:</td><td>{_esc(results.get("url", ""))}</td></tr>
      <tr><td class="meta-label">תאריך סריקה:</td><td>{_esc(_fmt_date(results.get("timestamp", "")))}</td></tr>
      <tr><td class="meta-label">מזהה סריקה:</td><td>{_esc(results.get("scan_id", ""))}</td></tr>
      <tr><td class="meta-label">תקן:</td><td>WCAG 2.2 AA / תקן ישראלי 5568</td></tr>
    </table>

    <div class="score-box" style="color: {_score_color(score)};">
      ציון נגישות: {score} / 100
    </div>
    <p class="score-note">
      ציון הנגישות נע בין 0 ל-100, ומבוסס על עמידה בהנחיות WCAG 2.2 ברמה AA ותקן ישראלי 5568.
      ציון נמוך מצביע על בעיות נגישות משמעותיות הדורשות טיפול.
    </p>

    <div class="risk-box" style="border-color: {_risk_color(level)}; color: {_risk_color(level)};">
      רמת סיכון משפטי: {_esc(risk_data["label"])}
    </div>
    <p class="risk-note">
      רמת הסיכון המשפטי מוערכת על בסיס מספר הליקויים וחומרתם,
      בהתאם לקריטריונים שנקבעו בחוק הנגישות הישראלי.
    </p>
    <p class="risk-explanation">{_esc(risk_data["explanation"])}</p>
    {fine_html}
    """


def _build_legal_overview_html() -> str:
    return """
    <div class="page-break"></div>
    <h2>סקירה משפטית</h2>
    <p>
      חוק שוויון זכויות לאנשים עם מוגבלות (תיקון מס' 15) מחייב כל גוף
      להנגיש את שירותי האינטרנט שלו בהתאם לתקן הישראלי 5568.
      התקן מבוסס על הנחיות WCAG 2.2 ברמה AA.
      אי-עמידה בתקן עלולה להוביל לתביעות אזרחיות, קנסות מנהליים
      ופגיעה במוניטין.
    </p>
    <ul class="legal-list">
      <li>הנגשת האתר לפי WCAG 2.2 AA.</li>
      <li>פרסום הצהרת נגישות באתר.</li>
      <li>מינוי רכז/ת נגישות.</li>
      <li>ביצוע סקר נגישות תקופתי.</li>
    </ul>
    """


def _build_issues_table_html(results: Dict) -> str:
    summary = results.get("summary", {})
    rows = [
        ("קריטי", summary.get("critical", 0), SEVERITY_COLORS["critical"]),
        ("חמור", summary.get("serious", 0), SEVERITY_COLORS["serious"]),
        ("בינוני", summary.get("moderate", 0), SEVERITY_COLORS["moderate"]),
        ("קל", summary.get("minor", 0), SEVERITY_COLORS["minor"]),
    ]
    total = summary.get("total", 0)

    rows_html = ""
    for label, count, color in rows:
        rows_html += f'<tr><td>{label}</td><td style="color:{color};font-weight:bold;">{count}</td></tr>\n'

    return f"""
    <h2>סיכום ממצאים לפי חומרה</h2>
    <table class="summary-table">
      <thead>
        <tr><th>סוג ליקוי</th><th>כמות</th></tr>
      </thead>
      <tbody>
        {rows_html}
        <tr class="total-row"><td>סה"כ</td><td>{total}</td></tr>
      </tbody>
    </table>
    """


def _build_detailed_issues_html(results: Dict) -> str:
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
        return """
        <div class="page-break"></div>
        <h2>פירוט ממצאים</h2>
        <p>לא נמצאו ליקויים בסריקה האוטומטית.</p>
        """

    # Sort: critical first
    severity_order = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}
    all_issues.sort(key=lambda x: severity_order.get(x["severity"], 9))

    issues_html = '<div class="page-break"></div>\n<h2>פירוט ממצאים</h2>\n'

    for i, issue in enumerate(all_issues, 1):
        sev = issue["severity"]
        sev_label = SEVERITY_LABELS.get(sev, sev)
        sev_color = SEVERITY_COLORS.get(sev, "#6b7280")

        issue_html = f'<div class="issue" style="border-right-color: {sev_color};">\n'
        issue_html += f'  <h3>{i}. {_esc(issue["title"])} '
        issue_html += f'<span class="severity-badge" style="background:{sev_color};">{sev_label}</span></h3>\n'

        if issue.get("help"):
            issue_html += f'  <p>{_esc(issue["help"])}</p>\n'

        if issue.get("wcag"):
            issue_html += f'  <p class="wcag-ref">WCAG: {_esc(issue["wcag"])}</p>\n'

        fix = issue.get("fix", {})
        if fix:
            if fix.get("summary_he"):
                issue_html += f'  <p><strong>כיצד לתקן:</strong> {_esc(fix["summary_he"])}</p>\n'
            if fix.get("impact"):
                issue_html += f'  <p><strong>השפעה:</strong> {_esc(fix["impact"])}</p>\n'
            if fix.get("code_example"):
                code = _esc(fix["code_example"].strip())
                issue_html += f'  <pre><code>{code}</code></pre>\n'

        issue_html += '</div>\n'
        issues_html += issue_html

    return issues_html


def _build_standards_checklist_html(results: Dict) -> str:
    coverage = results.get("coverage", {})
    checked_keys = coverage.get("checked_keys", [])
    auto_pct = int(coverage.get("automated_estimate", 0.77) * 100)

    checked_items = ""
    for key in checked_keys:
        label = CHECKED_KEYS_MAP.get(key, key)
        checked_items += f"<li>✔ {_esc(label)}</li>\n"

    manual_items_list = [
        "איכות תיאורים חלופיים",
        "כתוביות לוידאו",
        "חווית קורא מסך",
        "בהירות תוכן וקישורים",
    ]
    manual_html = ""
    for item in manual_items_list:
        manual_html += f"<li>✖ {item}</li>\n"

    return f"""
    <h2>עמידה בתקן – רשימת בדיקות</h2>
    <p><strong>כיסוי אוטומטי כולל: {auto_pct}%</strong></p>

    <p><strong>נבדק אוטומטית:</strong></p>
    <ul class="checklist">{checked_items}</ul>

    <p><strong>דורש בדיקה ידנית:</strong></p>
    <ul class="checklist">{manual_html}</ul>
    """


def _build_recommendations_html(results: Dict) -> str:
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

    items = ""
    for i, step in enumerate(recs.get(level, recs["MEDIUM"]), 1):
        items += f"<li>{step}</li>\n"

    return f"""
    <h2>המלצות לצעדים הבאים</h2>
    <ol class="recommendations-list">{items}</ol>
    """


def _build_resources_html() -> str:
    return """
    <div class="resources-section">
      <h2>מקורות מידע נוספים</h2>
      <p class="resources-links">
        <a href="https://www.w3.org/WAI/WCAG22/quickref/">WCAG 2.2 Guidelines</a> |
        <a href="https://www.nevo.co.il/law_html/law01/999_969.htm">חוק הנגישות הישראלי</a> |
        <a href="https://www.gov.il/he/departments/topics/accessibility">נגישות – אתר ממשלתי</a>
      </p>
    </div>
    """


def _build_disclaimer_html() -> str:
    today = datetime.now().strftime("%d/%m/%Y")
    return f"""
    <div class="disclaimer">
      <p>
        <strong>הצהרת אחריות:</strong><br>
        דו"ח זה מבוסס על סריקה אוטומטית ומזהה בממוצע 77% מבעיות הנגישות.
        נגישות מלאה דורשת גם בדיקה ידנית מקצועית.
        השימוש בדו"ח אינו מהווה ייעוץ משפטי.
        להתייעצות משפטית, פנה לעורך דין מוסמך.
      </p>
    </div>

    <div class="signature-block">
      <p>
        דו"ח זה נוצר באופן אוטומטי על ידי Israeli Accessibility Scanner.<br>
        תאריך הפקה: {today}
      </p>
      <div class="signature-logo">{LOGO_SVG}</div>
    </div>
    """


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
REPORT_CSS = """
@page {
  size: A4;
  margin: 2cm;

  @bottom-center {
    content: counter(page) " / " counter(pages);
    font-family: "DejaVu Sans", sans-serif;
    font-size: 8px;
    color: #aaa;
  }
}

body {
  font-family: "DejaVu Sans", "Noto Sans Hebrew", "Arial", sans-serif;
  direction: rtl;
  text-align: right;
  font-size: 11px;
  line-height: 1.7;
  color: #1f2937;
}

p {
  margin-bottom: 10px;
}

/* Logo */
.logo-container {
  text-align: center;
  margin-bottom: 20px;
}
.logo-container svg {
  display: inline-block;
}

/* Title */
h1.title {
  font-size: 28px;
  text-align: center;
  color: #111827;
  margin-bottom: 24px;
  padding-bottom: 12px;
  border-bottom: 3px solid #e5e7eb;
}

/* Section headings */
h2 {
  font-size: 18px;
  color: #1a56db;
  border-bottom: 2px solid #e5e7eb;
  padding-bottom: 8px;
  margin-top: 32px;
  margin-bottom: 16px;
}

h3 {
  font-size: 13px;
  margin-bottom: 6px;
  margin-top: 8px;
}

/* Meta table */
.meta-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 28px;
}
.meta-table td {
  padding: 8px 10px;
  font-size: 11px;
  border-bottom: 1px solid #f3f4f6;
}
.meta-label {
  font-weight: bold;
  width: 130px;
  color: #374151;
}

/* Score box */
.score-box {
  font-size: 48px;
  font-weight: bold;
  text-align: center;
  margin: 24px 0 12px 0;
  padding: 24px;
  background: #f9fafb;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
}

.score-note {
  font-size: 10px;
  color: #6b7280;
  text-align: center;
  margin-bottom: 24px;
  line-height: 1.6;
  font-style: italic;
}

/* Risk box */
.risk-box {
  background-color: #fef7f0;
  border: 3px solid;
  padding: 18px;
  margin: 24px 0 12px 0;
  font-weight: bold;
  font-size: 24px;
  text-align: center;
  border-radius: 8px;
}

.risk-note {
  font-size: 10px;
  color: #6b7280;
  text-align: center;
  margin-bottom: 12px;
  line-height: 1.6;
  font-style: italic;
}

.risk-explanation {
  font-size: 12px;
  color: #374151;
  text-align: center;
  margin-bottom: 8px;
  font-weight: 500;
}

.fine-note {
  font-size: 12px;
  text-align: center;
  color: #dc2626;
  margin-bottom: 16px;
}

/* Legal list */
.legal-list {
  padding-right: 20px;
  margin-top: 12px;
  margin-bottom: 16px;
}
.legal-list li {
  margin-bottom: 8px;
  line-height: 1.7;
}

/* Summary table */
.summary-table {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0 28px 0;
}
.summary-table th, .summary-table td {
  border: 1px solid #d1d5db;
  padding: 10px 14px;
  text-align: center;
  font-size: 12px;
}
.summary-table thead tr {
  background: #e5e7eb;
  font-weight: bold;
}
.summary-table tbody tr:nth-child(even) {
  background: #f9fafb;
}
.total-row {
  background: #e5e7eb !important;
  font-weight: bold;
}

/* Issues */
.issue {
  margin-bottom: 28px;
  border-right: 5px solid #eee;
  padding-right: 14px;
  padding-bottom: 12px;
  padding-top: 4px;
}

.issue p {
  margin-bottom: 6px;
  line-height: 1.7;
}

.severity-badge {
  color: white;
  padding: 3px 12px;
  border-radius: 4px;
  font-size: 10px;
  margin-right: 8px;
  display: inline-block;
}

.wcag-ref {
  font-size: 10px;
  color: #6b7280;
  margin-top: 2px;
}

/* Code blocks */
code, pre {
  font-family: "DejaVu Sans Mono", "Courier New", monospace;
  background: #f8f9fa;
  direction: ltr;
  text-align: left;
  padding: 10px 12px;
  display: block;
  font-size: 9px;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
  margin-top: 8px;
}

/* Checklists */
.checklist {
  list-style: none;
  padding-right: 0;
  margin-bottom: 16px;
}
.checklist li {
  margin-bottom: 6px;
  font-size: 11px;
  line-height: 1.6;
}

/* Recommendations */
.recommendations-list {
  padding-right: 22px;
  margin-bottom: 16px;
}
.recommendations-list li {
  margin-bottom: 10px;
  line-height: 1.7;
}

/* Resources */
.resources-section {
  margin-top: 32px;
  padding-top: 16px;
  border-top: 1px solid #e5e7eb;
}

.resources-links {
  font-size: 11px;
  direction: ltr;
  text-align: right;
}

.resources-links a {
  color: #1a56db;
  text-decoration: underline;
}

/* Disclaimer */
.disclaimer {
  font-size: 10px;
  color: #666;
  border-top: 2px solid #d1d5db;
  margin-top: 40px;
  padding-top: 20px;
  line-height: 1.7;
}

/* Signature block */
.signature-block {
  margin-top: 24px;
  padding-top: 16px;
  text-align: center;
  border-top: 1px dashed #d1d5db;
}

.signature-block p {
  font-size: 10px;
  color: #9ca3af;
  line-height: 1.6;
  margin-bottom: 12px;
}

.signature-logo {
  text-align: center;
  opacity: 0.6;
}

.signature-logo svg {
  width: 200px;
  height: auto;
}

/* Page breaks */
.page-break {
  page-break-before: always;
}
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate_pdf_report(results: Dict[str, Any]) -> bytes:
    """Generate a complete Hebrew PDF accessibility report.

    Returns raw PDF bytes, compatible with the existing route API.
    """
    sections = [
        _build_cover_html(results),
        _build_legal_overview_html(),
        _build_issues_table_html(results),
        _build_detailed_issues_html(results),
        _build_standards_checklist_html(results),
        _build_recommendations_html(results),
        _build_resources_html(),
        _build_disclaimer_html(),
    ]

    body_content = "\n".join(sections)

    html_str = f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="UTF-8">
  <style>{REPORT_CSS}</style>
</head>
<body>
{body_content}
</body>
</html>"""

    buf = BytesIO()
    HTML(string=html_str).write_pdf(buf)
    pdf_bytes = buf.getvalue()
    buf.close()

    logger.info(f"Generated PDF report ({len(pdf_bytes)} bytes)")
    return pdf_bytes
