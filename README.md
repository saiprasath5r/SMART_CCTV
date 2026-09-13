# 🛡️ SMART CCTV: Production-Ready AI Surveillance & Security Monitoring

A full-stack AI CCTV surveillance and facility security monitoring system built with **FastAPI (Python)**, **HTML5 Canvas / WebRTC**, **OpenCV Real-Time Face, Location & Gender Analytics**, **Google Gemini AI Safety Agent**, and **Twilio SMS / WhatsApp Alerting**.

---

## 🌟 Key Features

1. **Live Camera Feed & Stream**:
   - Seamlessly captures browser webcam via WebRTC / Canvas and supports IP Camera RTSP streams.
   - High-throughput OpenCV face detection with dynamic cyberpunk bounding boxes, HUD crosshairs, and targeting reticles.
   - Built-in High-Fidelity synthetic security test feed for instant demo & testing without requiring physical camera permissions.

2. **Real-Time Demographics & Person Location Tracking**:
   - Real-time **Spatial Location / Sector Tracking** (e.g. `Sector A (North) - Main Entrance`, `Sector B (South) - West Corridor`).
   - Real-time gender classification (`Male` / `Female`) with calibrated confidence scores (e.g. `Male 94%`).
   - Live telemetry counters for **Total Occupants**, **Male Count**, **Female Count**, and **Average Dwell Time**.

3. **Interactive Safety AI Agent ("AEGIS Sentinel")**:
   - Autonomous security voice prompt via browser Web Speech API: *"Welcome. For safety purposes, please state your name and purpose of visit."*
   - Interactive speech transcription (Speech-to-Text) + manual verification.
   - Google Gemini AI-powered reasoning engine assessing visitor intent, threat level (`LOW`, `MEDIUM`, `HIGH`), and returning natural spoken security instructions.
   - Robust offline heuristic safety rule fallback.

4. **Anomaly Detection & Automated Alerts**:
   - Tracks individual visitor dwell time using Centroid & IoU tracking.
   - Triggers a **Prolonged Loitering Alert** when any person remains stationary in the sector for >15 seconds.
   - Multi-channel instant alerting via **Twilio SMS & WhatsApp** with simulation mode for instant evaluation.
   - Dashboard red visual alert banner with Web Audio API synthetic police/security siren.

5. **Data Logging & CSV Audit Export**:
   - Persistent SQLite database logging: Timestamp, Visitor ID, Name, Gender & Confidence, First/Last seen, Dwell time, Loitering status, AI Transcripts, Threat Assessment, and Captured Face Snapshots.
   - Instant 1-click **Downloadable CSV Audit Log**.

---

## 📁 Project Structure

```
.
├── backend/
│   ├── __init__.py
│   ├── config.py              # Application settings & environment loader
│   ├── database.py            # SQLite schema, tables, logging & CSV exporter
│   ├── tracker.py             # Centroid visitor tracking & dwell time engine
│   ├── ai_engine.py           # Face detection, gender classification & snapshot capture
│   ├── safety_agent.py        # Gemini AI safety reasoning & dialogue agent
│   └── alert_service.py       # Twilio SMS/WhatsApp alert dispatcher
├── data/
│   ├── snapshots/             # Saved cropped face snapshot images
│   └── surveillance.db        # SQLite persistent database
├── static/
│   ├── css/
│   │   └── style.css          # Modern Cyberpunk HUD Glassmorphism styling
│   ├── js/
│   │   ├── audio_alarm.js     # Web Audio API synthetic siren alarm generator
│   │   ├── voice_agent.js     # Web Speech API synthesis & recognition controller
│   │   ├── camera.js          # Canvas video streaming, HUD crosshairs & bounding boxes
│   │   └── app.js             # Main dashboard controller & WebSocket manager
│   ├── img/
│   │   └── face_placeholder.svg
│   └── models/                # Deep learning weights directory
├── templates/
│   └── index.html             # Futuristic Mission Control Security Dashboard
├── main.py                    # FastAPI server entry point & WebSocket pipeline
├── requirements.txt           # Backend Python package dependencies
├── .env.example               # Configuration template
└── README.md
```

---

## 🚀 Getting Started

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Environment Configuration (Optional)
Copy `.env.example` to `.env` or configure directly in the web UI Settings modal:
```bash
cp .env.example .env
```
Key configuration parameters:
- `GEMINI_API_KEY`: Your Google Gemini API key (optional; heuristic fallback works offline).
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `TWILIO_TO_NUMBER`: Twilio SMS credentials (optional; simulation mode works out-of-the-box).
- `LOITERING_THRESHOLD_SECONDS`: Dwell time threshold in seconds before triggering an alert (default: `15`).

### 3. Launch Application
```bash
python main.py
```
Or with Uvicorn:
```bash
uvicorn main.py --host 0.0.0.0 --port 8000 --reload
```

### 4. Open Mission Control Dashboard
Navigate to [http://localhost:8000](http://localhost:8000) in your web browser (Google Chrome or Microsoft Edge recommended for Web Speech & Web Audio support).

---

## 📊 API Reference

- `GET /` - Main Mission Control Dashboard UI.
- `WS /ws/stream` - High-speed bidirectional WebSocket stream for video frame analysis, bounding boxes, and real-time alerts.
- `GET /api/stats` - Summary of active occupants, demographic counts, and alert counts.
- `GET /api/visitors` - List of recently detected visitors with snapshots and threat assessments.
- `GET /api/alerts` - Security alerts history log.
- `GET /api/logs/export.csv` - Download complete audit log as a CSV spreadsheet.
- `POST /api/agent/interrogate` - Interrogate visitor statement via Gemini AI Safety Sentinel.
- `POST /api/alerts/trigger` - Manual panic button trigger.
- `POST /api/config` - Dynamic runtime settings update.
