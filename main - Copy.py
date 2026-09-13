import os
import time
import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response, HTTPException, Body
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from backend.config import settings
from backend.database import db_manager
from backend.ai_engine import surveillance_engine
from backend.safety_agent import safety_agent
from backend.alert_service import alert_service

app = FastAPI(
    title="SMART CCTV",
    description="Smart AI CCTV Surveillance & Demographics Monitoring System.",
    version="1.0.0"
)

# CORS Configuration
# Allow Firebase Hosting domains + Cloud Run URL + local development
_ALLOWED_ORIGINS = [
    "*",  # Dev: allow all (restrict in production via env var ALLOWED_ORIGINS)
]
_env_origins = os.getenv("ALLOWED_ORIGINS", "")
if _env_origins:
    _ALLOWED_ORIGINS = [o.strip() for o in _env_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure snapshot directory exists
settings.snapshots_dir.mkdir(parents=True, exist_ok=True)

# Mount Static and Snapshots directories
app.mount("/static", StaticFiles(directory=str(settings.base_dir / "static")), name="static")
app.mount("/snapshots", StaticFiles(directory=str(settings.snapshots_dir)), name="snapshots")

# Templates
templates = Jinja2Templates(directory=str(settings.base_dir / "templates"))

# --- Pydantic Request Models ---
class InterrogateRequest(BaseModel):
    visitor_id: str
    transcript: str
    gender: Optional[str] = "Undetermined"
    location: Optional[str] = "Sector A - Main Entrance"
    dwell_time: Optional[float] = 0.0
    is_loitering: Optional[bool] = False

class AlertTriggerRequest(BaseModel):
    visitor_id: Optional[str] = "OPERATOR_OVERRIDE"
    alert_type: str = "MANUAL_PANIC"
    message: str = "Manual security alert triggered from Mission Control Dashboard."

class ConfigUpdateRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_from_number: Optional[str] = None
    twilio_to_number: Optional[str] = None
    twilio_whatsapp_from: Optional[str] = None
    twilio_whatsapp_to: Optional[str] = None
    loitering_threshold_seconds: Optional[int] = None
    default_safety_prompt: Optional[str] = None
    rtsp_stream_url: Optional[str] = None

# --- HTTP Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    """Render the Main Security Mission Control Dashboard."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "loitering_threshold": settings.loitering_threshold_seconds,
            "default_prompt": settings.default_safety_prompt,
            "has_gemini_key": bool(settings.gemini_api_key),
            "has_twilio_config": bool(settings.twilio_account_sid and settings.twilio_auth_token)
        }
    )

@app.get("/api/stats")
async def get_statistics():
    """Return aggregated surveillance and demographic metrics."""
    stats = db_manager.get_stats()
    return {"status": "success", "data": stats}

@app.get("/api/visitors")
async def get_visitors(limit: int = 50):
    """Retrieve list of recently tracked visitors with metadata and face snapshots."""
    visitors = db_manager.get_recent_visitors(limit=limit)
    return {"status": "success", "data": visitors}

@app.get("/api/alerts")
async def get_alerts(limit: int = 30):
    """Retrieve security alerts audit log."""
    alerts = db_manager.get_recent_alerts(limit=limit)
    return {"status": "success", "data": alerts}

@app.get("/api/logs/export.csv")
async def export_logs_csv():
    """Download full surveillance audit log as a CSV spreadsheet."""
    csv_content = db_manager.export_csv()
    filename = f"surveillance_audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.post("/api/agent/interrogate")
async def interrogate_visitor(payload: InterrogateRequest):
    """
    Process visitor spoken/typed responses via Gemini AI Safety Sentinel,
    updating the visitor register and triggering alarms if threat is detected.
    """
    result = safety_agent.process_inquiry(
        visitor_id=payload.visitor_id,
        visitor_response=payload.transcript,
        gender=payload.gender,
        location=payload.location or "Sector A - Main Entrance",
        dwell_time=payload.dwell_time,
        is_loitering=payload.is_loitering
    )

    # If HIGH threat detected, trigger instant dispatch alert
    if result.get("threat_level") == "HIGH":
        alert_service.send_high_threat_alert(
            visitor_id=payload.visitor_id,
            visitor_name=result.get("visitor_name", "Unknown"),
            purpose=result.get("purpose", "Unauthorized"),
            statement=payload.transcript
        )

    return {"status": "success", "data": result}

