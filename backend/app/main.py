"""
Israeli Accessibility Scanner API
Main FastAPI application
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, HttpUrl, EmailStr
from typing import Optional, Literal
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from .payment import PaymentService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Israeli Accessibility Scanner API",
    description="Hebrew-first WCAG 2.2 AA & Israeli Standard 5568 compliance checker",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware – allow Vercel frontend + local dev
_default_origins = ",".join([
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:8888",
    "https://frontend-sooty-omega-76.vercel.app",
])
_allowed_origins = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",") if o.strip()
]
_allow_origin_regex = r"https://.*\.vercel\.app"

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


# Request/Response models
class ScanRequest(BaseModel):
    url: HttpUrl
    standard: Literal["WCAG_2_2_AA", "IL_5568"] = "IL_5568"
    locale: Literal["he", "en"] = "he"
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com",
                "standard": "IL_5568",
                "locale": "he"
            }
        }


class SendReportRequest(BaseModel):
    url: HttpUrl
    scan_id: str = ""
    email: EmailStr

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com",
                "scan_id": "scan_abc123",
                "email": "user@example.com"
            }
        }


class HealthResponse(BaseModel):
    status: str
    version: str
    coverage: dict


class CreatePaymentRequest(BaseModel):
    url: HttpUrl
    email: EmailStr
    scan_id: str = ""

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com",
                "email": "user@example.com",
                "scan_id": "scan_abc123",
            }
        }


class PaymentResponse(BaseModel):
    session_id: str
    payment_url: str
    demo_mode: bool


class PaymentVerifyResponse(BaseModel):
    status: str
    pdf_token: Optional[str] = None
    email: str
    scan_url: str
    demo_mode: bool = False


# Payment service singleton
payment_service = PaymentService()


# Routes
@app.get("/", response_model=HealthResponse)
async def root():
    """
    API health check
    """
    return {
        "status": "ok",
        "version": "1.0.0",
        "coverage": {
            "axe_core": "57%",
            "playwright_checks": "20%",
            "total_automated": "77%",
            "manual_required": "23%"
        }
    }


@app.get("/health")
async def health():
    """
    Health check endpoint for monitoring
    """
    return {"status": "healthy"}


@app.post("/api/v1/scan")
async def scan_page(request: ScanRequest):
    """
    Scan a single URL for accessibility issues
    
    Returns:
    - Overall score (0-100)
    - Issue breakdown by severity
    - Detailed issues with fix instructions
    - Legal risk assessment (Israeli law)
    """
    try:
        logger.info(f"Scanning URL: {request.url}")
        
        # Import scanner (will create next)
        from .scanner import scan_url
        
        # Perform scan
        results = await scan_url(
            url=str(request.url),
            standard=request.standard,
            locale=request.locale
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Scan failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Scan failed. Please check the URL and try again.")


@app.post("/api/v1/scan/pdf")
async def scan_and_generate_pdf(request: ScanRequest):
    """
    Scan URL and return PDF report
    
    Note: This is a paid feature (₪99)
    For MVP, we'll return JSON and generate PDF on frontend
    """
    try:
        logger.info(f"Scanning URL for PDF: {request.url}")
        
        from .scanner import scan_url
        from .pdf_generator import generate_pdf_report
        
        # Perform scan
        results = await scan_url(
            url=str(request.url),
            standard=request.standard,
            locale=request.locale
        )
        
        # Generate PDF
        pdf_bytes = generate_pdf_report(results)
        
        # Sanitize scan_id for safe use in filename header
        safe_id = "".join(c for c in results.get("scan_id", "report") if c.isalnum() or c in "-_")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="accessibility-report-{safe_id}.pdf"'
            }
        )
        
    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail="PDF generation failed. Please try again.")


@app.post("/api/v1/send-report")
async def send_report_email(request: SendReportRequest):
    """
    Scan URL, generate PDF, and send it via email.
    All in-memory – no data is persisted.
    """
    try:
        logger.info(f"Generating and sending report for {request.url} to {request.email}")

        from .scanner import scan_url
        from .pdf_generator import generate_pdf_report

        # Scan
        results = await scan_url(url=str(request.url))

        # Generate PDF
        pdf_bytes = generate_pdf_report(results)

        # Send email
        _send_email(
            to_addr=str(request.email),
            subject=f"דוח נגישות – {request.url}",
            html_body=_build_email_html(results),
            pdf_bytes=pdf_bytes,
            pdf_filename=f"accessibility-report-{results['scan_id']}.pdf",
        )

        return {"status": "sent", "email": str(request.email)}

    except RuntimeError as e:
        # SMTP configuration errors — safe to expose
        logger.error(f"Send report config error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Send report failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send report. Please try again.")


def _esc(value) -> str:
    """Escape HTML special characters to prevent injection."""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _build_email_html(results: dict) -> str:
    """Simple HTML email body with visual hierarchy."""
    risk = results.get("risk", {})
    level = risk.get("level", "MEDIUM")
    level_he = _esc(risk.get("level_he", level))
    score = int(results.get("score", 0))
    summary = results.get("summary", {})
    safe_url = _esc(results.get("url", ""))

    risk_color = {
        "LOW": "#059669", "MEDIUM": "#d97706",
        "HIGH": "#dc2626", "CRITICAL": "#880000"
    }.get(level, "#d97706")

    return f"""\
