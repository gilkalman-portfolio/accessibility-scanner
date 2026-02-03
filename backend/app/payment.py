"""
Payment Service for Israeli Accessibility Scanner
Handles Grow/Meshulam payment gateway integration with demo mode fallback.
"""

import os
import secrets
import logging
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class PaymentService:
    """
    Manages payment sessions, Meshulam API integration, and token-based PDF access.

    Demo mode: When MESHULAM_PAGE_CODE is empty, all payments auto-succeed
    without contacting Meshulam. A visible warning is returned in responses.
    """

    def __init__(self):
        self.api_key = os.getenv("MESHULAM_API_KEY", "")
        self.user_id = os.getenv("MESHULAM_USER_ID", "")
        self.page_code = os.getenv("MESHULAM_PAGE_CODE", "")
        self.sandbox = os.getenv("MESHULAM_SANDBOX", "true").lower() == "true"
        self.amount = int(os.getenv("PAYMENT_AMOUNT", "79"))
        self.frontend_url = os.getenv(
            "FRONTEND_URL",
            "https://frontend-sooty-omega-76.vercel.app",
        ).rstrip("/")
        self.backend_url = os.getenv(
            "BACKEND_URL",
            "https://truthful-simplicity-production.up.railway.app",
        ).rstrip("/")

        # Demo mode when no Meshulam credentials configured
        self.demo_mode = not bool(self.page_code)

        # In-memory session store  {session_id: dict}
        self._sessions: dict[str, dict] = {}
        # Token → session_id mapping  {pdf_token: session_id}
        self._tokens: dict[str, str] = {}

        # Production safety: warn loudly if demo mode is on with production URLs
        if self.demo_mode:
            logger.warning(
                "⚠️  PaymentService running in DEMO MODE — no real payments. "
                "Set MESHULAM_PAGE_CODE to enable real payments."
            )
        else:
            env = "SANDBOX" if self.sandbox else "PRODUCTION"
            logger.info(f"PaymentService initialized — Meshulam {env}")

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    async def create_session(
        self,
        url: str,
        email: str,
        scan_id: str,
    ) -> dict:
        """
        Create a payment session and return a Meshulam payment URL (or demo URL).
        """
        self._cleanup_expired()

        session_id = f"pay_{secrets.token_hex(6)}"
        session = {
            "session_id": session_id,
            "scan_id": scan_id,
            "url": url,
            "email": email,
            "amount": self.amount,
            "status": "pending",
            "meshulam_process_id": None,
            "payment_url": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "pdf_token": None,
            "pdf_bytes": None,  # Cached after generation
            "demo_mode": self.demo_mode,
        }

        if self.demo_mode:
            payment_url = self._create_demo_payment(session)
        else:
            payment_url = await self._create_meshulam_payment(session)

        session["payment_url"] = payment_url
        self._sessions[session_id] = session

        logger.info(
            f"Payment session created: {session_id} | "
            f"email={email} | demo={self.demo_mode}"
        )

        return {
            "session_id": session_id,
            "payment_url": payment_url,
            "demo_mode": self.demo_mode,
        }

    async def verify_session(self, session_id: str) -> dict:
        """
        Verify payment was completed. Returns status + pdf_token on success.
        """
        session = self._sessions.get(session_id)
        if not session:
            return {"status": "not_found", "pdf_token": None, "email": "", "scan_url": ""}

        # Already completed — return existing token
        if session["status"] == "completed" and session["pdf_token"]:
            return {
                "status": "completed",
                "pdf_token": session["pdf_token"],
                "email": session["email"],
                "scan_url": session["url"],
                "demo_mode": session["demo_mode"],
            }

        # Verify with Meshulam or auto-complete in demo
        if self.demo_mode:
            verified = True
        else:
            verified = await self._verify_meshulam_payment(session)

        if verified:
            # Generate one-time PDF token
            pdf_token = secrets.token_urlsafe(32)
            session["status"] = "completed"
            session["completed_at"] = datetime.now(timezone.utc).isoformat()
            session["pdf_token"] = pdf_token
            self._tokens[pdf_token] = session_id

            logger.info(f"Payment verified: {session_id} | token generated")

            return {
                "status": "completed",
                "pdf_token": pdf_token,
                "email": session["email"],
                "scan_url": session["url"],
                "demo_mode": session["demo_mode"],
            }

        return {
            "status": "pending",
            "pdf_token": None,
            "email": session["email"],
            "scan_url": session["url"],
            "demo_mode": session["demo_mode"],
        }

    def get_session_by_token(self, pdf_token: str) -> Optional[dict]:
        """
        Look up a session by its PDF download token.
        Returns session dict if token is valid and not expired, else None.
        Token allows up to 3 uses within 30 minutes.
        """
        session_id = self._tokens.get(pdf_token)
        if not session_id:
            return None

        session = self._sessions.get(session_id)
        if not session:
            return None

        if session["status"] != "completed":
            return None

        # Check expiry (30 min from completion)
        completed_at = session.get("completed_at", "")
        if completed_at:
            try:
                completed_time = datetime.fromisoformat(completed_at)
                elapsed = (datetime.now(timezone.utc) - completed_time).total_seconds()
                if elapsed > 1800:  # 30 minutes
                    logger.info(f"Token expired: {pdf_token[:8]}...")
                    del self._tokens[pdf_token]
                    return None
            except (ValueError, TypeError):
                pass

        return session

    def store_pdf(self, session_id: str, pdf_bytes: bytes):
        """Cache generated PDF bytes in the session for download."""
        session = self._sessions.get(session_id)
        if session:
            session["pdf_bytes"] = pdf_bytes

    def get_cached_pdf(self, session_id: str) -> Optional[bytes]:
        """Retrieve cached PDF bytes for a session."""
        session = self._sessions.get(session_id)
        if session:
            return session.get("pdf_bytes")
        return None

    async def handle_webhook(self, data: dict) -> bool:
        """
        Handle Meshulam server-to-server webhook callback.
        Updates session status based on payment result.
        """
        external_id = data.get("customFields", {}).get("cField1", "")
        status_code = data.get("status", "")

        if not external_id:
            logger.warning("Webhook received without external identifier")
            return False

        session = self._sessions.get(external_id)
        if not session:
            logger.warning(f"Webhook for unknown session: {external_id}")
            return False

        if status_code == "1":  # Success
            if session["status"] != "completed":
                pdf_token = secrets.token_urlsafe(32)
                session["status"] = "completed"
                session["completed_at"] = datetime.now(timezone.utc).isoformat()
                session["pdf_token"] = pdf_token
                self._tokens[pdf_token] = external_id
                logger.info(f"Webhook confirmed payment: {external_id}")
            return True

        logger.info(f"Webhook non-success status {status_code} for {external_id}")
        return False

    # ------------------------------------------------------------------ #
    #  Meshulam API
    # ------------------------------------------------------------------ #

    async def _create_meshulam_payment(self, session: dict) -> str:
        """Call Meshulam createPaymentProcess API."""
        import httpx

        base_url = (
            "https://sandbox.meshulam.co.il"
            if self.sandbox
            else "https://secure.meshulam.co.il"
        )
        endpoint = f"{base_url}/api/light/server/1.0/createPaymentProcess"

        success_url = (
            f"{self.frontend_url}/payment-success.html"
            f"?session_id={session['session_id']}"
        )
        cancel_url = f"{self.frontend_url}/?payment=cancelled"
        webhook_url = f"{self.backend_url}/api/v1/payment/webhook"

        payload = {
            "pageCode": self.page_code,
            "userId": self.user_id,
            "apiKey": self.api_key,
            "sum": session["amount"],
            "description": f"דוח נגישות – {session['url'][:60]}",
            "successUrl": success_url,
            "cancelUrl": cancel_url,
            "invoiceNotifyUrl": webhook_url,
            "cField1": session["session_id"],
            "pageField[email]": session["email"],
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(endpoint, data=payload, timeout=15.0)
                resp.raise_for_status()
                data = resp.json()

            if data.get("status") != 1:
                err_msg = data.get("err", {}).get("message", "Unknown Meshulam error")
                raise RuntimeError(f"Meshulam: {err_msg}")

            payment_url = data["data"]["url"]
            session["meshulam_process_id"] = data["data"].get("processId")

            logger.info(f"Meshulam payment created: {session['session_id']}")
            return payment_url

        except httpx.HTTPError as e:
            logger.error(f"Meshulam API error: {e}")
            raise RuntimeError("Payment gateway unavailable. Please try again.")

    async def _verify_meshulam_payment(self, session: dict) -> bool:
        """Call Meshulam getPaymentProcessInfo to verify payment."""
        import httpx

        process_id = session.get("meshulam_process_id")
        if not process_id:
            return False

        base_url = (
            "https://sandbox.meshulam.co.il"
            if self.sandbox
            else "https://secure.meshulam.co.il"
        )
        endpoint = f"{base_url}/api/light/server/1.0/getPaymentProcessInfo"

        payload = {
            "pageCode": self.page_code,
            "userId": self.user_id,
            "apiKey": self.api_key,
            "processId": process_id,
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(endpoint, data=payload, timeout=15.0)
                resp.raise_for_status()
                data = resp.json()

            if data.get("status") != 1:
                return False

            process_info = data.get("data", {})
            # Meshulam status 1 = completed successfully
            return process_info.get("transactionStatus") == 1

        except Exception as e:
            logger.error(f"Meshulam verify error: {e}")
            return False

    # ------------------------------------------------------------------ #
    #  Demo mode
    # ------------------------------------------------------------------ #

    def _create_demo_payment(self, session: dict) -> str:
        """Return a URL that redirects directly to success page (no real payment)."""
        return (
            f"{self.frontend_url}/payment-success.html"
            f"?session_id={session['session_id']}&demo=1"
        )

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def is_production_safe(self) -> bool:
        """Check if demo mode is OFF (real payments configured)."""
        return not self.demo_mode

    def _cleanup_expired(self):
        """Remove sessions older than 2 hours to prevent memory leaks."""
        now = time.time()
        cutoff = 7200  # 2 hours in seconds
        expired = []

        for sid, session in self._sessions.items():
            created = session.get("created_at", "")
            try:
                created_dt = datetime.fromisoformat(created)
                elapsed = (datetime.now(timezone.utc) - created_dt).total_seconds()
                if elapsed > cutoff:
                    expired.append(sid)
            except (ValueError, TypeError):
                expired.append(sid)

        for sid in expired:
            session = self._sessions.pop(sid, {})
            token = session.get("pdf_token")
            if token:
                self._tokens.pop(token, None)

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired payment sessions")
