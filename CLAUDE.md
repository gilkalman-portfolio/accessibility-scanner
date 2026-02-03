# Accessibility Scanner – Project Documentation

> **Purpose**: Complete reference for AI agents (Claude) resuming work on this project.
> Read this file first before making any changes.

---

## 1. Project Overview

**Israeli Accessibility Scanner** – a full-stack web app that scans websites for accessibility compliance per **Israeli Standard 5568** and **WCAG 2.2 AA**. It evaluates legal exposure risk for accessibility lawsuits under Israeli law.

| Component | Stack | Hosted On | URL |
|-----------|-------|-----------|-----|
| Backend API | Python 3.11 / FastAPI / Playwright / WeasyPrint | Railway.app | `https://truthful-simplicity-production.up.railway.app` |
| Frontend | Static HTML / CSS / JS (vanilla, no framework) | Vercel | `https://frontend-sooty-omega-76.vercel.app` |

**Language**: Hebrew (RTL). All user-facing text is in Hebrew. Code/comments are in English.

---

## 2. Repository Structure

```
accessibility-scanner/
├── railway.json                  # Root – tells Railway to use backend/Dockerfile
├── .gitignore
├── CLAUDE.md                     # THIS FILE
│
├── backend/
│   ├── Dockerfile                # Playwright + WeasyPrint image
│   ├── requirements.txt          # Python deps (fastapi, playwright, weasyprint, etc.)
│   ├── railway.json              # Railway service config (auto-deploy, health check)
│   ├── .env                      # Local secrets (gitignored)
│   ├── .env.example              # Template for .env
│   └── app/
│       ├── __init__.py
│       ├── main.py               # FastAPI app, routes, CORS, email logic
│       ├── scanner.py            # Core async scanner (axe-core + Playwright checks)
│       ├── scanner_subprocess.py # Sync fallback scanner (v1.1, CLI-capable)
│       └── pdf_generator.py      # WeasyPrint Hebrew PDF report (v3.1)
│
├── frontend/
│   ├── index.html                # Main page (RTL Hebrew, single-page)
│   ├── script.js                 # IIFE – API calls, UI rendering, score animation
│   ├── style.css                 # RTL design system v2.1
│   ├── vercel.json               # Vercel config (no build, security headers)
│   ├── manifest.json             # PWA manifest
│   ├── logo.svg                  # Full logo
│   ├── logo-compact.svg          # Compact logo
│   └── icons/                    # PWA icons (192px, 512px)
```

---

## 3. API Endpoints

Base URL: `https://truthful-simplicity-production.up.railway.app`

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/` | Health check + coverage info | None |
| GET | `/health` | Simple health ping (used by Railway) | None |
| GET | `/docs` | Swagger UI | None |
| POST | `/api/v1/scan` | Scan URL, return JSON report | None |
| POST | `/api/v1/scan/pdf` | Scan URL, return PDF bytes | None (paid feature) |
| POST | `/api/v1/send-report` | Scan + PDF + email delivery | None |

### Request Models

```python
# POST /api/v1/scan and /api/v1/scan/pdf
{
    "url": "https://example.com",        # Required
    "standard": "IL_5568",               # or "WCAG_2_2_AA", default IL_5568
    "locale": "he"                       # or "en", default "he"
}

