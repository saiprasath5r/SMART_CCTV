import time
import math
from collections import OrderedDict
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from backend.config import settings

class TrackedPerson:
    def __init__(self, obj_id: int, bbox: Tuple[int, int, int, int], gender: str, gender_conf: float):
        self.obj_id = obj_id
        self.visitor_id = f"VISITOR-{obj_id:03d}"
        self.bbox = bbox  # (x, y, w, h)
        self.centroid = self._calc_centroid(bbox)
        
        self.first_seen_time = time.time()
        self.last_seen_time = self.first_seen_time
        self.first_seen_iso = datetime.now().isoformat()
        self.last_seen_iso = self.first_seen_iso
        
        self.disappeared = 0
        self.duration_seconds = 0.0
        
        # Flags
        self.is_loitering = False
        self.loitering_alerted = False
        self.snapshot_saved = False
        self.snapshot_path = ""
        self.voice_prompt_triggered = False
        self.interrogation_completed = False
        
        # Gender smoothing
        self.gender_votes = [(gender, gender_conf)]
        self.gender = gender
        self.gender_confidence = gender_conf
        
        # Profile details
        self.visitor_name = "Anonymous"
        self.purpose = "Unstated"
        self.threat_level = "PENDING"
        self.location = self._calc_sector(self.centroid)
        self.db_persisted = False
        self.last_db_sync_time = 0.0

    def _calc_centroid(self, bbox: Tuple[int, int, int, int]) -> Tuple[int, int]:
        x, y, w, h = bbox
        return (int(x + w / 2.0), int(y + h / 2.0))

    def _calc_sector(self, centroid: Tuple[int, int]) -> str:
        cx, cy = centroid
        # Categorize into sectors based on 640x360 coordinates
        if cx < 213:
            zone_x = "West Corridor"
        elif cx < 426:
            zone_x = "Main Entrance"
        else:
            zone_x = "East Wing"

        if cy < 180:
            zone_y = "Sector A (North)"
        else:
            zone_y = "Sector B (South)"

        return f"{zone_y} - {zone_x}"

    def update(self, bbox: Tuple[int, int, int, int], gender: str, gender_conf: float):
        self.bbox = bbox
        self.centroid = self._calc_centroid(bbox)
        self.location = self._calc_sector(self.centroid)
        self.last_seen_time = time.time()
        self.last_seen_iso = datetime.now().isoformat()
        self.duration_seconds = self.last_seen_time - self.first_seen_time
        self.disappeared = 0

        # Update gender smoothing (window of 15 frames with confidence weighting)
        if len(self.gender_votes) >= 15:
            self.gender_votes.pop(0)
        self.gender_votes.append((gender, gender_conf))
        
        male_score = sum(conf for g, conf in self.gender_votes if g == "Male")
        female_score = sum(conf for g, conf in self.gender_votes if g == "Female")
        total_score = male_score + female_score

        if male_score > female_score:
            self.gender = "Male"
            self.gender_confidence = round(male_score / max(1e-5, total_score), 2)
        elif female_score > male_score:
            self.gender = "Female"
            self.gender_confidence = round(female_score / max(1e-5, total_score), 2)
        else:
            self.gender = gender
            self.gender_confidence = gender_conf

        # Check loitering threshold
        if self.duration_seconds >= settings.loitering_threshold_seconds:
            self.is_loitering = True

    def to_dict(self) -> Dict[str, Any]:
        x, y, w, h = self.bbox
        return {
            "obj_id": self.obj_id,
            "visitor_id": self.visitor_id,
            "bbox": [int(x), int(y), int(w), int(h)],
            "centroid": [int(self.centroid[0]), int(self.centroid[1])],
            "gender": self.gender,
            "gender_confidence": round(float(self.gender_confidence), 2),
            "dwell_time": round(float(self.duration_seconds), 1),
            "is_loitering": self.is_loitering,
            "loitering_alerted": self.loitering_alerted,
            "snapshot_path": self.snapshot_path,
            "voice_prompt_triggered": self.voice_prompt_triggered,
            "threat_level": self.threat_level,
            "visitor_name": self.visitor_name,
            "purpose": self.purpose,
            "location": self.location
        }


class CentroidTracker:
    def __init__(self, max_disappeared: int = 30, max_distance: float = 120.0, on_deregister=None):
        self.next_object_id = 1
        self.objects: Dict[int, TrackedPerson] = OrderedDict()
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance
        self.on_deregister = on_deregister

    def register(self, bbox: Tuple[int, int, int, int], gender: str, gender_conf: float) -> TrackedPerson:
        person = TrackedPerson(self.next_object_id, bbox, gender, gender_conf)
        self.objects[self.next_object_id] = person
        self.next_object_id += 1
        return person

    def deregister(self, object_id: int):
        if object_id in self.objects:
            person = self.objects[object_id]
            if self.on_deregister:
                try:
                    self.on_deregister(person)
                except Exception as e:
                    print(f"[Tracker] Error in on_deregister callback: {e}")
            del self.objects[object_id]

    def update(self, rects: List[Tuple[Tuple[int, int, int, int], str, float]]) -> List[TrackedPerson]:
        """
        rects: List of tuples -> ((x, y, w, h), gender, gender_confidence)
        Returns list of active tracked persons in current frame.
        """
        if len(rects) == 0:
            for object_id in list(self.objects.keys()):
                self.objects[object_id].disappeared += 1
                if self.objects[object_id].disappeared > self.max_disappeared:
                    self.deregister(object_id)
            return list(self.objects.values())

        # If no tracked objects yet, register all
        if len(self.objects) == 0:
            for bbox, gender, conf in rects:
                self.register(bbox, gender, conf)
            return list(self.objects.values())

        # Compute centroids of input rects
        input_centroids = []
        for bbox, _, _ in rects:
            x, y, w, h = bbox
            input_centroids.append((int(x + w / 2.0), int(y + h / 2.0)))

        object_ids = list(self.objects.keys())
        object_centroids = [self.objects[oid].centroid for oid in object_ids]

        # Compute pairwise euclidean distances
        distances = []
        for i, (ocx, ocy) in enumerate(object_centroids):
            row = []
            for j, (icx, icy) in enumerate(input_centroids):
                dist = math.hypot(ocx - icx, ocy - icy)
                row.append((dist, i, j))
            distances.extend(row)

        distances.sort(key=lambda item: item[0])

        used_objects = set()
        used_inputs = set()

        for dist, obj_idx, inp_idx in distances:
            if obj_idx in used_objects or inp_idx in used_inputs:
                continue

            if dist > self.max_distance:
                continue

            obj_id = object_ids[obj_idx]
            bbox, gender, conf = rects[inp_idx]
            self.objects[obj_id].update(bbox, gender, conf)

            used_objects.add(obj_idx)
            used_inputs.add(inp_idx)

        # Handle unmatched existing objects (disappeared)
        for i, obj_id in enumerate(object_ids):
            if i not in used_objects:
                self.objects[obj_id].disappeared += 1
                if self.objects[obj_id].disappeared > self.max_disappeared:
                    self.deregister(obj_id)

        # Handle unmatched new inputs (register new person)
        for j in range(len(rects)):
            if j not in used_inputs:
                bbox, gender, conf = rects[j]
                self.register(bbox, gender, conf)

        return list(self.objects.values())