<div dir="rtl" style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:24px">
  <h1 style="font-size:22px;color:#1a56db;border-bottom:2px solid #e5e7eb;padding-bottom:12px">
    דוח נגישות – {safe_url}
  </h1>

  <table style="width:100%;border-collapse:collapse;margin:16px 0">
    <tr>
      <td style="padding:12px;background:#f9fafb;border-radius:8px;text-align:center;width:50%">
        <div style="font-size:12px;color:#6b7280">ציון נגישות</div>
        <div style="font-size:32px;font-weight:bold;color:{risk_color}">{score}/100</div>
      </td>
      <td style="padding:12px;background:#f9fafb;border-radius:8px;text-align:center;width:50%">
        <div style="font-size:12px;color:#6b7280">רמת סיכון</div>
        <div style="font-size:20px;font-weight:bold;color:{risk_color}">{level_he}</div>
      </td>
    </tr>
  </table>

  <h2 style="font-size:16px;color:#374151">סיכום ממצאים</h2>
  <table style="width:100%;border-collapse:collapse;margin-bottom:16px">
    <tr style="background:#e5e7eb"><th style="padding:8px">סוג</th><th style="padding:8px">כמות</th></tr>
    <tr><td style="padding:8px;text-align:center">קריטי</td><td style="padding:8px;text-align:center;color:#dc2626;font-weight:bold">{summary.get('critical',0)}</td></tr>
    <tr style="background:#f9fafb"><td style="padding:8px;text-align:center">חמור</td><td style="padding:8px;text-align:center;color:#d97706;font-weight:bold">{summary.get('serious',0)}</td></tr>
    <tr><td style="padding:8px;text-align:center">בינוני</td><td style="padding:8px;text-align:center;color:#0891b2;font-weight:bold">{summary.get('moderate',0)}</td></tr>
    <tr style="background:#f9fafb"><td style="padding:8px;text-align:center">קל</td><td style="padding:8px;text-align:center;color:#6b7280;font-weight:bold">{summary.get('minor',0)}</td></tr>
  </table>

  <p style="font-size:13px;color:#6b7280;border-top:1px solid #e5e7eb;padding-top:12px">
    הדוח המלא מצורף כקובץ PDF.<br>
    מערכת זו אינה מהווה ייעוץ משפטי.
  </p>