# POST /api/v1/send-report
{
    "url": "https://example.com",
    "scan_id": "scan_abc123",            # Optional
    "email": "user@example.com"          # Required
}
```

### Scan Response Structure

```json
{
    "scan_id": "scan_<8-char-hex>",
    "url": "https://...",
    "timestamp": "ISO 8601",
    "score": 0-100,
    "standard": "IL_5568",
    "locale": "he",
    "coverage": { "axe_core": "57%", "playwright_checks": "20%", "total_automated": "77%" },
    "summary": { "total": N, "critical": N, "serious": N, "moderate": N, "minor": N },
    "issues": {
        "axe_core": [ { "id", "impact", "description", "help_url", "nodes", "hebrew_title", "fix_he" } ],
        "playwright": [ { "id", "impact", "description", "help_url", "fix_he" } ]
    },
    "risk": {
        "level": "LOW|MEDIUM|HIGH|CRITICAL",
        "level_he": "נמוכה|בינונית|גבוהה|קריטית",
        "explanation_key": "LOW_RISK|MEDIUM_RISK|HIGH_RISK|CRITICAL_RISK",
        "estimated_fine": "₪0–25,000 | ₪25–75,000 | ₪50–150,000 | ₪75–150,000",
        "recommendation_he": "..."
    },
    "what_we_checked": [...],
    "next_steps": [...]
}
```

---

## 4. Scanning Logic (`scanner.py`)

Two scanning layers run in parallel:

### Layer 1: axe-core (57% coverage)
- Injects axe-core 4.8.3 via CDN into the target page
- Tests against: WCAG 2A, 2AA, 2.1A, 2.1AA, 2.2AA
- Returns violations with impact levels (critical/serious/moderate/minor)

### Layer 2: Playwright Custom Checks (20% coverage)
- **Keyboard navigation** (WCAG 2.1.1) – Tab through elements, check focus
- **Focus visibility** (WCAG 2.4.7) – Focus indicator detection
- **Skip links** (WCAG 2.4.1) – Skip-to-content link check
- **Form error handling** (WCAG 3.3.1) – Form validation feedback
- **Accessibility statement** (IL 5568) – Statement page detection

### Score Calculation
```
Start: 100
- Critical issues:  -10 each (max 5 counted)
- Serious issues:   -5 each
- Moderate issues:  -2 each
- Minor issues:     -1 each
Result: clamped to 0-100
```

### Legal Risk Assessment
```
CRITICAL: critical >= 5                → ₪75-150K
HIGH:     critical >= 3 OR score < 40  → ₪50-150K
MEDIUM:   score < 70                   → ₪25-75K
LOW:      else                         → ₪0-25K
```

---

## 5. PDF Generator (`pdf_generator.py`)

- **Engine**: WeasyPrint (replaced ReportLab for better RTL/Hebrew support)
- **Font**: DejaVu Sans (system-installed in Docker), Noto Sans Hebrew fallback
- **Output**: Raw PDF bytes via `generate_pdf_report(results: dict) -> bytes`

### PDF Sections (8 pages+)
1. Cover page (logo, score, risk level, metadata)
2. Legal overview (Israeli law reference)
3. Issues summary table
4. Detailed issues (sorted by severity, with fix instructions)
5. Standards checklist (automated vs manual)
6. Recommendations (prioritized by risk level)
7. Resources (external links)
8. Disclaimer & signature

---

## 6. Frontend Architecture

### Tech
- **No framework** – vanilla HTML/CSS/JS
- **Font**: Google Fonts – Heebo (Hebrew)
- **Direction**: RTL throughout
- **PWA-ready**: manifest.json + icons

### Key Design Elements
- **Score Ring**: SVG circle, animated stroke-dashoffset (1.4s cubic-bezier)
- **Risk Badge**: Color-coded with severity glow, pulse animation on CRITICAL
- **Issue Cards**: 4 cards (critical/serious/moderate/minor) with color-coded SVG icons
- **Mobile Sticky CTA**: Fixed bottom bar on mobile (≤768px), frosted glass backdrop
- **FAQ**: 6 expandable `<details>` elements
- **Section Dividers**: border-top/bottom between major sections

### script.js Structure (IIFE)
```javascript
// API config
const API_URL = window.__API_URL__ || "";
const ENDPOINT_SCAN = `${API_URL}/api/v1/scan`;
const ENDPOINT_PDF  = `${API_URL}/api/v1/scan/pdf`;
const ENDPOINT_EMAIL = `${API_URL}/api/v1/send-report`;

// Key functions
normalizeUrl(raw)           // Adds https:// if missing
exposureLabel(level)        // Risk level → Hebrew label
exposureExplanation(key)    // Risk explanation key → Hebrew text
scoreDescription(score)     // Score → Hebrew status text
scoreColor(score)           // Score → RGB color
animateScoreRing(score)     // SVG animation
postJson(url, payload)      // Fetch wrapper with 60s timeout
renderResults(scan)         // Populate all result DOM elements
downloadPdf(scan)           // Fetch PDF blob → browser download
sendReportEmail(email)      // POST to send-report endpoint
```

### CSS Design System (style.css v2.1)
```css
/* Key variables */
--section-gap: 40px;

/* Breakpoints */
@media (max-width: 768px)   /* Tablet */
@media (max-width: 480px)   /* Mobile */

