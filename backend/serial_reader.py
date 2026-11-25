"""
PRIME-Factory v1.0 — Serial Reader (Real Mode)
Source: Software Constitution v1.0, Section 10 — Serial Reader (Real Mode)

Reads Arduino Serial data in a background thread.
Format: STATE,RPM,UNITS,I_A,V_V,T_C,VIB,SETPOINT
Baud: 9600
Only Arduino Uno — no ESP32, no MQTT in this phase.
"""

import serial
import threading
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List
from collections import deque


@dataclass
class SensorReading:
    """Raw data from Arduino Serial (1 Hz)."""
    timestamp: datetime
    state: str          # IDLE | RUNNING | FAULT
    rpm: float          # Actual speed from TCRT
    units: int          # Cumulative revolution count
    current_a: float    # Current from ACS712
    voltage_v: float    # Source voltage (×5 divider)
    temp_c: float       # Motor temperature (DS18B20)
    vib_rms: float      # Vibration RMS (ADXL345, gravity removed)
    setpoint_rpm: int   # Operator setpoint from Pot


class SerialReader:
    """
    Reads Arduino Serial data in a background thread.
    Format: STATE,RPM,UNITS,I_A,V_V,T_C,VIB,SETPOINT
    Baud: 9600
    """

    def __init__(self, port: str = "COM3", baud: int = 9600, buffer_size: int = 300):
        self.port = port
        self.baud = baud
        self.buffer_size = buffer_size
        self.readings: deque = deque(maxlen=buffer_size)
        self.is_connected = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._serial: Optional[serial.Serial] = None

    def start(self):
        """Start background reading thread."""
        try:
            self._serial = serial.Serial(self.port, self.baud, timeout=1)
            self.is_connected = True
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._read_loop, daemon=True)
            self._thread.start()
        except serial.SerialException as e:
            print(f"[SerialReader] Connection failed: {e}")
            self.is_connected = False

    def stop(self):
        """Stop reading thread."""
        self._stop_event.set()
        if self._serial and self._serial.is_open:
            self._serial.close()
        self.is_connected = False

    def _read_loop(self):
        """Background loop: parse lines and append to buffer."""
        while not self._stop_event.is_set():
            try:
                if self._serial and self._serial.is_open:
                    line = self._serial.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        reading = self._parse_line(line)
                        if reading:
                            self.readings.append(reading)
            except Exception as e:
                print(f"[SerialReader] Error: {e}")

    def _parse_line(self, line: str) -> Optional[SensorReading]:
        """
        Parse: STATE,RPM,UNITS,I_A,V_V,T_C,VIB,SETPOINT
        Example: RUNNING,218.5,47,0.842,11.95,42.3,0.125,220
        """
        try:
            parts = line.split(',')
            if len(parts) != 8:
                return None

            return SensorReading(
                timestamp=datetime.now(),
                state=parts[0].strip(),
                rpm=float(parts[1]),
                units=int(parts[2]),
                current_a=float(parts[3]),
                voltage_v=float(parts[4]),
                temp_c=float(parts[5]),
                vib_rms=float(parts[6]),
                setpoint_rpm=int(parts[7])
            )
        except (ValueError, IndexError):
            return None

    def get_latest(self) -> Optional[SensorReading]:
        """Get most recent reading."""
        if self.readings:
            return self.readings[-1]
        return None

    def get_last_n(self, n: int) -> List[SensorReading]:
        """Get last N readings."""
        return list(self.readings)[-n:]
