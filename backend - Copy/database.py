import sqlite3
import csv
import io
from datetime import datetime
from typing import List, Dict, Any, Optional
from backend.config import settings

class DatabaseManager:
    def __init__(self, db_path=None):
        self.db_path = str(db_path or settings.db_path)
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Create necessary database tables with indexes."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Visitors table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS visitors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visitor_id TEXT UNIQUE NOT NULL,
                gender TEXT DEFAULT 'Undetermined',
                gender_confidence REAL DEFAULT 0.0,
                location TEXT DEFAULT 'Sector A - Main Entrance',
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                duration_seconds REAL DEFAULT 0.0,
                is_loitering INTEGER DEFAULT 0,
                snapshot_path TEXT DEFAULT '',
                threat_level TEXT DEFAULT 'PENDING',
                visitor_name TEXT DEFAULT 'Anonymous',
                purpose_of_visit TEXT DEFAULT 'Unstated',
                created_at TEXT NOT NULL
            )
            """)

            # Ensure location column exists if upgrading existing DB
            try:
                cursor.execute("ALTER TABLE visitors ADD COLUMN location TEXT DEFAULT 'Sector A - Main Entrance'")
            except Exception:
                pass

            # Conversations table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visitor_id TEXT NOT NULL,
                ai_prompt TEXT NOT NULL,
                visitor_response TEXT NOT NULL,
                ai_reply TEXT NOT NULL,
                threat_assessment TEXT DEFAULT 'LOW',
                timestamp TEXT NOT NULL,
                FOREIGN KEY (visitor_id) REFERENCES visitors (visitor_id)
            )
            """)

            # Alerts table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visitor_id TEXT,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                channel TEXT NOT NULL,
                status TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """)

            # Create Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_visitors_visitor_id ON visitors(visitor_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_visitors_created_at ON visitors(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)")
            conn.commit()

    def upsert_visitor(
        self,
        visitor_id: str,
        gender: str = "Undetermined",
        gender_confidence: float = 0.0,
        location: str = "Sector A - Main Entrance",
        first_seen: str = None,
        last_seen: str = None,
        duration_seconds: float = 0.0,
        is_loitering: bool = False,
        snapshot_path: str = "",
        threat_level: str = "PENDING",
        visitor_name: str = "Anonymous",
        purpose_of_visit: str = "Unstated"
    ):
        """Insert or update visitor record."""
        now = datetime.now().isoformat()
        first_seen = first_seen or now
        last_seen = last_seen or now

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO visitors (
                visitor_id, gender, gender_confidence, location, first_seen, last_seen,
                duration_seconds, is_loitering, snapshot_path, threat_level,
                visitor_name, purpose_of_visit, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(visitor_id) DO UPDATE SET
                gender = CASE WHEN excluded.gender != 'Undetermined' THEN excluded.gender ELSE visitors.gender END,
                gender_confidence = CASE WHEN excluded.gender_confidence > 0 THEN excluded.gender_confidence ELSE visitors.gender_confidence END,
                location = CASE WHEN excluded.location != '' THEN excluded.location ELSE visitors.location END,
                last_seen = excluded.last_seen,
                duration_seconds = excluded.duration_seconds,
                is_loitering = MAX(visitors.is_loitering, excluded.is_loitering),
                snapshot_path = CASE WHEN excluded.snapshot_path != '' THEN excluded.snapshot_path ELSE visitors.snapshot_path END,
                threat_level = CASE WHEN excluded.threat_level != 'PENDING' THEN excluded.threat_level ELSE visitors.threat_level END,
                visitor_name = CASE WHEN excluded.visitor_name != 'Anonymous' THEN excluded.visitor_name ELSE visitors.visitor_name END,
                purpose_of_visit = CASE WHEN excluded.purpose_of_visit != 'Unstated' THEN excluded.purpose_of_visit ELSE visitors.purpose_of_visit END
            """, (
                visitor_id, gender, gender_confidence, location, first_seen, last_seen,
                duration_seconds, int(is_loitering), snapshot_path, threat_level,
                visitor_name, purpose_of_visit, now
            ))
            conn.commit()

    def log_conversation(
        self,
        visitor_id: str,
        ai_prompt: str,
        visitor_response: str,
        ai_reply: str,
        threat_assessment: str = "LOW"
    ) -> int:
        """Record AI voice/chat interaction transcript."""
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO conversations (visitor_id, ai_prompt, visitor_response, ai_reply, threat_assessment, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (visitor_id, ai_prompt, visitor_response, ai_reply, threat_assessment, now))
            conv_id = cursor.lastrowid
            conn.commit()
            return conv_id

    def log_alert(
        self,
        visitor_id: Optional[str],
        alert_type: str,
        severity: str,
        message: str,
        channel: str,
        status: str
    ) -> int:
        """Record security alerts (Loitering, Intrusion, Twilio SMS/WhatsApp)."""
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO alerts (visitor_id, alert_type, severity, message, channel, status, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (visitor_id or "N/A", alert_type, severity, message, channel, status, now))
            alert_id = cursor.lastrowid
            conn.commit()
            return alert_id

    def get_recent_visitors(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent visitors with their latest conversation and alert status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT 
                v.*,
                (SELECT c.visitor_response FROM conversations c WHERE c.visitor_id = v.visitor_id ORDER BY c.id DESC LIMIT 1) as latest_transcript,
                (SELECT c.ai_reply FROM conversations c WHERE c.visitor_id = v.visitor_id ORDER BY c.id DESC LIMIT 1) as latest_ai_reply,
                (SELECT a.alert_type FROM alerts a WHERE a.visitor_id = v.visitor_id ORDER BY a.id DESC LIMIT 1) as latest_alert
            FROM visitors v
            ORDER BY v.id DESC
            LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_recent_alerts(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Retrieve recent security alerts."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM alerts
            ORDER BY id DESC
            LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_stats(self) -> Dict[str, Any]:
        """Aggregate total visitors, demographics, alerts, and loitering instances."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM visitors")
            total_visitors = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM visitors WHERE gender = 'Male'")
            total_males = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM visitors WHERE gender = 'Female'")
            total_females = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM visitors WHERE is_loitering = 1")
            total_loitering = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM alerts")
            total_alerts = cursor.fetchone()[0]

            cursor.execute("SELECT AVG(duration_seconds) FROM visitors WHERE duration_seconds > 0")
            avg_dwell = cursor.fetchone()[0] or 0.0

            return {
                "total_visitors": total_visitors,
                "total_males": total_males,
                "total_females": total_females,
                "total_loitering": total_loitering,
                "total_alerts": total_alerts,
                "avg_dwell_time": round(avg_dwell, 1)
            }

    def export_csv(self) -> str:
        """Export comprehensive surveillance and visitor audit log to CSV format."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT 
                v.id,
                v.visitor_id,
                v.visitor_name,
                v.gender,
                ROUND(v.gender_confidence * 100, 1) as gender_confidence_pct,
                v.location,
                v.first_seen,
                v.last_seen,
                ROUND(v.duration_seconds, 1) as dwell_time_sec,
                CASE WHEN v.is_loitering = 1 THEN 'YES' ELSE 'NO' END as loitering_detected,
                v.threat_level,
                v.purpose_of_visit,
                (SELECT GROUP_CONCAT('AI: ' || c.ai_prompt || ' | Visitor: ' || c.visitor_response, ' ;; ') 
                 FROM conversations c WHERE c.visitor_id = v.visitor_id) as full_transcripts,
                (SELECT GROUP_CONCAT(a.alert_type || ' (' || a.channel || ' - ' || a.status || ')', ' ;; ') 
                 FROM alerts a WHERE a.visitor_id = v.visitor_id) as alert_history,
                v.snapshot_path,
                v.created_at
            FROM visitors v
            ORDER BY v.id DESC
            """)
            rows = cursor.fetchall()

            output = io.StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow([
                "Record ID",
                "Visitor ID",
                "Visitor Name",
                "Gender",
                "Gender Confidence (%)",
                "Person Location / Sector",
                "First Seen (Timestamp)",
                "Last Seen (Timestamp)",
                "Dwell Time (Seconds)",
                "Loitering Alert Triggered",
                "Threat Level Assessment",
                "Stated Purpose of Visit",
                "AI Voice Dialogue Transcripts",
                "Alert History & Notification Status",
                "Face Snapshot File Path",
                "Record Created At"
            ])

            for row in rows:
                writer.writerow(list(row))

            return output.getvalue()

# Global database manager instance
db_manager = DatabaseManager()
