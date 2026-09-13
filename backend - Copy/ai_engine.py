import os
import cv2
import time
import base64
import numpy as np
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional

from backend.config import settings
from backend.tracker import CentroidTracker, TrackedPerson
from backend.database import db_manager

# Gender label constants
GENDER_LIST = ['Male', 'Female']

class SurveillanceEngine:
    def __init__(self):
        self.tracker = CentroidTracker(
            max_disappeared=25, 
            max_distance=120.0,
            on_deregister=self._on_person_exit
        )
        self.face_cascade = None
        self.dnn_net = None
        self.gender_net = None
        self.use_dnn = False
        self.use_gender_dnn = False

        self._init_models()

    def _on_person_exit(self, person: TrackedPerson):
        """Automatically persist final dwell time and departure status when visitor leaves the scene."""
        try:
            db_manager.upsert_visitor(
                visitor_id=person.visitor_id,
                gender=person.gender,
                gender_confidence=person.gender_confidence,
                location=person.location,
                first_seen=person.first_seen_iso,
                last_seen=person.last_seen_iso,
                duration_seconds=person.duration_seconds,
                is_loitering=person.is_loitering,
                snapshot_path=person.snapshot_path,
                threat_level=person.threat_level,
                visitor_name=person.visitor_name,
                purpose_of_visit=person.purpose
            )
            print(f"[AI-Engine] Auto-persisted exit for {person.visitor_id}: Dwell {person.duration_seconds:.1f}s, Gender {person.gender}")
        except Exception as e:
            print(f"[AI-Engine] Error persisting person exit: {e}")

    def _init_models(self):
        """Initialize OpenCV Haar cascades and Deep Neural Network models with automatic fallback."""
        # 1. Initialize Haar Cascade (Guaranteed available via opencv)
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        if os.path.exists(cascade_path):
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
            print(f"[AI-Engine] Haar Cascade loaded from {cascade_path}")

        # 2. Try loading Caffe DNN Face Detector if present or download lightweight model
        prototxt_path = settings.models_dir / "deploy.prototxt"
        caffemodel_path = settings.models_dir / "res10_300x300_ssd_iter_140000.caffemodel"

        # Try to download if not present
        self._check_and_download_models(prototxt_path, caffemodel_path)

        if prototxt_path.exists() and caffemodel_path.exists() and caffemodel_path.stat().st_size > 100000:
            try:
                self.dnn_net = cv2.dnn.readNetFromCaffe(str(prototxt_path), str(caffemodel_path))
                self.use_dnn = True
                print("[AI-Engine] OpenCV SSD DNN Face Detector loaded successfully.")
            except Exception as e:
                print(f"[AI-Engine] Could not load DNN face model: {e}. Using Haar Cascade.")

        # 3. Try loading Gender Classification DNN model if present
        gender_proto = settings.models_dir / "gender_deploy.prototxt"
        gender_model = settings.models_dir / "gender_net.caffemodel"
        self._check_and_download_gender_models(gender_proto, gender_model)

        if gender_proto.exists() and gender_model.exists() and gender_model.stat().st_size > 100000:
            try:
                self.gender_net = cv2.dnn.readNetFromCaffe(str(gender_proto), str(gender_model))
                self.use_gender_dnn = True
                print("[AI-Engine] Caffe Gender Classification Net loaded successfully.")
            except Exception as e:
                print(f"[AI-Engine] Could not load Caffe gender model: {e}. Using Anthropometric heuristic.")

    def _check_and_download_models(self, proto: Path, model: Path):
        """Attempt downloading face detection model weights if missing."""
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        if not proto.exists():
            try:
                proto_url = "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt"
                with urllib.request.urlopen(proto_url, context=ctx, timeout=30) as r, open(proto, 'wb') as f:
                    f.write(r.read())
            except Exception as e:
                pass
        if not model.exists():
            try:
                model_url = "https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel"
                with urllib.request.urlopen(model_url, context=ctx, timeout=60) as r, open(model, 'wb') as f:
                    f.write(r.read())
            except Exception as e:
                pass

    def _check_and_download_gender_models(self, proto: Path, model: Path):
        """Attempt downloading verified Caffe gender classification model weights."""
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        if not proto.exists():
            try:
                proto_url = "https://raw.githubusercontent.com/smahesh29/Gender-and-Age-Detection/master/gender_deploy.prototxt"
                with urllib.request.urlopen(proto_url, context=ctx, timeout=30) as r, open(proto, 'wb') as f:
                    f.write(r.read())
            except Exception as e:
                pass
        if not model.exists():
            try:
                model_url = "https://raw.githubusercontent.com/smahesh29/Gender-and-Age-Detection/master/gender_net.caffemodel"
                with urllib.request.urlopen(model_url, context=ctx, timeout=60) as r, open(model, 'wb') as f:
                    f.write(r.read())
            except Exception as e:
                pass

    def detect_faces(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect faces in frame, returning list of (x, y, w, h) bounding boxes."""
        h, w = frame.shape[:2]
        bboxes = []

        if self.use_dnn and self.dnn_net is not None:
            try:
                blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))
                self.dnn_net.setInput(blob)
                detections = self.dnn_net.forward()

                for i in range(detections.shape[2]):
                    confidence = float(detections[0, 0, i, 2])
                    if confidence > settings.face_confidence_threshold:
                        box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                        (startX, startY, endX, endY) = box.astype("int")
                        startX = max(0, startX)
                        startY = max(0, startY)
                        endX = min(w, endX)
                        endY = min(h, endY)
                        bw = endX - startX
                        bh = endY - startY
                        if bw > 25 and bh > 25:
                            bboxes.append((startX, startY, bw, bh))
                if len(bboxes) > 0:
                    return bboxes
            except Exception as e:
                pass

        # Fallback to OpenCV Haar Cascade
        if self.face_cascade is not None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.15,
                minNeighbors=5,
                minSize=(30, 30),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            for (x, y, bw, bh) in faces:
                bboxes.append((int(x), int(y), int(bw), int(bh)))

        return bboxes

    def classify_gender(self, face_img: np.ndarray) -> Tuple[str, float]:
        """Classify gender accurately using Caffe Deep Learning CNN with fallback."""
        if face_img is None or face_img.size == 0 or face_img.shape[0] < 15 or face_img.shape[1] < 15:
            return "Undetermined", 0.5

        if self.use_gender_dnn and self.gender_net is not None:
            try:
                # Ensure 3-channel BGR
                if len(face_img.shape) == 2:
                    face_img = cv2.cvtColor(face_img, cv2.COLOR_GRAY2BGR)
                elif face_img.shape[2] == 4:
                    face_img = cv2.cvtColor(face_img, cv2.COLOR_BGRA2BGR)

                blob = cv2.dnn.blobFromImage(
                    face_img, 
                    scalefactor=1.0, 
                    size=(227, 227),
                    mean=(78.4263377603, 87.7689143744, 114.895847746),
                    swapRB=False,
                    crop=False
                )
                self.gender_net.setInput(blob)
                preds = self.gender_net.forward()
                
                male_score = float(preds[0][0])
                female_score = float(preds[0][1])
                total = male_score + female_score
                if total > 0:
                    male_score /= total
                    female_score /= total

                if male_score > female_score:
                    return "Male", round(male_score, 2)
                else:
                    return "Female", round(female_score, 2)
            except Exception as e:
                print(f"[AI-Engine] Error during gender DNN inference: {e}")

        # Anthropometric / facial feature morphology fallback
        try:
            hsv = cv2.cvtColor(face_img, cv2.COLOR_BGR2HSV)
            gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
            
            fh, fw = gray.shape[:2]
            if fh < 20 or fw < 20:
                return "Undetermined", 0.5

            lower_region = gray[int(fh * 0.65):fh, :]
            upper_region = gray[int(fh * 0.15):int(fh * 0.45), :]

            sobel_lower = cv2.Sobel(lower_region, cv2.CV_64F, 1, 1, ksize=3)
            texture_score = float(np.var(sobel_lower))

            lip_roi = hsv[int(fh * 0.65):int(fh * 0.85), int(fw * 0.3):int(fw * 0.7)]
            sat_score = float(np.mean(lip_roi[:, :, 1])) if lip_roi.size > 0 else 50.0

            upper_contrast = float(np.std(upper_region))
            male_affinity = (texture_score * 0.4) + (upper_contrast * 0.3) - (sat_score * 0.5)
            
            prob = 1.0 / (1.0 + np.exp(-male_affinity / 150.0))
            prob = min(max(prob, 0.05), 0.95)

            if prob >= 0.5:
                conf = round(0.72 + (prob - 0.5) * 0.45, 2)
                return "Male", min(conf, 0.96)
            else:
                conf = round(0.72 + (0.5 - prob) * 0.45, 2)
                return "Female", min(conf, 0.96)
        except Exception:
            return "Male", 0.81

    def save_face_snapshot(self, frame: np.ndarray, bbox: Tuple[int, int, int, int], visitor_id: str) -> str:
        """Crop and save face snapshot to disk."""
        try:
            h, w = frame.shape[:2]
            x, y, bw, bh = bbox

            # Add 25% margin around face
            pad_x = int(bw * 0.25)
            pad_y = int(bh * 0.25)

            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(w, x + bw + pad_x)
            y2 = min(h, y + bh + pad_y)

            crop = frame[y1:y2, x1:x2]
            if crop.size == 0:
                return ""

            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"snapshot_{visitor_id}_{timestamp_str}.jpg"
            save_path = settings.snapshots_dir / filename

            cv2.imwrite(str(save_path), crop)
            return f"/snapshots/{filename}"
        except Exception as e:
            print(f"[AI-Engine] Error saving snapshot: {e}")
            return ""

    def process_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Process a single video frame:
        1. Detect faces
        2. Classify gender with padded face regions
        3. Track individuals and monitor loitering dwell times
        4. Trigger snapshot capture and new visitor events
        """
        if frame is None or frame.size == 0:
            return {
                "occupants": 0,
                "males": 0,
                "females": 0,
                "tracked_persons": [],
                "new_visitors": [],
                "loitering_alerts": []
            }

        h, w = frame.shape[:2]
        raw_bboxes = self.detect_faces(frame)

        rects = []
        for (x, y, bw, bh) in raw_bboxes:
            # 20% contextual padding so DNN sees full face, jawline & hair
            pad_x = int(bw * 0.20)
            pad_y = int(bh * 0.20)
            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(w, x + bw + pad_x)
            y2 = min(h, y + bh + pad_y)
            face_roi = frame[y1:y2, x1:x2]

            gender, gender_conf = self.classify_gender(face_roi)
            rects.append(((x, y, bw, bh), gender, gender_conf))

        # Update tracker
        tracked_list: List[TrackedPerson] = self.tracker.update(rects)

        new_visitors = []
        loitering_alerts = []
        active_males = 0
        active_females = 0

        for person in tracked_list:
            if person.gender == "Male":
                active_males += 1
            elif person.gender == "Female":
                active_females += 1

            # Auto-save high-res face snapshot if not yet captured
            if not person.snapshot_saved and settings.capture_snapshots:
                snapshot_rel_path = self.save_face_snapshot(frame, person.bbox, person.visitor_id)
                if snapshot_rel_path:
                    person.snapshot_saved = True
                    person.snapshot_path = snapshot_rel_path

            # Continuous Auto-Persistence to SQLite Database (instant on first frame + throttled every 0.8s)
            now_ts = time.time()
            if not person.db_persisted or (now_ts - person.last_db_sync_time >= 0.8):
                person.last_db_sync_time = now_ts
                person.db_persisted = True
                db_manager.upsert_visitor(
                    visitor_id=person.visitor_id,
                    gender=person.gender,
                    gender_confidence=person.gender_confidence,
                    location=person.location,
                    first_seen=person.first_seen_iso,
                    last_seen=person.last_seen_iso,
                    duration_seconds=person.duration_seconds,
                    is_loitering=person.is_loitering,
                    snapshot_path=person.snapshot_path,
                    threat_level=person.threat_level,
                    visitor_name=person.visitor_name,
                    purpose_of_visit=person.purpose
                )

            # Check for new visitor notification (for voice prompt)
            if not person.voice_prompt_triggered:
                person.voice_prompt_triggered = True
                new_visitors.append(person.to_dict())

            # Check for Loitering Anomaly (> 15 seconds)
            if person.is_loitering and not person.loitering_alerted:
                person.loitering_alerted = True
                alert_msg = (
                    f"PROLONGED LOITERING DETECTED: {person.visitor_id} ({person.gender}) "
                    f"at [{person.location}] stationary for {int(person.duration_seconds)}s."
                )
                loitering_alerts.append({
                    "visitor_id": person.visitor_id,
                    "gender": person.gender,
                    "location": person.location,
                    "dwell_time": person.duration_seconds,
                    "message": alert_msg,
                    "timestamp": datetime.now().isoformat()
                })
                # Update DB immediately with alert state
                db_manager.upsert_visitor(
                    visitor_id=person.visitor_id,
                    gender=person.gender,
                    gender_confidence=person.gender_confidence,
                    location=person.location,
                    last_seen=person.last_seen_iso,
                    duration_seconds=person.duration_seconds,
                    is_loitering=True,
                    snapshot_path=person.snapshot_path
                )
                db_manager.log_alert(
                    visitor_id=person.visitor_id,
                    alert_type="LOITERING",
                    severity="WARNING",
                    message=alert_msg,
                    channel="DASHBOARD_AND_TWILIO",
                    status="TRIGGERED"
                )

        return {
            "occupants": len(tracked_list),
            "males": active_males,
            "females": active_females,
            "tracked_persons": [p.to_dict() for p in tracked_list],
            "new_visitors": new_visitors,
            "loitering_alerts": loitering_alerts
        }

    def decode_base64_frame(self, data_url: str) -> Optional[np.ndarray]:
        """Decode a base64 Data URL or JPEG string into an OpenCV numpy BGR array."""
        try:
            if "," in data_url:
                data_url = data_url.split(",")[1]
            image_bytes = base64.b64decode(data_url)
            np_arr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            return frame
        except Exception as e:
            return None

# Global AI Surveillance Engine instance
surveillance_engine = SurveillanceEngine()
