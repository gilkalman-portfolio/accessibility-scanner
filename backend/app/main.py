"""
Israeli Accessibility Scanner API
Main FastAPI application
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, HttpUrl
from typing import Optional, Literal
import logging

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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


class HealthResponse(BaseModel):
    status: str
    version: str
    coverage: dict


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
        raise HTTPException(status_code=500, detail=str(e))


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
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=accessibility-report-{results['scan_id']}.pdf"
            }
        )
        
    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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
