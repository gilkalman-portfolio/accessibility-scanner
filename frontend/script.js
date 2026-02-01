(() => {
  "use strict";

  // ---- Config ----
  const API_URL =
    window.location.hostname === "localhost"
      ? "http://localhost:8000"
      : "";

  const ENDPOINT_SCAN = `${API_URL}/api/v1/scan`;
  const ENDPOINT_PDF = `${API_URL}/api/v1/scan/pdf`;
  const ENDPOINT_EMAIL = `${API_URL}/api/v1/send-report`;

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
    riskFine: $("riskFine"),
    riskNote: $("riskNote"),

    criticalCount: $("criticalCount"),
    majorCount: $("majorCount"),
    moderateCount: $("moderateCount"),
    minorCount: $("minorCount"),

    downloadPdfButton: $("downloadPdfButton"),
    newScanButton: $("newScanButton"),

    emailSection: $("emailSection"),
    emailForm: $("emailForm"),
    emailInput: $("emailInput"),
    sendEmailButton: $("sendEmailButton"),
    emailStatus: $("emailStatus"),
  };

  let lastScan = null;

  // ---- Helpers ----
  function setLoading(isLoading) {
    if (els.buttonText) els.buttonText.style.display = isLoading ? "none" : "";
    if (els.buttonLoader) els.buttonLoader.style.display = isLoading ? "inline-block" : "none";
    if (els.scanForm) {
      const btn = els.scanForm.querySelector('button[type="submit"]');
      if (btn) btn.disabled = isLoading;
    }
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

  function showResults() {
    if (!els.results) return;
    els.results.style.display = "block";
    els.results.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function hideResults() {
    if (!els.results) return;
    els.results.style.display = "none";
    if (els.emailSection) els.emailSection.style.display = "none";
  }

  function normalizeUrl(raw) {
    const s = (raw || "").trim();
    if (!s) return "";
    if (/^https?:\/\//i.test(s)) return s;
    return `https://${s}`;
  }

  // ---- Risk / score labels ----
  function riskLabel(level) {
    const v = (level || "").toUpperCase();
    if (v === "CRITICAL") return "קריטית";
    if (v === "HIGH") return "גבוהה";
    if (v === "MEDIUM") return "בינונית";
    if (v === "LOW") return "נמוכה";
    return "לא ידועה";
  }

  function riskExplanation(key) {
    switch ((key || "").toUpperCase()) {
      case "RISK_CRITICAL":
        return "נמצאו ליקויים מהותיים. זהו דוח אוטומטי ואינו ייעוץ משפטי.";
      case "RISK_HIGH":
        return "נמצאו ליקויים משמעותיים. זהו דוח אוטומטי ואינו ייעוץ משפטי.";
      case "RISK_MEDIUM":
        return "נמצאו ליקויים בינוניים. זהו דוח אוטומטי ואינו ייעוץ משפטי.";
      case "RISK_LOW":
        return "נמצאו ליקויים מעטים יחסית. זהו דוח אוטומטי ואינו ייעוץ משפטי.";
      default:
        return "זהו דוח אוטומטי ואינו ייעוץ משפטי.";
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

    const circumference = 2 * Math.PI * 52; // r=52
    const offset = circumference - (score / 100) * circumference;

    circle.style.stroke = scoreColor(score);
    // Trigger reflow for animation
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
        throw new Error("הסריקה התארכה יותר מדי (timeout). נסה שוב או נסה דף אחר באתר.");
      }
      throw e;
    } finally {
      clearTimeout(t);
    }
  }

  // ---- Render results ----
  function renderResults(scan) {
    lastScan = scan;

    // URL
    if (els.scannedUrl) els.scannedUrl.textContent = scan.url || "";

    // Score
    const score = Number(scan.score || 0);
    if (els.scoreValue) els.scoreValue.textContent = String(score);
    if (els.scoreDesc) els.scoreDesc.textContent = scoreDescription(score);
    animateScoreRing(score);

    // Risk
    const risk = scan.risk || {};
    const level = (risk.level || "UNKNOWN").toUpperCase();
    const explanationKey = risk.explanation_key || "";

    if (els.riskBadge) els.riskBadge.textContent = riskLabel(level);
    if (els.riskNote) els.riskNote.textContent = riskExplanation(explanationKey);
    if (els.riskFine && risk.estimated_fine) {
      els.riskFine.textContent = `טווח קנסות משוער: ${risk.estimated_fine}`;
    }

    // Risk block styling
    if (els.riskBlock) {
      els.riskBlock.className = "risk-block";
      if (level === "LOW") els.riskBlock.classList.add("risk-low");
      else if (level === "MEDIUM") els.riskBlock.classList.add("risk-medium");
      else if (level === "HIGH") els.riskBlock.classList.add("risk-high");
      else if (level === "CRITICAL") els.riskBlock.classList.add("risk-critical");
    }

    // Issues summary
    const summary = scan.summary || {};
    if (els.criticalCount) els.criticalCount.textContent = String(summary.critical || 0);
    if (els.majorCount) els.majorCount.textContent = String(summary.serious || 0);
    if (els.moderateCount) els.moderateCount.textContent = String(summary.moderate || 0);
    if (els.minorCount) els.minorCount.textContent = String(summary.minor || 0);

    // CTA
    if (els.downloadPdfButton) {
      els.downloadPdfButton.disabled = false;
    }

    // Hide email section until PDF downloaded
    if (els.emailSection) els.emailSection.style.display = "none";

    showResults();
  }

  // ---- PDF Download ----
  async function downloadPdf(scan) {
    const payload = { url: scan.url };
    const controller = new AbortController();
    const t = setTimeout(() => controller.abort(), 90000);

    try {
      const res = await fetch(ENDPOINT_PDF, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      if (!res.ok) {
        let errMsg = `הפקת הדוח נכשלה (HTTP ${res.status})`;
        try {
          const j = await res.json();
          errMsg = j?.detail || j?.error || j?.message || errMsg;
        } catch (_) {}
        throw new Error(errMsg);
      }

      const blob = await res.blob();
      const a = document.createElement("a");
      const url = URL.createObjectURL(blob);

      a.href = url;
      const safeId = scan.scan_id || "scan";
      a.download = `accessibility-report-${safeId}.pdf`;

      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);

      // Show email section after download
      if (els.emailSection) {
        els.emailSection.style.display = "block";
        els.emailSection.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    } catch (e) {
      if (e.name === "AbortError") {
        throw new Error("הפקת הדוח התארכה יותר מדי (timeout). נסה שוב.");
      }
      throw e;
    } finally {
      clearTimeout(t);
    }
  }

  // ---- Email sending ----
  async function sendReportEmail(email) {
    if (!lastScan) throw new Error("אין תוצאות סריקה.");

    const payload = {
      url: lastScan.url,
      scan_id: lastScan.scan_id,
      email: email,
    };

    return await postJson(ENDPOINT_EMAIL, payload, 60000);
  }

  function showEmailStatus(msg, type) {
    if (!els.emailStatus) return;
    els.emailStatus.textContent = msg;
    els.emailStatus.className = `email-status ${type}`;
    els.emailStatus.style.display = "block";
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

  async function onDownloadPdf() {
    clearError();
    if (!lastScan) {
      showError("אין תוצאות סריקה להורדת דוח.");
      return;
    }

    if (els.downloadPdfButton) els.downloadPdfButton.disabled = true;
    try {
      await downloadPdf(lastScan);
    } catch (err) {
      showError(err?.message || "שגיאה לא ידועה בעת הורדת הדוח.");
    } finally {
      if (els.downloadPdfButton) els.downloadPdfButton.disabled = false;
    }
  }

  async function onSendEmail(e) {
    e.preventDefault();
    const email = els.emailInput ? els.emailInput.value.trim() : "";
    if (!email) return;

    if (els.sendEmailButton) els.sendEmailButton.disabled = true;
    showEmailStatus("שולח...", "");

    try {
      await sendReportEmail(email);
      showEmailStatus("הדוח נשלח בהצלחה למייל שלך.", "success");
    } catch (err) {
      showEmailStatus(
        err?.message || "שליחת המייל נכשלה. נסה שוב.",
        "error"
      );
    } finally {
      if (els.sendEmailButton) els.sendEmailButton.disabled = false;
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

  // ---- Bind ----
  function bind() {
    if (els.scanForm) els.scanForm.addEventListener("submit", onSubmit);
    if (els.downloadPdfButton) els.downloadPdfButton.addEventListener("click", onDownloadPdf);
    if (els.newScanButton) els.newScanButton.addEventListener("click", onScanAnother);
    if (els.emailForm) els.emailForm.addEventListener("submit", onSendEmail);
  }

  // Boot
  bind();
  hideResults();
})();