@app.post("/api/alerts/trigger")
async def trigger_manual_alert(payload: AlertTriggerRequest):
    """Manually dispatch a security emergency alert."""
    result = alert_service.dispatch_alert(
        visitor_id=payload.visitor_id,
        alert_type=payload.alert_type,
        severity="CRITICAL",
        message=payload.message
    )
    return {"status": "success", "data": result}

@app.get("/api/config")
async def get_config():
    """Get active configuration (with masked sensitive keys)."""
    return {
        "loitering_threshold_seconds": settings.loitering_threshold_seconds,
        "default_safety_prompt": settings.default_safety_prompt,
        "has_gemini_key": bool(settings.gemini_api_key),
        "has_twilio_config": bool(settings.twilio_account_sid and settings.twilio_auth_token),
        "twilio_from_number": settings.twilio_from_number,
        "twilio_to_number": settings.twilio_to_number,
        "rtsp_stream_url": settings.rtsp_stream_url
    }

@app.post("/api/config")
async def update_config(payload: ConfigUpdateRequest):
    """Update settings dynamically from UI modal."""
    if payload.gemini_api_key is not None:
        safety_agent.update_api_key(payload.gemini_api_key)
    
    if payload.twilio_account_sid is not None or payload.twilio_auth_token is not None:
        alert_service.update_credentials(
            account_sid=payload.twilio_account_sid or "",
            auth_token=payload.twilio_auth_token or "",
            from_number=payload.twilio_from_number or "",
            to_number=payload.twilio_to_number or "",
            whatsapp_from=payload.twilio_whatsapp_from or "",
            whatsapp_to=payload.twilio_whatsapp_to or ""
        )

    if payload.loitering_threshold_seconds is not None:
        settings.loitering_threshold_seconds = payload.loitering_threshold_seconds

    if payload.default_safety_prompt is not None:
        settings.default_safety_prompt = payload.default_safety_prompt

    if payload.rtsp_stream_url is not None:
        settings.rtsp_stream_url = payload.rtsp_stream_url

    return {"status": "success", "message": "Configuration updated successfully."}

# --- High-Performance WebSocket Stream & Inference ---

@app.websocket("/ws/stream")
async def websocket_stream_endpoint(websocket: WebSocket):
    """
    Bi-directional real-time WebSocket connection:
    - Receives live video frames from client webcam/RTSP
    - Performs face detection & gender classification
    - Tracks visitor dwell time & detects loitering
    - Returns bounding boxes, demographic counts, voice prompt triggers & loitering alerts
    """
    await websocket.accept()
    last_processed_time = time.time()

    try:
        while True:
            # Receive data frame or message
            data_text = await websocket.receive_text()
            message = json.loads(data_text)

            msg_type = message.get("type", "frame")

            if msg_type == "frame":
                frame_b64 = message.get("frame", "")
                if not frame_b64:
                    continue

                # Decode frame
                frame = surveillance_engine.decode_base64_frame(frame_b64)
                if frame is not None:
                    # Run AI detection & tracking
                    results = surveillance_engine.process_frame(frame)

                    # Handle loitering alert notifications
                    for alert in results.get("loitering_alerts", []):
                        alert_service.send_loitering_alert(
                            visitor_id=alert["visitor_id"],
                            gender=alert["gender"],
                            dwell_time=alert["dwell_time"]
                        )

                    now = time.time()
                    fps = round(1.0 / (now - last_processed_time + 1e-6), 1)
                    last_processed_time = now

                    # Send back results
                    response_payload = {
                        "type": "detection_result",
                        "fps": fps,
                        "occupants": results["occupants"],
                        "males": results["males"],
                        "females": results["females"],
                        "tracked_persons": results["tracked_persons"],
                        "new_visitors": results["new_visitors"],
                        "loitering_alerts": results["loitering_alerts"],
                        "timestamp": datetime.now().isoformat()
                    }
                    await websocket.send_text(json.dumps(response_payload))

            elif msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "time": time.time()}))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WebSocket] Disconnect / Error: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port, reload=False)
