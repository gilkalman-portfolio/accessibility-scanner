console.log("SCRIPT VERSION: 2026-01-27 BLUE-MAPPING v3");
(() => {
  // ---------------- Config ----------------
  const API_URL =
    window.location.hostname === "localhost"
      ? "http://localhost:8000"
      : ""; // same-origin in production (recommended)

  const ENDPOINT_SCAN = `${API_URL}/api/v1/scan`;
  const ENDPOINT_PDF = `${API_URL}/api/v1/scan/pdf`;

  const els = {
    scanForm: document.getElementById("scanForm"),
    urlInput: document.getElementById("urlInput"),
    loading: document.getElementById("loading"),
    errorMessage: document.getElementById("errorMessage"),

    results: document.getElementById("results"),
    exposureValue: document.getElementById("exposureValue"),
    exposureNote: document.getElementById("exposureNote"),

    criticalCount: document.getElementById("criticalCount"),
    majorCount: document.getElementById("majorCount"),
    minorCount: document.getElementById("minorCount"),

    downloadPdfButton: document.getElementById("downloadPdfButton"),
    scanAnotherButton: document.getElementById("scanAnotherButton"),
  };

  let lastScan = null;

  // ---------------- Helpers ----------------
  function setLoading(isLoading) {
    if (els.loading) els.loading.style.display = isLoading ? "block" : "none";
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
  }

  function normalizeUrl(raw) {
    const s = (raw || "").trim();
    if (!s) return "";
    if (/^https?:\/\//i.test(s)) return s;
    return `https://${s}`;
  }

  function riskLabel(level) {
    const v = (level || "").toUpperCase();
    if (v === "CRITICAL") return "קריטית";
    if (v === "HIGH") return "גבוהה";
    if (v === "MEDIUM") return "בינונית";
    if (v === "LOW") return "נמוכה";
    return "לא ידועה";
  }

  function riskExplanation(explanationKey) {
    // Keep it legally safe: no promises, no legal advice.
    switch ((explanationKey || "").toUpperCase()) {
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

      const contentType = res.headers.get("content-type") || "";
      if (!res.ok) {
        let errMsg = `שגיאה מהשרת (HTTP ${res.status})`;
        try {
          if (contentType.includes("application/json")) {
            const j = await res.json();
            errMsg = j?.detail || j?.error || j?.message || errMsg;
          } else {
            const txt = await res.text();
            if (txt) errMsg = txt.slice(0, 300);
          }
        } catch (_) {}
        throw new Error(errMsg);
      }

      if (contentType.includes("application/json")) {
        return await res.json();
      }
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

  // ---------------- Core ----------------
  async function runScan(url) {
    // Backend expects: { url }
    const result = await postJson(ENDPOINT_SCAN, { url });
    return result;
  }

  function renderResults(scan) {
    lastScan = scan;

    // Map backend schema -> UI fields
    const level = scan?.risk?.level || "UNKNOWN";
    const explanationKey = scan?.risk?.explanation_key || "";

    const summary = scan?.summary || {};
    const critical = Number(summary.critical || 0);
    const serious = Number(summary.serious || 0);
    const moderate = Number(summary.moderate || 0);
    const minor = Number(summary.minor || 0);

    if (els.exposureValue) els.exposureValue.textContent = riskLabel(level);
    if (els.exposureNote) els.exposureNote.textContent = riskExplanation(explanationKey);

    if (els.criticalCount) els.criticalCount.textContent = String(critical);
    if (els.majorCount) els.majorCount.textContent = String(serious);
    if (els.minorCount) els.minorCount.textContent = String(moderate + minor);

    // CTA: keep single paid action behavior (download report)
    if (els.downloadPdfButton) {
      els.downloadPdfButton.disabled = false;
      els.downloadPdfButton.style.display = "inline-flex";
    }

    showResults();
  }

  async function downloadPdf(scan) {
    // Backend likely expects: { url } (and optionally scan_id if you decide later)
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
      const safeId = scan?.scan_id ? scan.scan_id : "scan";
      a.download = `accessibility-report-${safeId}.pdf`;

      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      if (e.name === "AbortError") {
        throw new Error("הפקת הדוח התארכה יותר מדי (timeout). נסה שוב.");
      }
      throw e;
    } finally {
      clearTimeout(t);
    }
  }

  // ---------------- Events ----------------
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
      const result = await runScan(url);
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

  function onScanAnother() {
    clearError();
    hideResults();
    if (els.urlInput) els.urlInput.focus();
  }

  function bind() {
    if (els.scanForm) els.scanForm.addEventListener("submit", onSubmit);
    if (els.downloadPdfButton) els.downloadPdfButton.addEventListener("click", onDownloadPdf);
    if (els.scanAnotherButton) els.scanAnotherButton.addEventListener("click", onScanAnother);
  }

  // Boot
  bind();
  hideResults();
})();
