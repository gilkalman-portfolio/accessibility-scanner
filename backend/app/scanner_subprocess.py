"""
Subprocess scanner - runs Playwright in isolation to avoid asyncio issues
Accessibility Scanner v1.1 - Risk Assessment Product
"""

import sys
import json
from playwright.sync_api import sync_playwright
import uuid
from datetime import datetime


# Risk level enum values (internal)
RISK_LOW = "LOW"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"
RISK_CRITICAL = "CRITICAL"


def scan_url_sync(url: str, standard: str = "IL_5568", locale: str = "he") -> dict:
    """
    Main scanning function (runs in subprocess)
    Returns risk assessment focused response (v1.1)
    """
    scan_id = f"scan_{uuid.uuid4().hex[:12]}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Use domcontentloaded instead of networkidle for faster, more reliable loading
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            # Wait a bit more for dynamic content
            page.wait_for_timeout(2000)

            # Run axe-core
            page.add_script_tag(url="https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.8.3/axe.min.js")
            axe_results = page.evaluate("""
                async () => {
                    const results = await axe.run({
                        runOnly: {
                            type: 'tag',
                            values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']
                        }
                    });
                    return results;
                }
            """)

            # Run Playwright checks
            playwright_checks = []

            # Check keyboard navigation (keyboard reachability)
            interactive_count = page.evaluate("""
                () => document.querySelectorAll('button, a, input, select, textarea, [tabindex]').length
            """)
            focusable_count = page.evaluate("""
                () => {
                    let count = 0;
                    document.querySelectorAll(
                        'button:not([disabled]), a[href], input:not([disabled]), ' +
                        'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
                    ).forEach(el => {
                        const style = window.getComputedStyle(el);
                        if (style.display !== 'none' && style.visibility !== 'hidden') count++;
                    });
                    return count;
                }
            """)
            keyboard_issue = interactive_count > 0 and focusable_count < interactive_count * 0.9
            if keyboard_issue:
                playwright_checks.append({
                    "check_key": "KEYBOARD_ACCESS",
                    "severity": "critical",
                    "nodes_count": interactive_count - focusable_count
                })

            # Check skip links (skip-link presence)
            has_skip_link = page.evaluate("""
                () => {
                    for (let link of document.querySelectorAll('a[href^="#"]')) {
                        const text = link.textContent.toLowerCase();
                        if (text.includes('skip') || text.includes('דלג') || text.includes('main') || text.includes('תוכן'))
                            return true;
                    }
                    return false;
                }
            """)
            if not has_skip_link:
                playwright_checks.append({
                    "check_key": "SKIP_LINK",
                    "severity": "moderate",
                    "nodes_count": 1
                })

            # Check focus visibility
            has_focus_styles = page.evaluate("""
                () => {
                    const styles = document.styleSheets;
                    for (let sheet of styles) {
                        try {
                            for (let rule of sheet.cssRules || []) {
                                if (rule.selectorText && rule.selectorText.includes(':focus')) {
                                    return true;
                                }
                            }
                        } catch (e) {}
                    }
                    return false;
                }
            """)
            if not has_focus_styles:
                playwright_checks.append({
                    "check_key": "FOCUS_VISIBLE",
                    "severity": "serious",
                    "nodes_count": 1
                })

            # Check basic form error exposure
            forms = page.evaluate("""
                () => {
                    const forms = document.querySelectorAll('form');
                    let issues = 0;
                    forms.forEach(form => {
                        const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
                        inputs.forEach(input => {
                            const hasAriaDescribedby = input.hasAttribute('aria-describedby');
                            const hasAriaErrormessage = input.hasAttribute('aria-errormessage');
                            if (!hasAriaDescribedby && !hasAriaErrormessage) {
                                issues++;
                            }
                        });
                    });
                    return issues;
                }
            """)
            if forms > 0:
                playwright_checks.append({
                    "check_key": "FORM_ERRORS",
                    "severity": "moderate",
                    "nodes_count": forms
                })

            # Calculate score
            score = 100
            for v in axe_results.get("violations", []):
                impact = v.get("impact", "moderate")
                nodes = len(v.get("nodes", []))
                weights = {"critical": 10, "serious": 5, "moderate": 2, "minor": 1}
                score -= weights.get(impact, 2) * min(nodes, 5)
            for c in playwright_checks:
                weights = {"critical": 15, "serious": 10, "moderate": 5, "minor": 2}
                score -= weights.get(c.get("severity", "moderate"), 5)
            score = max(0, min(100, score))

            # Count by severity
            def count_severity(sev):
                cnt = sum(len(v.get("nodes", [])) for v in axe_results.get("violations", []) if v.get("impact") == sev)
                cnt += sum(c.get("nodes_count", 1) for c in playwright_checks if c.get("severity") == sev)
                return cnt

            critical = count_severity("critical")
            serious = count_severity("serious")
            moderate = count_severity("moderate")
            minor = count_severity("minor")
            total = critical + serious + moderate + minor

            # Calculate risk level (v1.1 risk model)
            # Risk Calculation:
            # if critical_issues >= 5: CRITICAL
            # elif critical_issues >= 3 or score < 40: HIGH
            # elif score < 70: MEDIUM
            # else: LOW
            if critical >= 5:
                risk_level = RISK_CRITICAL
                risk_explanation_key = "RISK_CRITICAL"
            elif critical >= 3 or score < 40:
                risk_level = RISK_HIGH
                risk_explanation_key = "RISK_HIGH"
            elif score < 70:
                risk_level = RISK_MEDIUM
                risk_explanation_key = "RISK_MEDIUM"
            else:
                risk_level = RISK_LOW
                risk_explanation_key = "RISK_LOW"

            # Build checked_keys from what we actually checked
            checked_keys = ["ALT_MISSING", "COLOR_CONTRAST", "ARIA", "FORM_LABELS"]
            if keyboard_issue or focusable_count > 0:
                checked_keys.append("KEYBOARD_ACCESS")
            if not has_skip_link or has_skip_link:
                # We always check for skip links
                pass
            checked_keys.append("FOCUS_VISIBLE")

            # Return v1.1 API response format
            return {
                "scan_id": scan_id,
                "url": url,
                "timestamp": datetime.utcnow().isoformat() + "Z",

                "score": score,

                "risk": {
                    "level": risk_level,
                    "explanation_key": risk_explanation_key
                },

                "summary": {
                    "total": total,
                    "critical": critical,
                    "serious": serious,
                    "moderate": moderate,
                    "minor": minor
                },

                "coverage": {
                    "automated_estimate": 0.75,
                    "checked_keys": checked_keys,
                    "manual_required": True
                },

                "next_action": "DOWNLOAD_REPORT"
            }

        finally:
            browser.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "URL_REQUIRED", "error_key": "INVALID_URL"}))
        sys.exit(1)

    url = sys.argv[1]
    standard = sys.argv[2] if len(sys.argv) > 2 else "IL_5568"
    locale = sys.argv[3] if len(sys.argv) > 3 else "he"

    try:
        result = scan_url_sync(url, standard, locale)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        error_msg = str(e)
        # Map errors to keys (frontend will display Hebrew)
        if "Timeout" in error_msg:
            error_key = "TIMEOUT"
        elif "net::ERR_BLOCKED" in error_msg or "403" in error_msg:
            error_key = "BLOCKED"
        elif "net::ERR" in error_msg:
            error_key = "INVALID_URL"
        else:
            error_key = "PARTIAL_SCAN"
        print(json.dumps({"error": error_msg, "error_key": error_key}, ensure_ascii=False))
        sys.exit(1)
