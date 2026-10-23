import paho.mqtt.client as mqtt
import json
import time
import random
import sys
import signal
from datetime import datetime

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_CLIENT_ID = "mock_esp32_station"
TOPIC_DATA = "prime-factory/data"
TOPIC_STATUS = "prime-factory/status"

VALID_MODES = ["normal", "clog", "high_temp", "overweight", "brownout"]

class MockState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.state = "IDLE"
        self.uptime_ms = 0
        self.weight = 0.0
        self.current = 0.0
        self.temp = 25.0
        self.motor_current = 0.0
        self.servo_angle = 0
        self.error = None
        self.cycle_elapsed_ms = 0

    def to_payload(self):
        return {
            "device": "esp32_station",
            "uptime_ms": self.uptime_ms,
            "weight": round(self.weight, 2),
            "current": round(self.current, 3),
            "temp": round(self.temp, 1),
            "status": self.state,
            "error": self.error,
            "motor_current": round(self.motor_current, 3),
            "servo_angle": self.servo_angle,
        }

def tick_normal(s, elapsed_ms):
    if s.state == "IDLE":
        s.weight = 0.0
        s.current = 0.05
        s.motor_current = 0.0
        s.servo_angle = 0
        s.temp = 25.0 + random.uniform(-0.5, 0.5)
        s.error = None
        if elapsed_ms > 1000:
            s.state = "FILLING"
            s.cycle_elapsed_ms = 0

    elif s.state == "FILLING":
        s.cycle_elapsed_ms += 1000
        progress = min(s.cycle_elapsed_ms / 8000.0, 1.0)
        s.weight = 95.0 * progress + random.uniform(-0.3, 0.3)
        s.current = 0.85 + random.uniform(-0.05, 0.05)
        s.motor_current = 0.65 + random.uniform(-0.03, 0.03)
        s.servo_angle = 90
        s.temp = min(42.0 + random.uniform(-0.3, 0.3), 45.0)
        if s.cycle_elapsed_ms >= 8000:
            s.state = "SETTLING"
            s.cycle_elapsed_ms = 0

    elif s.state == "SETTLING":
        s.cycle_elapsed_ms += 1000
        s.weight = 95.0 + min(5.0, s.cycle_elapsed_ms * 10.0) + random.uniform(-0.2, 0.2)
        s.current = 0.1 + random.uniform(-0.02, 0.02)
        s.motor_current = 0.0
        s.servo_angle = 0
        if s.cycle_elapsed_ms >= 500:
            s.state = "COMPLETE"
            s.cycle_elapsed_ms = 0

    elif s.state == "COMPLETE":
        s.cycle_elapsed_ms += 1000
        s.weight = 100.0 + random.uniform(-0.5, 0.5)
        s.current = 0.05
        s.motor_current = 0.0
        if s.cycle_elapsed_ms >= 2500:
            s.reset()

def tick_clog(s, elapsed_ms):
    tick_normal(s, elapsed_ms)
    if s.state == "FILLING" and s.weight > 30.0:
        s.current = 2.8 + random.uniform(-0.1, 0.1)
        s.error = "CLOG"

def tick_high_temp(s, elapsed_ms):
    tick_normal(s, elapsed_ms)
    s.temp = 72.0 + random.uniform(-1.0, 1.0)

def tick_overweight(s, elapsed_ms):
    tick_normal(s, elapsed_ms)
    if s.state == "FILLING":
        s.weight = s.weight + 25.0
        if s.weight > 110.0:
            s.error = "OVERWEIGHT"
    if s.state == "COMPLETE":
        s.weight = 125.0 + random.uniform(-1.0, 1.0)

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"[MQTT] Connected to {MQTT_BROKER}:{MQTT_PORT}")
        client.publish(TOPIC_STATUS, "ONLINE", qos=1, retain=True)
    else:
        print(f"[MQTT] Connection failed: {reason_code}")

def on_disconnect(client, userdata, flags, reason_code, properties):
    print(f"[MQTT] Disconnected (reason: {reason_code})")

def main():
    if len(sys.argv) < 2 or sys.argv[1].lower() not in VALID_MODES:
        print(f"Usage: python mock_publisher.py <mode>")
        print(f"Modes: {', '.join(VALID_MODES)}")
        sys.exit(1)

    mode = sys.argv[1].lower()
    print("=" * 60)
    print(f"PRIME-Factory Mock Publisher - Mode: {mode.upper()}")
    print("=" * 60)

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=MQTT_CLIENT_ID,
        clean_session=True,
    )
    client.will_set(TOPIC_STATUS, "OFFLINE", qos=1, retain=True)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    except ConnectionRefusedError:
        print(f"\nERROR: Cannot connect to {MQTT_BROKER}:{MQTT_PORT}. Is broker running?")
        sys.exit(1)

    client.loop_start()

    state = MockState()
    start_time = time.time()
    last_tick = time.time()
    last_brownout = time.time()

    def signal_handler(sig, frame):
        print("\n\n[SHUTDOWN] Stopping Mock Publisher...")
        client.publish(TOPIC_STATUS, "OFFLINE", qos=1, retain=True)
        time.sleep(0.2)
        client.loop_stop()
        client.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    print(f"\n{'Time':<10} {'Status':<12} {'Weight':<10} {'Current':<10} {'Temp':<8} {'Error':<10}")
    print("-" * 70)

    while True:
        now = time.time()

        if mode == "brownout" and (now - last_brownout > 30.0):
            print("\n[BROWNOUT] Simulating connection loss...")
            client.publish(TOPIC_STATUS, "OFFLINE", qos=1, retain=True)
            time.sleep(0.3)
            client.disconnect()
            time.sleep(5.0)
            try:
                client.reconnect()
                client.publish(TOPIC_STATUS, "ONLINE", qos=1, retain=True)
            except Exception as e:
                print(f"[BROWNOUT] Reconnect failed: {e}")
            last_brownout = time.time()

        if now - last_tick >= 1.0:
            elapsed_ms = int((now - start_time) * 1000)
            state.uptime_ms = elapsed_ms

            if mode == "normal": tick_normal(state, elapsed_ms)
            elif mode == "clog": tick_clog(state, elapsed_ms)
            elif mode == "high_temp": tick_high_temp(state, elapsed_ms)
            elif mode == "overweight": tick_overweight(state, elapsed_ms)
            elif mode == "brownout": tick_normal(state, elapsed_ms)

            payload = state.to_payload()
            json_str = json.dumps(payload)

            try:
                client.publish(TOPIC_DATA, json_str, qos=1)
            except Exception as e:
                print(f"[WARN] Publish exception: {e}")

            t_str = datetime.now().strftime("%H:%M:%S")
            print(f"{t_str:<10} {state.state:<12} {state.weight:>7.2f}g  {state.current:>6.2f}A  {state.temp:>5.1f}C  {(state.error or ''):<10}")

            last_tick = now

        time.sleep(0.05)

if __name__ == "__main__":
    main()