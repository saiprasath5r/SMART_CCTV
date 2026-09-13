import json
import re
from datetime import datetime
from typing import Dict, Any, Optional
from backend.config import settings
from backend.database import db_manager

class SafetyAIAgent:
    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.model_name = settings.gemini_model
        self.client = None
        self._init_gemini_client()

    def _init_gemini_client(self):
        """Initialize Google GenAI client if API key is provided."""
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                print(f"[Safety-AI] Gemini Client initialized with model {self.model_name}")
            except Exception as e:
                print(f"[Safety-AI] Error initializing Gemini client: {e}")
                self.client = None
        else:
            self.client = None

    def update_api_key(self, new_key: str):
        """Update API key at runtime."""
        self.api_key = new_key
        settings.gemini_api_key = new_key
        self._init_gemini_client()

    def process_inquiry(
        self,
        visitor_id: str,
        visitor_response: str,
        gender: str = "Undetermined",
        location: str = "Sector A - Main Entrance",
        dwell_time: float = 0.0,
        is_loitering: bool = False
    ) -> Dict[str, Any]:
        """
        Process visitor statement using Gemini AI or robust security rule engine.
        Returns parsed identity, purpose, threat level, and spoken response.
        """
        prompt_question = settings.default_safety_prompt

        # Clean input
        visitor_response_clean = visitor_response.strip()
        if not visitor_response_clean:
            visitor_response_clean = "No audible or text response provided."

        # 1. Try Gemini API if client configured
        if self.client:
            try:
                result = self._gemini_evaluate(
                    visitor_id=visitor_id,
                    visitor_response=visitor_response_clean,
                    gender=gender,
                    location=location,
                    dwell_time=dwell_time,
                    is_loitering=is_loitering
                )
                if result:
                    self._persist_and_update(visitor_id, prompt_question, visitor_response_clean, result)
                    return result
            except Exception as e:
                print(f"[Safety-AI] Gemini API execution failed: {e}. Switching to heuristic fallback.")

        # 2. Heuristic Security Rule-Engine Fallback
        result = self._heuristic_evaluate(
            visitor_id=visitor_id,
            visitor_response=visitor_response_clean,
            gender=gender,
            location=location,
            dwell_time=dwell_time,
            is_loitering=is_loitering
        )
        self._persist_and_update(visitor_id, prompt_question, visitor_response_clean, result)
        return result

    def _gemini_evaluate(
        self,
        visitor_id: str,
        visitor_response: str,
        gender: str,
        location: str,
        dwell_time: float,
        is_loitering: bool
    ) -> Optional[Dict[str, Any]]:
        """Query Gemini API with security reasoning instructions."""
        system_instruction = (
            "You are the SMART CCTV Intelligent AI Sentinel. "
            "Your job is to analyze visitor statements caught on surveillance camera, extract their name and purpose of visit, "
            "assess potential threat level (LOW, MEDIUM, HIGH), and provide a concise, professional verbal response for the Web Speech synthesizer. "
            "Always respond strictly with a valid JSON object in this exact schema:\n"
            "{\n"
            '  "visitor_name": "Extracted name or Anonymous",\n'
            '  "purpose": "Concise summary of their visit purpose",\n'
            '  "threat_level": "LOW" | "MEDIUM" | "HIGH",\n'
            '  "reply_speech": "Brief spoken security response under 30 words",\n'
            '  "action_required": "ACCESS_GRANTED" | "ESCORT_REQUIRED" | "SECURITY_DISPATCHED"\n'
            "}"
        )

        user_content = (
            f"Surveillance Context:\n"
            f"- Visitor ID: {visitor_id}\n"
            f"- Visual Gender: {gender}\n"
            f"- Person Location: {location}\n"
            f"- Current Dwell Time: {dwell_time:.1f} seconds\n"
            f"- Loitering Anomaly: {'YES' if is_loitering else 'NO'}\n"
            f"- Visitor's Spoken Statement: \"{visitor_response}\"\n\n"
            f"Analyze and respond with JSON."
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=user_content,
            config={
                "system_instruction": system_instruction,
                "temperature": 0.2,
                "response_mime_type": "application/json"
            }
        )

        text = response.text.strip()
        # Parse JSON
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
            return {
                "visitor_name": parsed.get("visitor_name", "Anonymous"),
                "purpose": parsed.get("purpose", "Unstated"),
                "threat_level": parsed.get("threat_level", "LOW"),
                "reply_speech": parsed.get("reply_speech", "Thank you. Your details have been logged in the security register."),
                "action_required": parsed.get("action_required", "ACCESS_GRANTED")
            }
        return None

    def _heuristic_evaluate(
        self,
        visitor_id: str,
        visitor_response: str,
        gender: str,
        location: str,
        dwell_time: float,
        is_loitering: bool
    ) -> Dict[str, Any]:
        """Sophisticated local rule-based safety classifier."""
        resp_lower = visitor_response.lower()

        # Name extraction patterns
        name = "Anonymous"
        name_patterns = [
            r"(?:i am|my name is|this is|i'm)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)",
            r"^([a-zA-Z]+)\s+here",
            r"^([a-zA-Z]+(?:\s+[a-zA-Z]+)?)$"
        ]
        for pat in name_patterns:
            m = re.search(pat, visitor_response, re.IGNORECASE)
            if m:
                extracted = m.group(1).strip()
                if extracted.lower() not in ["delivery", "guest", "here", "visiting", "looking", "meeting"]:
                    name = extracted.title()
                    break

        # Purpose and Threat detection
        threat_level = "LOW"
        action = "ACCESS_GRANTED"
        purpose = "Visitor Inquiry"

        suspicious_keywords = ["steal", "break in", "trespass", "bypass", "forced", "weapon", "hide", "stalking", "unauthorized", "none of your business"]
        delivery_keywords = ["delivery", "courier", "package", "amazon", "fedex", "ups", "food", "order", "parcel", "drop off"]
        meeting_keywords = ["meeting", "interview", "appointment", "client", "employee", "work", "office", "consultation", "guest"]
        maintenance_keywords = ["repair", "maintenance", "electrician", "plumber", "inspection", "technician", "cleaner", "service"]

        if any(w in resp_lower for w in suspicious_keywords):
            threat_level = "HIGH"
            action = "SECURITY_DISPATCHED"
            purpose = "Suspicious Behavior / Hostile Intent"
            reply_speech = f"Alert: Access is denied. On-site security personnel have been dispatched to {visitor_id}."
        elif is_loitering or dwell_time > settings.loitering_threshold_seconds:
            threat_level = "MEDIUM"
            action = "ESCORT_REQUIRED"
            purpose = "Prolonged Loitering in Monitored Sector"
            reply_speech = f"Visitor {name if name != 'Anonymous' else visitor_id}, you have exceeded stationary time limits. Please proceed to the front reception."
        elif any(w in resp_lower for w in delivery_keywords):
            threat_level = "LOW"
            action = "ACCESS_GRANTED"
            purpose = "Package Delivery / Courier Services"
            reply_speech = f"Thank you {name if name != 'Anonymous' else ''}. Delivery clearance granted. Please deposit parcel at Bay 1."
        elif any(w in resp_lower for w in meeting_keywords):
            threat_level = "LOW"
            action = "ACCESS_GRANTED"
            purpose = "Official Meeting / Appointment"
            reply_speech = f"Welcome {name if name != 'Anonymous' else ''}. Your appointment access is registered. Please proceed inside."
        elif any(w in resp_lower for w in maintenance_keywords):
            threat_level = "LOW"
            action = "ACCESS_GRANTED"
            purpose = "Authorized Facility Maintenance"
            reply_speech = f"Welcome {name if name != 'Anonymous' else ''}. Maintenance credentials logged. Have a safe shift."
        else:
            threat_level = "LOW"
            action = "ACCESS_GRANTED"
            purpose = "General Visitor Inquiry"
            reply_speech = f"Thank you {name if name != 'Anonymous' else ''}. Your entry has been recorded in the surveillance log."

        return {
            "visitor_name": name,
            "purpose": purpose,
            "threat_level": threat_level,
            "reply_speech": reply_speech,
            "action_required": action
        }

    def _persist_and_update(self, visitor_id: str, prompt: str, visitor_response: str, result: Dict[str, Any]):
        """Save conversation and update visitor metadata in SQLite."""
        db_manager.log_conversation(
            visitor_id=visitor_id,
            ai_prompt=prompt,
            visitor_response=visitor_response,
            ai_reply=result.get("reply_speech", ""),
            threat_assessment=result.get("threat_level", "LOW")
        )
        db_manager.upsert_visitor(
            visitor_id=visitor_id,
            threat_level=result.get("threat_level", "LOW"),
            visitor_name=result.get("visitor_name", "Anonymous"),
            purpose_of_visit=result.get("purpose", "Unstated")
        )

# Global Safety AI Agent instance
safety_agent = SafetyAIAgent()