/* Accessibility */
@media (prefers-reduced-motion: reduce)
@media (prefers-contrast: high)
```

---

## 7. Deployment

### Backend → Railway.app

**How it works**: GitHub push to `main` → Railway auto-deploys via Dockerfile.

**Config chain**:
1. `railway.json` (repo root) → tells Railway: use `backend/Dockerfile`
2. `backend/Dockerfile` → builds Playwright + WeasyPrint image
3. COPY paths are repo-root-relative: `COPY backend/requirements.txt .` and `COPY backend/app ./app`

**Dockerfile base image**: `mcr.microsoft.com/playwright/python:v1.58.0-jammy`

**System deps installed**: pango, cairo, gdk-pixbuf, fonts (for WeasyPrint Hebrew PDF)

**Health check**: `GET /health` (300s timeout)

**Important**: If Dockerfile COPY paths break, it's because the build context is the repo root (not `backend/`). Always use `backend/` prefix in COPY commands.

### Frontend → Vercel

**How it works**: GitHub push to `main` → Vercel auto-deploys the `frontend/` directory.

**Config**:
- Root Directory: `frontend` (set in Vercel project settings)
- No build command (static files served as-is)
- `vercel.json` adds security headers + SPA rewrite rules

**Backend URL**: Hardcoded in `index.html`:
```html
<script>window.__API_URL__ = "https://truthful-simplicity-production.up.railway.app";</script>
```

---

## 8. CORS Configuration

In `backend/app/main.py`:

```python
# Allowed origins (hardcoded defaults + env override)
_allowed_origins = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:8888",
    "https://frontend-sooty-omega-76.vercel.app",
]
# Plus regex for ALL Vercel preview URLs:
_allow_origin_regex = r"https://.*\.vercel\.app"
```

**Override**: Set `ALLOWED_ORIGINS` env var (comma-separated) on Railway to customize.

---

## 9. Environment Variables

### Backend (Railway / .env)

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `ALLOWED_ORIGINS` | No | localhost + Vercel URL | CORS origins (comma-separated) |
| `SMTP_HOST` | For email | — | SMTP server (e.g. smtp.gmail.com) |
| `SMTP_PORT` | For email | 587 | SMTP port |
| `SMTP_USER` | For email | — | SMTP username |
| `SMTP_PASS` | For email | — | SMTP password/app-password |
| `SMTP_FROM` | No | SMTP_USER | From address |
| `API_HOST` | No | 0.0.0.0 | Bind host |
| `API_PORT` | No | 8000 | Bind port |

### Frontend

No env vars. Backend URL is set via `<script>` tag in `index.html`.

---

## 10. Hebrew Language Notes

### UI Framing
- **Not "legal risk"** → Use **"exposure to lawsuits"** (חשיפה לתביעות)
- **Not ₪ fines in UI** → Fine estimates only appear in PDF report
- Functions are named `exposureLabel()` / `exposureExplanation()` (not risk*)
- CTA says "רכוש דוח PDF" (Purchase PDF report), not legal advice

### Key Hebrew Terms
| Hebrew | English | Context |
|--------|---------|---------|
| בדוק נגישות | Check Accessibility | Scan button |
| ציון נגישות | Accessibility Score | Score label |
| חשיפה לתביעות | Exposure to Lawsuits | Risk label (UI) |
| רמת חשיפה | Exposure Level | Risk badge |
| קריטי / חמור / בינוני / קל | Critical / Serious / Moderate / Minor | Severity levels |
| דוח נגישות | Accessibility Report | PDF title |
| תקן ישראלי 5568 | Israeli Standard 5568 | Compliance standard |

---

## 11. Common Issues & Fixes

### "Script start.sh not found" on Railway
**Cause**: Railway can't find build instructions.
**Fix**: Ensure `railway.json` exists at repo root with `dockerfilePath: "backend/Dockerfile"`.

### CORS 400 on OPTIONS preflight
**Cause**: Frontend origin not in allowed CORS origins.
**Fix**: Add the Vercel URL to `_allowed_origins` in `main.py`, or set `ALLOWED_ORIGINS` env var on Railway.

### WeasyPrint Hebrew text not rendering
**Cause**: Missing system fonts in Docker.
**Fix**: Dockerfile installs `fonts-dejavu-core` and `fonts-noto`. The PDF uses `font-family: 'DejaVu Sans'`.

### Dockerfile COPY fails
**Cause**: Build context is repo root, not `backend/`.
**Fix**: Use `COPY backend/requirements.txt .` (not `COPY requirements.txt .`).

### Frontend not updating after push
**Cause**: Vercel root directory not set to `frontend`.
**Fix**: In Vercel project settings → General → Root Directory → set to `frontend`.

### PDF download times out
**Cause**: Scan + PDF generation can take 30-90 seconds.
**Fix**: Frontend uses 90s timeout for PDF endpoint. Railway health check timeout is 300s.

---

## 12. Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.1.0 | Jan 2025 | Reframed "legal risk" → "exposure to lawsuits", removed ₪ fines from UI, mobile sticky CTA, design polish |
| 2.0.0 | Jan 2025 | WeasyPrint PDF (replaced ReportLab), logo SVG, professional PDF design |
| 1.1.0 | Jan 2025 | Subprocess scanner, Docker deployment, Railway + Vercel setup |
| 1.0.0 | Jan 2025 | Initial release – axe-core + Playwright scanner, basic PDF |

---

## 13. Git & Branching

- **Main branch**: `main` (production)
- **Remote**: `https://github.com/gilkalman-portfolio/accessibility-scanner.git`
- Both Railway and Vercel auto-deploy from `main` on push
- Commit messages: English, conventional-ish format

---

## 14. Quick Start (Local Development)

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
playwright install chromium
cp .env.example .env             # Edit with your values
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
# Any static server works:
python -m http.server 8888
# Then open http://localhost:8888
```

Make sure `window.__API_URL__` in `index.html` points to `http://localhost:8000` for local dev (or is empty string to use relative paths).
