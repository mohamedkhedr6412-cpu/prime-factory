"""
PRIME-Factory — MQTT Subscriber (ESP32 gateway -> SQLite)

Subscribes to:
  - prime-factory/data   QoS 1, retain=false  (JSON telemetry from ESP32)
  - prime-factory/status QoS 1, retain=true   (ONLINE / OFFLINE + LWT)

Writes telemetry to data/factory.db -> sensor_readings, and mirrors the
retained device status into system_config['mqtt_status'].

The paho-mqtt import is intentionally lazy so the mapping helpers can be
unit-tested without the dependency installed.
"""

import calendar
import json
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from backend.serial_reader import SensorReading

GRAVITY = 9.80665  # m/s^2 -> g, for the existing PdM calculators


class MqttSubscriber:
    TOPIC_DATA = "prime-factory/data"
    TOPIC_STATUS = "prime-factory/status"
    TOPIC_CONTROL = "prime-factory/control"
    # A reading older than this is "stale" — the dashboard shows zeros/OFFLINE.
    LIVE_TIMEOUT_SEC = 5

    def __init__(self, host: Optional[str] = None, port: int = 1883,
                 client_id: Optional[str] = None,
                 db_path: str = "data/factory.db"):
        self.host = host or os.environ.get("MQTT_HOST", "192.168.100.16")
        self.port = int(port)
        # Unique per process, so two dashboards never evict each other.
        self.client_id = client_id or f"prime_dashboard_{os.getpid()}"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.is_connected = False
        self.mqtt_status = "UNKNOWN"
        self.latest: Optional[SensorReading] = None
        # Last speed command sent from this dashboard (not a hardware ack).
        self.control_mode = "LOCAL"
        self.control_speed_pct = 0
        self._lock = threading.Lock()
        self._client = None
        self._last_energy_time: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _as_float(value: Any, default: float = 0.0) -> float:
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_int(value: Any, default: int = 0) -> int:
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def normalize(cls, payload: Dict[str, Any]) -> Optional[SensorReading]:
        """Convert an ESP JSON payload into the platform's SensorReading."""
        if not isinstance(payload, dict):
            return None

        # Accept both the contract name 'current' and our ESP name 'current_a'.
        current = payload.get("current_a", payload.get("current"))
        if current is None:
            return None

        vibration_ms2 = cls._as_float(payload.get("vibration_ms2"))
        speed_pct = cls._as_int(payload.get("speed_pct"))
        status = str(payload.get("status") or "IDLE")
        control_mode = str(payload.get("control_mode") or "LOCAL").strip().upper()
        if control_mode not in ("LOCAL", "REMOTE"):
            control_mode = "LOCAL"

        return SensorReading(
            timestamp=datetime.now(),
            state=status,
            rpm=0.0,          # No RPM sensor in Phase 1 (speed_pct is available).
            units=0,          # No TCRT counter in the ESP payload yet.
            current_a=cls._as_float(current),
            voltage_v=cls._as_float(payload.get("voltage_v")),
            temp_c=cls._as_float(payload.get("temp")),  # null -> 0.0 placeholder
            vib_rms=vibration_ms2 / GRAVITY,            # g, for PdM calculators
            setpoint_rpm=0,
            speed_pct=speed_pct,
            device_id=str(payload.get("device") or "esp32_station"),
            uptime_ms=cls._as_int(payload.get("uptime_ms")),
            vibration_ms2=vibration_ms2,
            control_mode=control_mode,
            control_speed_pct=cls._as_float(payload.get("control_speed_pct")),
        )

    # ------------------------------------------------------------------
    # SQLite
    # ------------------------------------------------------------------
    def insert_reading(self, reading: SensorReading,
                       weight: Any = None, temp: Any = None) -> None:
        """Persist one normalized reading; keep weight/temp NULL when absent."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "INSERT INTO sensor_readings "
                "(timestamp, device_id, weight_g, current_a, temp_c, status, "
                " voltage_v, vibration_ms2, speed_pct, uptime_ms) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    reading.timestamp.isoformat(sep=" "),
                    reading.device_id,
                    weight,
                    reading.current_a,
                    temp,
                    reading.state,
                    reading.voltage_v,
                    reading.vibration_ms2,
                    reading.speed_pct,
                    reading.uptime_ms,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _log_energy(self, reading: SensorReading) -> None:
        """Accumulate energy between consecutive readings into energy_log.

        E(Wh) = P(W) × dt(s) / 3600. Large gaps are skipped so a disconnected
        device does not create a fake energy spike when it comes back.
        """
        now = reading.timestamp
        previous = self._last_energy_time
        self._last_energy_time = now
        if previous is None:
            return

        dt = (now - previous).total_seconds()
        power_w = reading.voltage_v * reading.current_a
        if dt <= 0 or dt > 60 or power_w <= 0.01:
            return

        energy_wh = power_w * dt / 3600.0
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "INSERT INTO energy_log "
                "(timestamp, device_id, interval_seconds, power_w, energy_wh) "
                "VALUES (?, ?, ?, ?, ?)",
                (now.isoformat(sep=" "), reading.device_id, dt,
                 power_w, energy_wh),
            )
            conn.commit()
        finally:
            conn.close()

    def handle_payload(self, payload: Dict[str, Any]) -> Optional[SensorReading]:
        # Hardware acknowledgement of the last mode/speed command, carried by
        # every telemetry packet (including duplicate republishes).
        ack_mode = str(payload.get("control_mode") or "").strip().upper()
        if ack_mode in ("LOCAL", "REMOTE"):
            with self._lock:
                self.control_mode = ack_mode
                self.control_speed_pct = int(
                    self._as_float(payload.get("control_speed_pct")))

        # ESP republishes the last sample every second with duplicate=true.
        # Ignore it so SQLite and energy_log only get genuine Arduino samples.
        if payload.get("duplicate") in (True, 1, "true", "True"):
            return None

        reading = self.normalize(payload)
        if reading is None:
            return None
        self.insert_reading(reading,
                            weight=payload.get("weight"),
                            temp=payload.get("temp"))
        self._log_energy(reading)
        with self._lock:
            self.latest = reading
        return reading

    def handle_status(self, value: Any) -> None:
        text = str(value).strip().upper()
        self.mqtt_status = text
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "INSERT OR REPLACE INTO system_config (key, value, updated_at) "
                "VALUES ('mqtt_status', ?, CURRENT_TIMESTAMP)",
                (text,),
            )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Speed control (dashboard -> MQTT -> ESP -> Arduino)
    # ------------------------------------------------------------------
    def get_control_state(self) -> Dict[str, Any]:
        """Last known control mode/speed (command or hardware ack)."""
        with self._lock:
            return {
                "mode": self.control_mode,
                "speed_pct": self.control_speed_pct,
            }

    def publish_control(self, mode: Any, speed_pct: Any) -> bool:
        """Publish MODE:L|R,SPD:0..100 as a retained QoS 1 MQTT command."""
        mode_text = ("R" if str(mode).strip().upper() in ("REMOTE", "R")
                     else "L")
        speed = int(round(self._as_float(speed_pct)))
        speed = max(0, min(100, speed))
        payload = f"MODE:{mode_text},SPD:{speed}"

        with self._lock:
            self.control_mode = "REMOTE" if mode_text == "R" else "LOCAL"
            self.control_speed_pct = speed

        if not self.is_connected or self._client is None:
            return False
        info = self._client.publish(self.TOPIC_CONTROL, payload, qos=1,
                                    retain=True)
        return getattr(info, "rc", 0) == 0

    # ------------------------------------------------------------------
    # MQTT callbacks
    # ------------------------------------------------------------------
    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        # paho 2.x passes a ReasonCode object; older versions pass an int.
        code = reason_code.value if hasattr(reason_code, "value") else reason_code
        self.is_connected = (int(code) == 0)
        client.subscribe(self.TOPIC_DATA, qos=1)
        client.subscribe(self.TOPIC_STATUS, qos=1)
        print(f"[MQTT] connected={self.is_connected} -> "
              f"{self.TOPIC_DATA}, {self.TOPIC_STATUS} (QoS 1)")

    def _on_disconnect(self, client, userdata, *args):
        self.is_connected = False
        self.mqtt_status = "OFFLINE"
        print("[MQTT] disconnected")

    def _on_message(self, client, userdata, msg):
        text = msg.payload.decode("utf-8", errors="ignore")
        if msg.topic == self.TOPIC_STATUS:
            self.handle_status(text)
            return
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return
        self.handle_payload(payload)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self):
        """Start a background MQTT loop. Non-blocking."""
        if self._client is not None:
            return self._client
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:
            raise RuntimeError(
                "paho-mqtt is required. Install it with: pip install paho-mqtt"
            ) from exc

        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.client_id,
            clean_session=True,
        )
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        client.reconnect_delay_set(min_delay=1, max_delay=30)
        client.connect_async(self.host, self.port, 60)
        client.loop_start()
        self._client = client
        return client

    def stop(self):
        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
        self.is_connected = False

    def get_latest(self) -> Optional[SensorReading]:
        with self._lock:
            return self.latest

    def get_latest_fresh(self,
                         max_age_sec: Optional[float] = None
                         ) -> Optional[SensorReading]:
        """Return the latest reading only if it arrived recently.

        This prevents the dashboard from showing an old value as if it were
        live after the ESP stops publishing.
        """
        with self._lock:
            reading = self.latest
        if reading is None:
            return None
        limit = self.LIVE_TIMEOUT_SEC if max_age_sec is None else max_age_sec
        age = (datetime.now() - reading.timestamp).total_seconds()
        if age < 0 or age > limit:
            return None
        return reading

    def get_energy_summary(self) -> Dict[str, Any]:
        """Return today/month/year energy totals plus grouped log rows."""
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        month = now.strftime("%Y-%m")
        year = now.strftime("%Y")

        conn = sqlite3.connect(str(self.db_path))
        try:
            totals = conn.execute(
                "SELECT "
                "COALESCE(SUM(CASE WHEN date(timestamp)=? THEN energy_wh ELSE 0 END),0), "
                "COALESCE(SUM(CASE WHEN strftime('%Y-%m',timestamp)=? THEN energy_wh ELSE 0 END),0), "
                "COALESCE(SUM(CASE WHEN strftime('%Y',timestamp)=? THEN energy_wh ELSE 0 END),0), "
                "COALESCE(SUM(energy_wh),0) "
                "FROM energy_log",
                (today, month, year),
            ).fetchone()

            stats = conn.execute(
                "SELECT COALESCE(SUM(interval_seconds),0), "
                "COALESCE(MAX(power_w),0), COUNT(*), "
                "MIN(timestamp), MAX(timestamp) FROM energy_log"
            ).fetchone()

            daily = conn.execute(
                "SELECT date(timestamp), SUM(energy_wh), COUNT(*) "
                "FROM energy_log GROUP BY 1 ORDER BY 1 DESC LIMIT 30"
            ).fetchall()
            monthly = conn.execute(
                "SELECT strftime('%Y-%m',timestamp), SUM(energy_wh), COUNT(*) "
                "FROM energy_log GROUP BY 1 ORDER BY 1 DESC LIMIT 12"
            ).fetchall()
            yearly = conn.execute(
                "SELECT strftime('%Y',timestamp), SUM(energy_wh), COUNT(*) "
                "FROM energy_log GROUP BY 1 ORDER BY 1 DESC"
            ).fetchall()

            # Buckets inside the *current* day/month/year. These drive the
            # period chart instead of the historical 30-day/12-month log.
            today_hourly_rows = conn.execute(
                "SELECT strftime('%H',timestamp) AS bucket, "
                "SUM(energy_wh), COUNT(*) FROM energy_log "
                "WHERE date(timestamp)=? GROUP BY bucket ORDER BY bucket",
                (today,),
            ).fetchall()
            month_daily_rows = conn.execute(
                "SELECT date(timestamp) AS bucket, "
                "SUM(energy_wh), COUNT(*) FROM energy_log "
                "WHERE strftime('%Y-%m',timestamp)=? GROUP BY bucket ORDER BY bucket",
                (month,),
            ).fetchall()
            year_monthly_rows = conn.execute(
                "SELECT strftime('%Y-%m',timestamp) AS bucket, "
                "SUM(energy_wh), COUNT(*) FROM energy_log "
                "WHERE strftime('%Y',timestamp)=? GROUP BY bucket ORDER BY bucket",
                (year,),
            ).fetchall()
        finally:
            conn.close()

        def pack(rows):
            return [
                {
                    "label": row[0],
                    "energy_wh": round(row[1] or 0.0, 6),
                    "energy_kwh": round((row[1] or 0.0) / 1000.0, 6),
                    "samples": row[2],
                }
                for row in rows
            ]

        def filled(rows, key, default_label):
            """Return a zero-valued bucket when a period has no samples."""
            row = rows.get(key)
            return (
                default_label,
                (row[1] or 0.0) if row else 0.0,
                (row[2] or 0) if row else 0,
            )

        hour_map = {row[0]: row for row in today_hourly_rows}
        day_map = {row[0]: row for row in month_daily_rows}
        month_map = {row[0]: row for row in year_monthly_rows}

        today_hourly = pack([
            filled(hour_map, f"{hour:02d}", f"{hour:02d}:00")
            for hour in range(24)
        ])
        days_in_month = calendar.monthrange(now.year, now.month)[1]
        month_daily = pack([
            filled(day_map, f"{month}-{day:02d}", f"{month}-{day:02d}")
            for day in range(1, days_in_month + 1)
        ])
        year_monthly = pack([
            filled(month_map, f"{year}-{month_no:02d}",
                   f"{year}-{month_no:02d}")
            for month_no in range(1, 13)
        ])

        runtime_seconds = float(stats[0] or 0.0)
        peak_power_w = float(stats[1] or 0.0)
        energy_samples = int(stats[2] or 0)

        # Duty cycle = accumulated ON time / whole logged window. The window
        # includes idle intervals because energy_log only stores ON intervals.
        monitored_seconds = 0.0
        if stats[3] and stats[4]:
            try:
                start = datetime.fromisoformat(str(stats[3]))
                end = datetime.fromisoformat(str(stats[4]))
                monitored_seconds = max(0.0, (end - start).total_seconds())
            except ValueError:
                monitored_seconds = runtime_seconds
        duty_pct = (
            min(100.0, runtime_seconds / monitored_seconds * 100.0)
            if monitored_seconds > 0 else 0.0
        )

        return {
            "today_wh": round(totals[0] or 0.0, 6),
            "month_wh": round(totals[1] or 0.0, 6),
            "year_wh": round(totals[2] or 0.0, 6),
            "total_wh": round(totals[3] or 0.0, 6),
            "runtime_seconds": round(runtime_seconds, 3),
            "runtime_hours": round(runtime_seconds / 3600.0, 6),
            "peak_power_w": round(peak_power_w, 3),
            "duty_pct": round(duty_pct, 2),
            "energy_samples": energy_samples,
            "daily": pack(daily),
            "monthly": pack(monthly),
            "yearly": pack(yearly),
            "today_hourly": today_hourly,
            "month_daily": month_daily,
            "year_monthly": year_monthly,
        }