</div>"""


def _send_email(
    to_addr: str,
    subject: str,
    html_body: str,
    pdf_bytes: bytes,
    pdf_filename: str,
):
    """Send email via SMTP with PDF attachment. In-memory only."""
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    from_addr = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_host or not smtp_user or not smtp_pass:
        raise RuntimeError(
            "SMTP not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASS env vars."
        )

    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # Attach PDF with safe ASCII filename
    attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    attachment.add_header(
        "Content-Disposition", "attachment", filename=pdf_filename
    )
    msg.attach(attachment)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)

    logger.info(f"Email sent to {to_addr}")


# ---- Payment Endpoints ---- #

@app.post("/api/v1/payment/create", response_model=PaymentResponse)
async def create_payment(request: CreatePaymentRequest):
    """
    Create a payment session. Returns a Meshulam payment page URL.
    In demo mode (no MESHULAM_PAGE_CODE), returns a mock URL that auto-succeeds.
    """
    try:
        logger.info(f"Creating payment session: url={request.url} email={request.email}")
        result = await payment_service.create_session(
            url=str(request.url),
            email=str(request.email),
            scan_id=request.scan_id,
        )
        return result
    except RuntimeError as e:
        logger.error(f"Payment creation failed: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Payment creation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create payment session.")


@app.get("/api/v1/payment/verify/{session_id}")
async def verify_payment(session_id: str):
    """
    Verify payment for a session. On success, generates PDF and sends email.
    Returns pdf_token for secure download.
    """
    try:
        result = await payment_service.verify_session(session_id)

        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail="Payment session not found.")

        # If payment just completed, generate PDF and send email
        if result["status"] == "completed" and result["pdf_token"]:
            session = payment_service._sessions.get(session_id)
            if session and not session.get("pdf_bytes"):
                try:
                    from .scanner import scan_url
                    from .pdf_generator import generate_pdf_report

                    scan_results = await scan_url(url=result["scan_url"])
                    pdf_bytes = generate_pdf_report(scan_results)
                    payment_service.store_pdf(session_id, pdf_bytes)

                    # Auto-send email with PDF
                    try:
                        _send_email(
                            to_addr=result["email"],
                            subject=f"דוח נגישות – {result['scan_url']}",
                            html_body=_build_email_html(scan_results),
                            pdf_bytes=pdf_bytes,
                            pdf_filename=f"accessibility-report-{scan_results.get('scan_id', 'report')}.pdf",
                        )
                        logger.info(f"Report emailed to {result['email']} for session {session_id}")
                    except Exception as email_err:
                        logger.error(f"Email send failed (payment still valid): {email_err}")

                except Exception as scan_err:
                    logger.error(f"PDF generation during verify failed: {scan_err}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Payment verify error: {e}")
        raise HTTPException(status_code=500, detail="Payment verification failed.")


@app.get("/api/v1/payment/download/{pdf_token}")
async def download_pdf_by_token(pdf_token: str):
    """
    Download PDF report using a one-time token from payment verification.
    Token expires after 30 minutes.
    """
    session = payment_service.get_session_by_token(pdf_token)
    if not session:
        raise HTTPException(status_code=404, detail="Invalid or expired download token.")

    pdf_bytes = session.get("pdf_bytes")
    if not pdf_bytes:
        # PDF not cached — regenerate
        try:
            from .scanner import scan_url
            from .pdf_generator import generate_pdf_report

            scan_results = await scan_url(url=session["url"])
            pdf_bytes = generate_pdf_report(scan_results)
            payment_service.store_pdf(session["session_id"], pdf_bytes)
        except Exception as e:
            logger.error(f"PDF regeneration failed: {e}")
            raise HTTPException(status_code=500, detail="PDF generation failed.")

    safe_id = "".join(
        c for c in session.get("scan_id", "report") if c.isalnum() or c in "-_"
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="accessibility-report-{safe_id}.pdf"'
        },
    )


@app.post("/api/v1/payment/webhook")
async def payment_webhook(request: Request):
    """
    Meshulam server-to-server payment notification.
    Updates session status when payment completes.
    """
    try:
        data = await request.json()
        logger.info(f"Payment webhook received: {data}")
        success = await payment_service.handle_webhook(data)
        return {"status": "ok", "processed": success}
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return {"status": "error", "processed": False}


@app.get("/api/v1/payment/status")
async def payment_system_status():
    """
    Check if the payment system is in demo mode or production.
    Useful for frontend to display demo warnings.
    """
    return {
        "demo_mode": payment_service.demo_mode,
        "amount": payment_service.amount,
        "currency": "ILS",
    }


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
