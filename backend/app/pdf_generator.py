"""
PDF Report Generator v1.1
Generates professional accessibility risk assessment reports in Hebrew
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from io import BytesIO
from datetime import datetime
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


# Hebrew copy mapping for PDF (matches frontend HEBREW_COPY)
HEBREW_COPY = {
    "risk": {
        "LOW": {
            "label": "רמת סיכון: נמוכה",
            "explanation": "מצב הנגישות טוב יחסית. מומלץ לבצע תחזוקה שוטפת."
        },
        "MEDIUM": {
            "label": "רמת סיכון: בינונית",
            "explanation": "קיימים ליקויי נגישות הדורשים טיפול כדי להפחית חשיפה."
        },
        "HIGH": {
            "label": "רמת סיכון: גבוהה",
            "explanation": "נמצאו ליקויי נגישות חמורים העלולים לחשוף אותך לתביעה או קנס."
        },
        "CRITICAL": {
            "label": "רמת סיכון: גבוהה מאוד",
            "explanation": "רמת סיכון גבוהה מאוד. האתר חשוף באופן משמעותי להליכים משפטיים."
        }
    },
    "checked_keys_map": {
        "ALT_MISSING": "תמונות ללא תיאור חלופי",
        "COLOR_CONTRAST": "ניגודיות צבעים",
        "ARIA": "תגיות ARIA",
        "FORM_LABELS": "תוויות טפסים",
        "KEYBOARD_ACCESS": "ניווט מקלדת",
        "FOCUS_VISIBLE": "נראות פוקוס"
    }
}


def generate_pdf_report(results: Dict[str, Any]) -> bytes:
    """
    Generate PDF accessibility risk assessment report (v1.1)

    Args:
        results: Scan results from scanner.py

    Returns:
        PDF as bytes
    """
    buffer = BytesIO()

    # Create PDF
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
        title=f"דוח הערכת סיכון נגישות - {results['url']}"
    )

    # Container for elements
    elements = []

    # Add content
    elements.extend(_create_header(results))
    elements.append(Spacer(1, 0.5*cm))

    elements.extend(_create_risk_assessment(results))
    elements.append(Spacer(1, 0.5*cm))

    elements.extend(_create_summary(results))
    elements.append(Spacer(1, 0.5*cm))

    elements.extend(_create_coverage_info(results))
    elements.append(PageBreak())

    elements.extend(_create_recommendations(results))

    # Build PDF
    doc.build(elements)

    # Get PDF bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes


def _get_hebrew_styles():
    """
    Create Hebrew-compatible text styles
    Note: For production, you'd need to register Hebrew fonts
    For MVP, we'll use standard fonts with RTL support
    """
    styles = getSampleStyleSheet()

    # Hebrew heading style
    hebrew_heading = ParagraphStyle(
        'HebrewHeading',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        alignment=TA_RIGHT,
        rightIndent=0,
        leftIndent=0,
        textColor=colors.HexColor('#1a1a1a')
    )

    # Hebrew body style
    hebrew_body = ParagraphStyle(
        'HebrewBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        alignment=TA_RIGHT,
        rightIndent=0,
        leftIndent=0,
        leading=16
    )

    # Hebrew bullet style
    hebrew_bullet = ParagraphStyle(
        'HebrewBullet',
        parent=hebrew_body,
        fontSize=10,
        leftIndent=20,
        bulletIndent=10
    )

    # Large centered style for risk level
    risk_style = ParagraphStyle(
        'RiskLevel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        alignment=TA_CENTER,
        spaceAfter=12
    )

    return {
        'heading': hebrew_heading,
        'body': hebrew_body,
        'bullet': hebrew_bullet,
        'risk': risk_style
    }


def _create_header(results: Dict[str, Any]) -> list:
    """Create report header"""
    styles = _get_hebrew_styles()
    elements = []

    # Title
    title = Paragraph(
        "דוח הערכת סיכון נגישות",
        styles['heading']
    )
    elements.append(title)
    elements.append(Spacer(1, 0.3*cm))

    # Parse timestamp
    timestamp = results['timestamp'].replace('Z', '+00:00')
    try:
        dt = datetime.fromisoformat(timestamp)
        formatted_date = dt.strftime('%d/%m/%Y %H:%M')
    except:
        formatted_date = results['timestamp']

    # Metadata table
    metadata = [
        ['URL:', results['url']],
        ['תאריך סריקה:', formatted_date],
        ['מזהה סריקה:', results['scan_id']],
        ['תקן:', 'תקן ישראלי 5568']
    ]

    table = Table(metadata, colWidths=[4*cm, 12*cm])
    table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(table)

    return elements


def _create_risk_assessment(results: Dict[str, Any]) -> list:
    """Create risk assessment section (PRIMARY OUTPUT)"""
    styles = _get_hebrew_styles()
    elements = []

    # Get risk level
    risk_level = results['risk']['level']
    risk_data = HEBREW_COPY['risk'].get(risk_level, HEBREW_COPY['risk']['MEDIUM'])

    elements.append(Paragraph("הערכת סיכון משפטי", styles['heading']))
    elements.append(Spacer(1, 0.3*cm))

    # Risk level color
    risk_color = {
        'LOW': colors.green,
        'MEDIUM': colors.orange,
        'HIGH': colors.red,
        'CRITICAL': colors.HexColor('#880000')
    }.get(risk_level, colors.orange)

    # Risk level display
    risk_table_data = [[risk_data['label']]]
    risk_table = Table(risk_table_data, colWidths=[16*cm])
    risk_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 28),
        ('TEXTCOLOR', (0, 0), (-1, -1), risk_color),
        ('BOX', (0, 0), (-1, -1), 3, risk_color),
        ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
        ('TOPPADDING', (0, 0), (-1, -1), 25),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 25),
    ]))
    elements.append(risk_table)
    elements.append(Spacer(1, 0.5*cm))

    # Explanation
    elements.append(Paragraph("<b>מה זה אומר?</b>", styles['body']))
    elements.append(Paragraph(risk_data['explanation'], styles['body']))

    if risk_level in ['HIGH', 'CRITICAL']:
        elements.append(Spacer(1, 0.3*cm))
        warning_text = "האתר עלול שלא לעמוד בדרישות תקן הנגישות הישראלי ולהיות חשוף לתביעה או קנס."
        elements.append(Paragraph(f"<b>{warning_text}</b>", styles['body']))

    return elements


def _create_summary(results: Dict[str, Any]) -> list:
    """Create summary section with score and issues"""
    styles = _get_hebrew_styles()
    elements = []

    # Score
    score = results['score']
    score_color = (
        colors.green if score >= 80
        else colors.orange if score >= 60
        else colors.red
    )

    elements.append(Paragraph("ציון נגישות", styles['heading']))
    elements.append(Spacer(1, 0.2*cm))

    # Score table
    score_data = [[f"{score}/100"]]
    score_table = Table(score_data, colWidths=[16*cm])
    score_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 36),
        ('TEXTCOLOR', (0, 0), (-1, -1), score_color),
        ('BOX', (0, 0), (-1, -1), 2, colors.grey),
        ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
        ('TOPPADDING', (0, 0), (-1, -1), 20),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
    ]))
    elements.append(score_table)
    elements.append(Spacer(1, 0.3*cm))

    # Issues summary
    summary = results['summary']
    issues_data = [
        ['סוג ליקוי', 'כמות'],
        ['קריטי', str(summary['critical'])],
        ['חמור', str(summary['serious'])],
        ['בינוני', str(summary['moderate'])],
        ['קל', str(summary['minor'])],
        ['סה"כ', str(summary['total'])]
    ]

    issues_table = Table(issues_data, colWidths=[8*cm, 8*cm])
    issues_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.whitesmoke])
    ]))
    elements.append(issues_table)

    return elements


def _create_coverage_info(results: Dict[str, Any]) -> list:
    """Create coverage information section"""
    styles = _get_hebrew_styles()
    elements = []

    elements.append(Paragraph("כיסוי הבדיקה", styles['heading']))
    elements.append(Spacer(1, 0.2*cm))

    coverage = results['coverage']
    automated_pct = int(coverage['automated_estimate'] * 100)
    manual_pct = 100 - automated_pct

    coverage_text = f"""
    <b>כיסוי אוטומטי כולל: {automated_pct}%</b><br/>
    נדרש בדיקה ידנית: {manual_pct}%
    """
    elements.append(Paragraph(coverage_text, styles['body']))
    elements.append(Spacer(1, 0.3*cm))

    # What we checked
    elements.append(Paragraph("<b>מה בדקנו אוטומטית:</b>", styles['body']))
    for key in coverage.get('checked_keys', []):
        hebrew_label = HEBREW_COPY['checked_keys_map'].get(key, key)
        elements.append(Paragraph(f"• {hebrew_label}", styles['bullet']))

    elements.append(Spacer(1, 0.2*cm))

    # What requires manual check
    elements.append(Paragraph("<b>מה דורש בדיקה ידנית:</b>", styles['body']))
    manual_items = ["איכות תיאורים חלופיים", "כתוביות לוידאו", "חווית קורא מסך", "בהירות תוכן"]
    for item in manual_items:
        elements.append(Paragraph(f"• {item}", styles['bullet']))

    return elements


def _create_recommendations(results: Dict[str, Any]) -> list:
    """Create recommendations section"""
    styles = _get_hebrew_styles()
    elements = []

    elements.append(Paragraph("המלצות לצעדים הבאים", styles['heading']))
    elements.append(Spacer(1, 0.2*cm))

    risk_level = results['risk']['level']

    # Recommendations based on risk level
    if risk_level == 'CRITICAL':
        recommendations = [
            "פנה מיידית לבודק נגישות מוסמך לבדיקה מקיפה",
            "טפל בליקויים הקריטיים בהקדם האפשרי",
            "שקול התייעצות משפטית בנושא חשיפה לתביעות",
            "הכן תוכנית תיקון עם לוחות זמנים ברורים"
        ]
    elif risk_level == 'HIGH':
        recommendations = [
            "טפל בליקויים הקריטיים והחמורים בהקדם",
            "בצע בדיקה ידנית מקצועית",
            "הכן תוכנית תיקון עם לוחות זמנים",
            "שקול הכשרת צוות בנושאי נגישות"
        ]
    elif risk_level == 'MEDIUM':
        recommendations = [
            "טפל בליקויים שנמצאו כדי להפחית חשיפה",
            "בצע בדיקה ידנית להשלמת הכיסוי",
            "שלב בדיקות נגישות בתהליך הפיתוח"
        ]
    else:  # LOW
        recommendations = [
            "המשך לתחזק את רמת הנגישות הקיימת",
            "בצע בדיקות תקופתיות",
            "שלב בדיקות נגישות אוטומטיות ב-CI/CD"
        ]

    for i, step in enumerate(recommendations, 1):
        elements.append(Paragraph(f"{i}. {step}", styles['body']))
        elements.append(Spacer(1, 0.1*cm))

    elements.append(Spacer(1, 0.5*cm))

    # Disclaimer
    disclaimer = """
    <b>הצהרת אחריות:</b><br/>
    דוח זה מבוסס על סריקה אוטומטית ומזהה בממוצע 75% מבעיות הנגישות.
    נגישות מלאה דורשת גם בדיקה ידנית מקצועית.
    השימוש בדוח אינו מהווה ייעוץ משפטי.
    להתייעצות משפטית, פנה לעורך דין מוסמך.
    """
    elements.append(Paragraph(disclaimer, styles['body']))

    # Footer
    elements.append(Spacer(1, 0.5*cm))
    footer = f"נוצר על ידי Israeli Accessibility Scanner | {datetime.now().strftime('%d/%m/%Y')}"
    elements.append(Paragraph(footer, ParagraphStyle('footer', alignment=TA_CENTER, fontSize=9)))

    return elements
