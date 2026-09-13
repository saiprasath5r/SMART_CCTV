import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

# Load .env if present
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class AppSettings(BaseModel):
    # Server
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    debug: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

    # Directories
    base_dir: Path = BASE_DIR
    data_dir: Path = BASE_DIR / "data"
    snapshots_dir: Path = BASE_DIR / "data" / "snapshots"
    db_path: Path = BASE_DIR / "data" / "surveillance.db"
    models_dir: Path = BASE_DIR / "static" / "models"

    # AI & Demographics
    loitering_threshold_seconds: int = int(os.getenv("LOITERING_THRESHOLD_SECONDS", "15"))
    face_confidence_threshold: float = float(os.getenv("FACE_CONFIDENCE_THRESHOLD", "0.5"))
    gender_confidence_threshold: float = float(os.getenv("GENDER_CONFIDENCE_THRESHOLD", "0.6"))
    capture_snapshots: bool = os.getenv("CAPTURE_SNAPSHOTS", "True").lower() in ("true", "1", "yes")
    default_camera_index: int = int(os.getenv("DEFAULT_CAMERA_INDEX", "0"))
    rtsp_stream_url: str = os.getenv("RTSP_STREAM_URL", "")

    # Gemini AI
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Twilio Alerting
    twilio_account_sid: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_from_number: str = os.getenv("TWILIO_FROM_NUMBER", "")
    twilio_to_number: str = os.getenv("TWILIO_TO_NUMBER", "")
    twilio_whatsapp_from: str = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
    twilio_whatsapp_to: str = os.getenv("TWILIO_WHATSAPP_TO", "")

    # Safety Voice Prompt
    default_safety_prompt: str = (
        "Welcome. For safety purposes, please state your name and purpose of visit."
    )

    class Config:
        arbitrary_types_allowed = True

# Global Settings Instance
settings = AppSettings()

# Ensure directories exist
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.snapshots_dir.mkdir(parents=True, exist_ok=True)
settings.models_dir.mkdir(parents=True, exist_ok=True)
