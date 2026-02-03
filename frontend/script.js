(() => {
  "use strict";

  // ---- Config ----
  const API_URL =
    window.location.hostname === "localhost"
      ? "http://localhost:8000"
      : (window.__API_URL__ || "");

  const ENDPOINT_SCAN = `${API_URL}/api/v1/scan`;
  const ENDPOINT_PDF = `${API_URL}/api/v1/scan/pdf`;
  const ENDPOINT_EMAIL = `${API_URL}/api/v1/send-report`;
  const ENDPOINT_PAYMENT_CREATE = `${API_URL}/api/v1/payment/create`;
  const ENDPOINT_PAYMENT_VERIFY = `${API_URL}/api/v1/payment/verify`;
  const ENDPOINT_PAYMENT_DOWNLOAD = `${API_URL}/api/v1/payment/download`;
  const ENDPOINT_PAYMENT_STATUS = `${API_URL}/api/v1/payment/status`;

  // ---- DOM refs ----
  const $ = (id) => document.getElementById(id);

  const els = {
    scanForm: $("scanForm"),
    urlInput: $("urlInput"),
    buttonText: $("buttonText"),
    buttonLoader: $("buttonLoader"),
    errorMessage: $("errorMessage"),

    results: $("results"),
    scannedUrl: $("scannedUrl"),

    scoreValue: $("scoreValue"),
    scoreCircle: $("scoreCircle"),
    scoreDesc: $("scoreDesc"),

    riskBlock: $("riskBlock"),
    riskBadge: $("riskBadge"),
    riskNote: $("riskNote"),

    criticalCount: $("criticalCount"),
    majorCount: $("majorCount"),
    moderateCount: $("moderateCount"),
    minorCount: $("minorCount"),

    // CTA + Payment elements
    ctaSection: $("ctaSection"),
    ctaCard: $("ctaCard"),
    ctaEmailForm: $("ctaEmailForm"),
    ctaEmailInput: $("ctaEmailInput"),
    ctaPurchaseButton: $("ctaPurchaseButton"),
    ctaButtonText: $("ctaButtonText"),
    ctaButtonLoader: $("ctaButtonLoader"),
    ctaError: $("ctaError"),
    launchDiscountBadge: $("launchDiscountBadge"),

    paymentProcessing: $("paymentProcessing"),
    paymentSuccessSection: $("paymentSuccessSection"),
    paymentSuccessEmail: $("paymentSuccessEmail"),
    paymentDownloadButton: $("paymentDownloadButton"),

    mobilePdfButton: $("mobilePdfButton"),
    mobileCta: $("mobileCta"),
    newScanButton: $("newScanButton"),
  };

  let lastScan = null;
  let currentPaymentSession = null;

  // ---- Helpers ----
  function setLoading(isLoading) {
    if (els.buttonText) els.buttonText.style.display = isLoading ? "none" : "";
    if (els.buttonLoader) els.buttonLoader.style.display = isLoading ? "inline-block" : "none";
    if (els.scanForm) {
      const btn = els.scanForm.querySelector('button[type="submit"]');
      if (btn) btn.disabled = isLoading;
    }
  }

  function setCtaLoading(isLoading) {
    if (els.ctaButtonText) els.ctaButtonText.style.display = isLoading ? "none" : "";
    if (els.ctaButtonLoader) els.ctaButtonLoader.style.display = isLoading ? "inline-block" : "none";
    if (els.ctaPurchaseButton) els.ctaPurchaseButton.disabled = isLoading;
  }

  function showError(msg) {
    if (!els.errorMessage) return;
    els.errorMessage.textContent = msg;
    els.errorMessage.style.display = "block";
  }

  function clearError() {
    if (!els.errorMessage) return;
    els.errorMessage.textContent = "";
    els.errorMessage.style.display = "none";
  }

  function showCtaError(msg) {
    const el = els.ctaError;
    if (!el) return;
    el.textContent = msg;
    el.style.display = "block";
  }

  function clearCtaError() {
    const el = els.ctaError;
    if (!el) return;
    el.textContent = "";
    el.style.display = "none";
  }

  function showResults() {
    if (!els.results) return;
    els.results.style.display = "block";
    els.results.scrollIntoView({ behavior: "smooth", block: "start" });
    if (els.mobileCta) els.mobileCta.style.display = "";
  }

  function hideResults() {
    if (!els.results) return;
    els.results.style.display = "none";
    if (els.mobileCta) els.mobileCta.style.display = "none";
    // Reset payment states
    showCtaCard();
  }

  function showCtaCard() {
    if (els.ctaCard) els.ctaCard.style.display = "";
    if (els.paymentProcessing) els.paymentProcessing.style.display = "none";
    if (els.paymentSuccessSection) els.paymentSuccessSection.style.display = "none";
  }

  function showPaymentProcessing() {
    if (els.ctaCard) els.ctaCard.style.display = "none";
    if (els.paymentProcessing) els.paymentProcessing.style.display = "";
    if (els.paymentSuccessSection) els.paymentSuccessSection.style.display = "none";
  }

  function showPaymentSuccess(email, pdfToken) {
    if (els.ctaCard) els.ctaCard.style.display = "none";
    if (els.paymentProcessing) els.paymentProcessing.style.display = "none";
    if (els.paymentSuccessSection) {
      els.paymentSuccessSection.style.display = "";
      if (els.paymentSuccessEmail) els.paymentSuccessEmail.textContent = email;
    }
    // Hide mobile CTA after successful payment
    if (els.mobileCta) els.mobileCta.style.display = "none";

    // Wire download button
    if (els.paymentDownloadButton && pdfToken) {
      els.paymentDownloadButton.onclick = () => downloadPdfByToken(pdfToken);
    }

    // Scroll to success
    if (els.paymentSuccessSection) {
      els.paymentSuccessSection.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  function normalizeUrl(raw) {
    const s = (raw || "").trim();
    if (!s) return "";
    if (/^https?:\/\//i.test(s)) return s;
    return `https://${s}`;
  }

  // ---- Exposure / score labels ----
  function exposureLabel(level) {
    const v = (level || "").toUpperCase();
    if (v === "CRITICAL") return "גבוהה";
    if (v === "HIGH") return "גבוהה";
    if (v === "MEDIUM") return "בינונית";
    if (v === "LOW") return "נמוכה";
    return "לא ידועה";
  }

  function exposureExplanation(key) {
    switch ((key || "").toUpperCase()) {
      case "RISK_CRITICAL":
        return "נמצאו בעיות קריטיות רבות. מומלץ לטפל בהן בדחיפות.";
      case "RISK_HIGH":
        return "נמצאו בעיות חמורות. מומלץ לטפל בהן בהקדם כדי לצמצם חשיפה.";
      case "RISK_MEDIUM":
        return "נמצאו בעיות בינוניות. כדאי לטפל בהן כדי לשפר את הנגישות.";
      case "RISK_LOW":
        return "נמצאו מעט בעיות. האתר במצב טוב יחסית.";
      default:
        return "התרעה טכנולוגית בלבד, אינה מהווה ייעוץ משפטי.";
    }
  }

  function scoreDescription(score) {
    if (score >= 80) return "מצב נגישות טוב";
    if (score >= 60) return "נדרשים שיפורים";
    if (score >= 40) return "מצב נגישות בינוני";
    return "נדרשת פעולה מיידית";
  }

  function scoreColor(score) {
    if (score >= 80) return "#059669";
    if (score >= 60) return "#d97706";
    return "#dc2626";
  }

  // ---- Score ring animation ----
  function animateScoreRing(score) {
    const circle = els.scoreCircle;
    if (!circle) return;

    const circumference = 2 * Math.PI * 52;
    const offset = circumference - (score / 100) * circumference;

    circle.style.stroke = scoreColor(score);
    circle.style.strokeDashoffset = String(circumference);
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        circle.style.strokeDashoffset = String(offset);
      });
    });
  }

  // ---- API ----
  async function postJson(url, payload, timeoutMs = 60000) {
    const controller = new AbortController();
    const t = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      const ct = res.headers.get("content-type") || "";
      if (!res.ok) {
        let errMsg = `שגיאה מהשרת (HTTP ${res.status})`;
        try {
          if (ct.includes("application/json")) {
            const j = await res.json();
            errMsg = j?.detail || j?.error || j?.message || errMsg;
          } else {
            const txt = await res.text();
            if (txt) errMsg = txt.slice(0, 300);
          }
        } catch (_) {}
        throw new Error(errMsg);
      }

      if (ct.includes("application/json")) return await res.json();
      return await res.text();
    } catch (e) {
      if (e.name === "AbortError") {
        throw new Error("הפעולה התארכה יותר מדי (timeout). נסה שוב.");
      }
      throw e;
    } finally {
      clearTimeout(t);
    }
  }

  async function getJson(url, timeoutMs = 90000) {
    const controller = new AbortController();
    const t = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const res = await fetch(url, { signal: controller.signal });
      if (!res.ok) {
        let errMsg = `שגיאה מהשרת (HTTP ${res.status})`;
        try {
          const j = await res.json();
          errMsg = j?.detail || j?.error || j?.message || errMsg;
        } catch (_) {}
        throw new Error(errMsg);
      }
      return await res.json();
    } catch (e) {
      if (e.name === "AbortError") {
        throw new Error("הפעולה התארכה יותר מדי (timeout). נסה שוב.");
      }
      throw e;
    } finally {
      clearTimeout(t);
    }
  }

  // ---- Render results ----
  function renderResults(scan) {
    lastScan = scan;

    if (els.scannedUrl) els.scannedUrl.textContent = scan.url || "";

    const score = Number(scan.score || 0);
    if (els.scoreValue) els.scoreValue.textContent = String(score);
    if (els.scoreDesc) els.scoreDesc.textContent = scoreDescription(score);
    animateScoreRing(score);

    const risk = scan.risk || {};
    const level = (risk.level || "UNKNOWN").toUpperCase();
    const explanationKey = risk.explanation_key || "";

    if (els.riskBadge) els.riskBadge.textContent = exposureLabel(level);
    if (els.riskNote) els.riskNote.textContent = exposureExplanation(explanationKey);

    if (els.riskBlock) {
      els.riskBlock.className = "risk-block";
      if (level === "LOW") els.riskBlock.classList.add("risk-low");
      else if (level === "MEDIUM") els.riskBlock.classList.add("risk-medium");
      else if (level === "HIGH") els.riskBlock.classList.add("risk-high");
      else if (level === "CRITICAL") els.riskBlock.classList.add("risk-critical");
    }

    const summary = scan.summary || {};
    if (els.criticalCount) els.criticalCount.textContent = String(summary.critical || 0);
    if (els.majorCount) els.majorCount.textContent = String(summary.serious || 0);
    if (els.moderateCount) els.moderateCount.textContent = String(summary.moderate || 0);
    if (els.minorCount) els.minorCount.textContent = String(summary.minor || 0);

    // Reset CTA to default state
    showCtaCard();

    showResults();
  }

  // ---- Payment Flow ----
  async function onPurchaseReport(e) {
    e.preventDefault();
    clearCtaError();

    const email = els.ctaEmailInput ? els.ctaEmailInput.value.trim() : "";
    if (!email) {
      showCtaError("נא להזין כתובת אימייל.");
      return;
    }
    if (!lastScan) {
      showCtaError("אין תוצאות סריקה. בצע סריקה קודם.");
      return;
    }

    setCtaLoading(true);

    try {
      const response = await postJson(ENDPOINT_PAYMENT_CREATE, {
        url: lastScan.url,
        email: email,
        scan_id: lastScan.scan_id || "",
      });

      currentPaymentSession = {
        session_id: response.session_id,
        email: email,
        scan_url: lastScan.url,
      };

      // Store session in localStorage for the return page
      localStorage.setItem("payment_session", JSON.stringify(currentPaymentSession));

      // Show processing state
      showPaymentProcessing();

      // Redirect to payment page (Meshulam or demo)
      window.location.href = response.payment_url;

    } catch (err) {
      setCtaLoading(false);
      showCtaCard();
      showCtaError(err?.message || "יצירת תשלום נכשלה. נסה שוב.");
    }
  }

  async function downloadPdfByToken(token) {
    try {
      const res = await fetch(`${ENDPOINT_PAYMENT_DOWNLOAD}/${token}`, {
        method: "GET",
      });

      if (!res.ok) {
        throw new Error("הורדת הדוח נכשלה. ייתכן שהקישור פג תוקף.");
      }

      const blob = await res.blob();
      const a = document.createElement("a");
      const url = URL.createObjectURL(blob);
      a.href = url;
      a.download = "accessibility-report.pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err?.message || "הורדה נכשלה. נסה שוב.");
    }
  }

  // Scroll to CTA section (for mobile sticky button)
  function scrollToCta() {
    if (els.ctaSection) {
      els.ctaSection.scrollIntoView({ behavior: "smooth", block: "center" });
      // Focus the email input for accessibility
      setTimeout(() => {
        if (els.ctaEmailInput) els.ctaEmailInput.focus();
      }, 500);
    }
  }

  // ---- Events ----
  async function onSubmit(e) {
    e.preventDefault();
    clearError();
    hideResults();

    const raw = els.urlInput ? els.urlInput.value : "";
    const url = normalizeUrl(raw);

    if (!url) {
      showError("נא להזין כתובת אתר (URL).");
      return;
    }

    setLoading(true);
    try {
      const result = await postJson(ENDPOINT_SCAN, { url });
      renderResults(result);
    } catch (err) {
      showError(err?.message || "שגיאה לא ידועה בעת הסריקה.");
    } finally {
      setLoading(false);
    }
  }

  function onScanAnother() {
    clearError();
    hideResults();
    if (els.urlInput) {
      els.urlInput.value = "";
      els.urlInput.focus();
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // ---- Check for payment return on page load ----
  function checkPaymentReturn() {
    const params = new URLSearchParams(window.location.search);
    const cancelled = params.get("payment");

    if (cancelled === "cancelled") {
      // User cancelled payment — show message
      showError("התשלום בוטל. תוכל לנסות שוב.");
      // Clean URL
      window.history.replaceState({}, "", window.location.pathname);
    }
  }

  // ---- Bind ----
  function bind() {
    if (els.scanForm) els.scanForm.addEventListener("submit", onSubmit);

    // CTA purchase form
    if (els.ctaEmailForm) els.ctaEmailForm.addEventListener("submit", onPurchaseReport);

    // Mobile sticky CTA — scroll to CTA section instead of direct download
    if (els.mobilePdfButton) els.mobilePdfButton.addEventListener("click", scrollToCta);

    if (els.newScanButton) els.newScanButton.addEventListener("click", onScanAnother);
  }

  // Boot
  bind();
  hideResults();
  checkPaymentReturn();
})();
