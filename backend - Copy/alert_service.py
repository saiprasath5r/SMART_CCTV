import time
from datetime import datetime
from typing import Dict, Any, Optional
from backend.config import settings
from backend.database import db_manager

class AlertService:
    def __init__(self):
        self.twilio_client = None
        self._init_twilio()

    def _init_twilio(self):
        """Initialize Twilio client if credentials are configured."""
        if settings.twilio_account_sid and settings.twilio_auth_token:
            try:
                from twilio.rest import Client
                self.twilio_client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
                print("[Alert-Service] Twilio Client initialized successfully.")
            except Exception as e:
                print(f"[Alert-Service] Error initializing Twilio client: {e}")
                self.twilio_client = None
        else:
            self.twilio_client = None

    def update_credentials(
        self,
        account_sid: str = "",
        auth_token: str = "",
        from_number: str = "",
        to_number: str = "",
        whatsapp_from: str = "",
        whatsapp_to: str = ""
    ):
        """Update Twilio configuration at runtime."""
        if account_sid:
            settings.twilio_account_sid = account_sid
        if auth_token:
            settings.twilio_auth_token = auth_token
        if from_number:
            settings.twilio_from_number = from_number
        if to_number:
            settings.twilio_to_number = to_number
        if whatsapp_from:
            settings.twilio_whatsapp_from = whatsapp_from
        if whatsapp_to:
            settings.twilio_whatsapp_to = whatsapp_to

        self._init_twilio()

    def send_loitering_alert(
        self,
        visitor_id: str,
        gender: str,
        dwell_time: float,
        location: str = "Main Sector 1"
    ) -> Dict[str, Any]:
        """Dispatch instant security alert for prolonged loitering anomaly."""
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message_body = (
            f"🚨 [CCTV SECURITY ALERT - LOITERING DETECTED]\n"
            f"• Location: {location}\n"
            f"• Visitor: {visitor_id} ({gender})\n"
            f"• Stationary Dwell Time: {int(dwell_time)}s (Threshold: {settings.loitering_threshold_seconds}s)\n"
            f"• Time: {timestamp_str}\n"
            f"• Action: Security surveillance active. Investigate immediately."
        )

        return self.dispatch_alert(
            visitor_id=visitor_id,
            alert_type="LOITERING_ANOMALY",
            severity="WARNING",
            message=message_body
        )

    def send_high_threat_alert(
        self,
        visitor_id: str,
        visitor_name: str,
        purpose: str,
        statement: str
    ) -> Dict[str, Any]:
        """Dispatch critical alert for high-risk visitor statement or unauthorized intrusion."""
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message_body = (
            f"🚨🚨 [CRITICAL SECURITY BREACH ALERT]\n"
            f"• Visitor: {visitor_id} (Name: {visitor_name})\n"
            f"• Threat Assessment: HIGH\n"
            f"• Stated Reason: {purpose}\n"
            f"• Transcript: \"{statement}\"\n"
            f"• Time: {timestamp_str}\n"
            f"• Action: Immediate security response dispatched."
        )

        return self.dispatch_alert(
            visitor_id=visitor_id,
            alert_type="HIGH_THREAT_DETECTION",
            severity="CRITICAL",
            message=message_body
        )

    def dispatch_alert(
        self,
        visitor_id: str,
        alert_type: str,
        severity: str,
        message: str
    ) -> Dict[str, Any]:
        """Send alert across available channels (Twilio SMS, Twilio WhatsApp, and local Audit Log)."""
        sms_status = "NOT_CONFIGURED"
        whatsapp_status = "NOT_CONFIGURED"

        # 1. SMS Dispatch
        if self.twilio_client and settings.twilio_from_number and settings.twilio_to_number:
            try:
                sms = self.twilio_client.messages.create(
                    body=message,
                    from_=settings.twilio_from_number,
                    to=settings.twilio_to_number
                )
                sms_status = f"SENT (SID: {sms.sid})"
            except Exception as e:
                sms_status = f"FAILED: {str(e)}"
        elif not self.twilio_client:
            sms_status = "SIMULATION_MODE (Live keys not set)"

        # 2. WhatsApp Dispatch
        if self.twilio_client and settings.twilio_whatsapp_from and settings.twilio_whatsapp_to:
            try:
                wa = self.twilio_client.messages.create(
                    body=message,
                    from_=settings.twilio_whatsapp_from,
                    to=settings.twilio_whatsapp_to
                )
                whatsapp_status = f"SENT (SID: {wa.sid})"
            except Exception as e:
                whatsapp_status = f"FAILED: {str(e)}"
        elif not self.twilio_client:
            whatsapp_status = "SIMULATION_MODE (Live keys not set)"

        overall_status = "SENT" if ("SENT (SID" in sms_status or "SENT (SID" in whatsapp_status) else "SIMULATION"

        # Log into SQLite
        alert_id = db_manager.log_alert(
            visitor_id=visitor_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            channel="SMS & WhatsApp",
            status=overall_status
        )

        return {
            "alert_id": alert_id,
            "visitor_id": visitor_id,
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "sms_status": sms_status,
            "whatsapp_status": whatsapp_status,
            "timestamp": datetime.now().isoformat()
        }

# Global Alert Service instance
alert_service = AlertService()
