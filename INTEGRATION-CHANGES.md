# PRIME-Factory — Track B Integration Changes

**Date:** 2026-11-25  
**Scope:** Adapt the existing Dash platform from direct Arduino Serial to the ESP32 → MQTT → SQLite path.  
**Arduino and ESP firmware were later modified only to speed up telemetry (see section 9). GitHub was NOT touched.**

---

## 1) Files removed from this working copy

These were committed artifacts from the old version and must not be part of the repository:

- `data/factory.db`
- `data/factory.db-shm`
- `data/factory.db-wal`
- `data/cache/real_mode_cache.db`
- `__pycache__/`
- `backend/__pycache__/`
- `firmware/__pycache__/`

A fresh `data/factory.db` was then generated locally with `python init_db.py`.

---

## 2) Files modified

### `.gitignore`
Added recursive rules so nested DB files cannot be committed again:

```gitignore
data/**/*.db
data/**/*.db-journal
data/**/*.db-wal
data/**/*.db-shm
```

### `config/schema.sql`
Extended `sensor_readings` with the fields our ESP actually publishes:

```sql
voltage_v      REAL,
vibration_ms2  REAL,
speed_pct      INTEGER,
uptime_ms      INTEGER
```

Added a new `energy_log` table for accumulated motor consumption:

```sql
CREATE TABLE IF NOT EXISTS energy_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    device_id        TEXT NOT NULL DEFAULT 'esp32_station',
    interval_seconds REAL NOT NULL,
    power_w          REAL NOT NULL,
    energy_wh        REAL NOT NULL
);
```

`init_db.py` now expects/creates 5 tables (the 4 original ones plus `energy_log`).

### `backend/serial_reader.py`
- `SensorReading` gained four optional fields (with defaults, so old serial code still works):
  `speed_pct`, `device_id`, `uptime_ms`, `vibration_ms2`.
- `import serial` is now optional; only the legacy `SerialReader.start()` requires pyserial.

### `requirements.txt`
Added:

```text
paho-mqtt>=2.1.0
```

### `app.py`
- The dashboard is now split into URL-based pages: `/` (Home), `/real` (Real Hardware Monitor) and `/simulation` (Industrial Simulation). Only the selected model's components are rendered.
- Real Mode now reads from `MqttSubscriber` instead of `SerialReader`.
- Status badge reflects the retained MQTT status / connection state only: `ONLINE` / `OFFLINE` / `CONNECTING`. It no longer turns red just because no data packet arrived in the last 5 seconds.
- Added `data-freshness-hint` beside the badge: `No data received yet`, `Live data • just now`, or `Waiting for new data • last Xs ago`.
- KPI label changed from `RPM` to `Speed (%)` because Phase 1 publishes a percentage, not RPM.
- Vibration KPI/chart now display raw `m/s²` to match the sensor screen; the `g` conversion is kept internally for PdM only.
- Charts and calculators still use only FRESH readings (latest 5 s). KPI cards display the newest received reading so the monitor never looks empty; the freshness hint clearly marks it as live or old, so a stale value is never presented as live. The badge remains `ONLINE` while MQTT/LWT says the device is connected.
- Each MQTT reading is buffered/cached once only; stale readings are never re-saved.
- Charts no longer fall back to old SQLite cache rows; they show only the last 60 s of live in-memory readings.
- Real Mode now has an **Energy Consumption Log** card with a **Show period** selector (Today / This month / This year). Only the chosen period is displayed: its total (kWh, 6 decimals, with Wh sublabel), cost and sample count. The Plotly bar chart shows consumption **inside** the chosen period (hourly today, daily this month, monthly this year), and the table/CSV contain the same selected buckets. Peak power, run time and duty cycle remain global logged statistics; the print/PDF button isolates only this card.
- Home-page description and empty-chart message updated for MQTT.
- `debug`/reloader disabled so only one MQTT subscriber process runs (otherwise two clients with the same id keep disconnecting each other).
- Simulation Mode was not changed.

### `README.md`
Real Mode description, structure, prerequisites and run instructions updated for MQTT/Mosquitto.

---

## 3) Files added

### `backend/mqtt_subscriber.py`
- Subscribes to:
  - `prime-factory/data` — QoS 1, retain=false
  - `prime-factory/status` — QoS 1, retained, ONLINE/OFFLINE + LWT
- Connects to `MQTT_HOST` (default `192.168.100.16:1883`).
- Parses JSON and maps it to `SensorReading`.
- Writes telemetry to `data/factory.db` → `sensor_readings`.
- Accumulates energy into `data/factory.db` → `energy_log` using `E(Wh) = V × I × Δt / 3600`; gaps > 60 s are skipped to avoid fake spikes after a disconnect.
- `get_energy_summary()` returns today/month/year/all-time Wh (the UI converts to kWh), grouped DAY/MONTH/YEAR rows, plus `runtime_seconds`, `runtime_hours`, `peak_power_w`, `duty_pct` and `energy_samples`.
- Writes device status to `system_config['mqtt_status']`.
- Uses a non-blocking background loop with automatic reconnect.
- `get_latest_fresh()` returns the latest reading only if it arrived within `LIVE_TIMEOUT_SEC = 5`; older readings are treated as stale.
- `paho-mqtt` is imported lazily so mapping helpers can be tested without it.

---

## 4) Field mapping (ESP JSON → SQLite)

| ESP JSON | Destination |
|---|---|
| `device` | `device_id` |
| `uptime_ms` | `uptime_ms` |
| `voltage_v` | `voltage_v` |
| `current_a` | `current_a` (also accepts `current`) |
| `vibration_ms2` | `vibration_ms2` in SQLite and on the dashboard (m/s²); `vib_rms_g = vibration_ms2 / 9.80665` kept internally for PdM |
| `speed_pct` | `speed_pct` and the `Speed (%)` KPI |
| `weight` | `weight_g` (NULL until sensor exists) |
| `temp` | `temp_c` (NULL in DB; 0.0 placeholder for calculators) |
| `status` | `status` (currently `IDLE`) |
| `error` | logged in `anomalies` only when non-null (no action yet) |
| `motor_current`, `servo_angle` | NULL until sensors exist |

Energy is derived from consecutive readings: `power_w = voltage_v × current_a`, `energy_wh = power_w × Δt / 3600`, stored in `energy_log`.

`rpm`, `units` and `setpoint_rpm` remain `0` because the ESP payload does not carry them. MES/EMS/PdM code therefore runs safely but its RPM/units-based values are placeholders until those sensors are added.

---

## 5) Verification performed

- `python init_db.py` → 5 required tables created (`sensor_readings`, `production_units`, `anomalies`, `system_config`, `energy_log`), 8 config rows, 0 readings.
- Schema columns confirmed: `voltage_v`, `vibration_ms2`, `speed_pct`, `uptime_ms` present.
- `python -m py_compile app.py backend/*.py init_db.py lwt_probe.py` → OK.
- Offline mapping test → row inserted with correct values; `temp_g`/`weight_g` stayed NULL.
- Live MQTT test through Mosquitto at `127.0.0.1:1883`:
  - subscriber connected, subscribed QoS 1 to both topics;
  - telemetry JSON was received and stored;
  - `system_config['mqtt_status']` became `ONLINE`.
- Retained-status test:
  - retained `OFFLINE` published before subscribe → subscriber read `OFFLINE` on connect;
  - later `ONLINE` → updated to `ONLINE` in memory and SQLite.
- Native Python test (installed Python 3.15.2 from python.org):
  - `pip install -r requirements.txt` succeeded, including `pandas` and `numpy`.
  - `app.py` imported and the Dash server started at `http://127.0.0.1:8050`.
  - Browser test: clicked **Enter Real Mode**; badge showed `🟢 ONLINE`, KPIs showed `IDLE`, `Speed (%) = 67`, `Current = 0.800`, `Voltage = 12.1`, and two graphs rendered.
  - 12 sample MQTT messages were stored in `sensor_readings`; 15 rows were written to `data/cache/real_mode_cache.db`.
- Bug found and fixed during this test: `debug=True` made Dash spawn an extra process, and both used the same MQTT client id (`prime_dashboard`), so they disconnected each other. Fixed by using a per-process client id (`prime_dashboard_<pid>`) and running the server with `debug=False, use_reloader=False`.
- Live-only / units update re-tested:
  - Freshness test: a just-arrived reading was accepted; a 10-second-old reading was rejected.
  - Browser after reload showed the label `Vibration (m/s²)` and live ESP values (Voltage ≈ 11.6–11.7 V, Current 0.000 A, Speed 0, Vibration 0.000 m/s²) with `🟢 ONLINE`.
  - The real ESP was publishing continuously; its readings replaced the earlier sample messages on the dashboard.
- Energy log tested:
  - Offline calculation test: 30 synthetic intervals at 10 V × 1 A × 60 s produced exactly `5.0 Wh = 0.005 kWh`, stored as 30 `energy_log` rows.
  - Live MQTT test: four 10 V / 1 A messages published to `prime-factory/data`; `energy_log` received 4 rows (~0.010 Wh total).
  - Browser after reload showed `Today / This month / This year = 0.000010 kWh` and table rows `DAY 2026-11-25`, `MONTH 2026-11`, `YEAR 2026` with 4 samples each.
  - With the real motor idle (`I = 0.000 A`), no new energy is accumulated — correct behaviour.
  - The 4 synthetic test rows were removed afterwards; later live ESP readings accumulated normally in `energy_log`.
- Page split tested in the browser:
  - `/` showed only the two model buttons; neither real KPIs nor simulation dropdowns existed.
  - `/real` showed only Real Hardware Monitor, KPIs/charts and the Energy Consumption Log; simulation controls were absent.
  - `/simulation` showed only the simulator controls/graphs; real KPIs and energy cards were absent.
  - Both **Back to Home** and simulation **Home** links returned to `/`.
- Energy log enhancements tested:
  - `python -m py_compile app.py backend/mqtt_subscriber.py init_db.py` → OK.
  - Offline calculation test: 31 intervals × 60 s at 10 W produced `today_wh=5.166667`, `runtime_hours=0.516667`, `peak_power_w=10.0`, `duty_pct=77.5`, `energy_samples=31` and 1 daily row.
  - Bug fixed: `dbc.Input` had an unsupported `bs_size` argument, which prevented the Real page from building; changed to `size="sm"`.
  - Bug fixed: chart title used the summary key (`"monthly"`) instead of the selected period, producing `Monthl`/shortened titles; it now uses the selected DAY/MONTH/YEAR label and categorical x-axis labels.
  - Browser check on `/real`: Wh sublabels, tariff input, period dropdown, peak/runtime/duty, chart, table and both buttons were present; console errors were empty.
  - Tariff test: setting 5 EGP/kWh changed today's cost from `0.0000 EGP` to `0.0003 EGP` and the table's Cost column to match.
  - Period test: selecting Monthly changed the chart title to `Energy per Month` and the x-axis title to `Month`.
  - CSV export produced `energy_report_20261125_2342.csv` with columns `Type, Period, Energy (kWh), Energy (Wh), Samples, Cost (5.00 EGP/kWh)` and the same three breakdown rows as the table.
  - Print callback test: clicking `🖨️ Print / Save PDF` called `window.print()` once; print CSS in `assets/custom.css` shows only `.energy-report-card` and hides controls.

---

## 6) Notes for you

- **Do not copy any `.db` file to GitHub.** Recreate it with `python init_db.py` on your machine.
- **Do not replace your whole repo directory** with this folder (this copy came from a ZIP and has no `.git`). Copy the changed files over your existing clone, then commit.
- `paho-mqtt` is now required; install with `pip install -r requirements.txt`.
- `pandas` and `numpy` remain in `requirements.txt` but are not imported by `app.py`. They installed normally on native Python 3.15.2 during the final test.
- The local DB currently contains live MQTT readings (including real `energy_log` rows accumulated by the running ESP), not synthetic test rows. To reset locally: stop the server, delete `data/factory.db` and `data/cache/real_mode_cache.db`, then run `python init_db.py`. Never commit `.db` files.

---

## 7) Badge / data-freshness fix (connection state separated from telemetry age)

Problem: the ESP was connected and the retained status was `ONLINE`, but the badge sometimes showed `OFFLINE`. The ESP publishes data only about every 48 s in IDLE, while `get_latest_fresh()` rejects readings older than 5 s. The old callback returned `OFFLINE` as soon as there was no fresh reading, before it checked the MQTT status.

Fix in `app.py`:
- Added `_mqtt_connection_badge()` — badge comes only from `mqtt_subscriber.is_connected` and `mqtt_status`.
- Added `_data_freshness_hint()` — uses the newest reading's age to explain whether KPI data is live or waiting.
- Added `data-freshness-hint` to the Real Mode layout and to `update_real_kpis()` outputs.
- KPI values still reset to `0` after `LIVE_TIMEOUT_SEC = 5`; no old reading is presented as live.

Verification on `http://127.0.0.1:8050/real`:
- Immediately after restart: badge `🟢 ONLINE`, hint `No data received yet`, KPIs `0` (MQTT status retained, no new telemetry yet).
- On the next real ESP packet: badge stayed `🟢 ONLINE`, hint `Live data • just now`, voltage `11.6`.
- After the 5 s freshness window: badge stayed `🟢 ONLINE`, hint changed to `Last reading Xs ago • waiting for new data` (yellow), and the KPI voltage stayed visible at `11.6` instead of resetting to `0` (see section 8).
- Published retained `OFFLINE` to `prime-factory/status`: badge changed to `🔴 OFFLINE` immediately.
- Restored retained `ONLINE`: badge changed back to `🟢 ONLINE`; final retained value and `system_config['mqtt_status']` are both `ONLINE`.
- Browser console errors in the refreshed test tab were empty, and all captured `/_dash-update-component` calls from that tab returned 200.
- Any old Real Mode tab left open from before the restart keeps posting the previous callback signature; hard-refresh those tabs after updating `app.py`.

---

## 8) Monitor values disappearing between MQTT packets

Problem: the ESP sends data only every ~48–54 s in IDLE, but `LIVE_TIMEOUT_SEC = 5` made the KPI cards reset to `0` for ~45 s after each packet. The broker, retained status and SQLite rows were all correct; only the monitor display looked empty.

Fix in `app.py`:
- `update_real_kpis()` now reads `get_latest()` for the KPI values, so the newest reading stays visible.
- `get_latest_fresh()` is still used for buffering/cache writes and calculator updates, so a stale reading is never saved twice or treated as live.
- `_data_freshness_hint()` now returns text **and** a class: green `Live data • just now`, yellow `Last reading Xs ago • waiting for new data`, grey `No data received yet`.
- Added `Output("data-freshness-hint", "className")` to the callback.
- Calculator updates now happen only when a genuinely new fresh timestamp arrives.

Result: the monitor always shows the last values (e.g. `11.6 V`, `0.000 A`) and clearly says whether they are live or how old they are. Charts remain live-only (≤5 s) as before.

---

## 9) Telemetry speed fix (firmware + duplicate guard)

Problem: readings reached the dashboard only every ~46–54 s. The Dash polls every 1 s and the ESP publishes immediately, so the delay was in the Arduino/serial source and in blocking sensor sampling.

### `Project-coding/Arduino-Main/Project-main/Project-main.ino`
- `CURRENT_SAMPLES` reduced from `300` to `40` and `VIBRATION_SAMPLES` from `50` to `12`; sample delays reduced from `2 ms` to `1 ms` for vibration.
- `sendTelemetry()` is now called **before** `readSensors()` in `loop()`, so the 1 s telemetry tick is never delayed by ADC/I²C sampling.
- `TELEMETRY_INTERVAL_MS` remains `1000 ms`.
- Must be re-uploaded to the Arduino board.

### `Project-coding/ESP-Main/project-auxiliary/project-auxiliary.ino`
- Added `REPUBLISH_MS = 1000` and `FRESH_SAMPLE_MS = 3500`.
- `publishTelemetry(bool duplicate = false)` now adds `"duplicate": true|false` to the JSON.
- Every 1 s, while the last Arduino sample is still younger than `FRESH_SAMPLE_MS`, the ESP republishes the last sample with `duplicate: true` as a fallback.
- `lastPublishTime` was added and initialized in `setup()`.
- Must be re-uploaded to the ESP32-S3.

### `backend/mqtt_subscriber.py`
- `handle_payload()` ignores messages with `duplicate: true`; they are not inserted into `sensor_readings` and do not call `_log_energy()`. This prevents double counting while keeping the MQTT topic active for other consumers.

### Verification
- `arduino-cli compile --fqbn arduino:avr:nano` → OK.
- `arduino-cli compile --fqbn esp32:esp32:esp32s3` → OK.
- `python -m py_compile app.py backend/mqtt_subscriber.py init_db.py` → OK.
- Duplicate test: two fresh payloads + one `duplicate:true` payload produced 2 `sensor_readings` rows, 1 `energy_log` row, and `handle_payload()` returned `None` for the duplicate.

---

## 10) Energy log: select one period and chart inside it

### `backend/mqtt_subscriber.py`
- `get_energy_summary()` now also returns `today_hourly` (24 buckets), `month_daily` (all days of the current month) and `year_monthly` (12 months of the current year).
- Buckets with no samples are kept with zero energy so the chart shows the whole active day/month/year instead of only non-empty dates.
- Existing `daily`, `monthly`, `yearly` and today/month/year totals remain unchanged for compatibility.

### `app.py`
- Replaced the always-visible Today / Month / Year / Cost tiles with a **Show period** radio selector (`TODAY`, `MONTH`, `YEAR`).
- Added `energy-summary`: only the selected period's kWh total, Wh sublabel, cost and logged-interval count are displayed.
- Removed the old `Chart period` dropdown; the chart, table, title and CSV now all follow the selected period.
- `_energy_chart()` plots Wh **inside** the selected period: by hour today, by day this month, by month this year.
- `export_energy_csv()` exports the selected buckets and names the file `energy_report_<view>_<timestamp>.csv`.
- Peak power, run time and duty cycle remain global statistics from all logged samples.

### Verification
- `python -m py_compile app.py backend/mqtt_subscriber.py init_db.py` → OK.
- Backend bucket test: 24 hourly, 30 daily and 12 monthly buckets; non-empty buckets matched the inserted rows and zero buckets had `0` samples.
- Browser on `/real`:
  - `Today` → 24 hourly bars and `HOUR` table rows.
  - `This month` → 30 daily bars and `DAY` table rows.
  - `This year` → 12 monthly bars and `MONTH` table rows.
  - CSV export produced `energy_report_year_YYYYMMDD_HHMM.csv` with the same 12 monthly rows as the table.
  - Browser console remained empty of errors.
- Dash was restarted after the callback change; old tabs must be hard-refreshed.
- No commit, push or remote change was made.

---

## 11) Platform speed control — LOCAL / REMOTE

### Protocol
- New retained QoS 1 topic: `prime-factory/control`, payload `MODE:L|R,SPD:0..100`.
- `L` = Arduino potentiometer (LOCAL); `R` = dashboard speed (REMOTE).
- Telemetry now carries `control_mode` (`LOCAL`/`REMOTE`) and `control_speed_pct` as a hardware acknowledgement. Old telemetry without these fields is still accepted and treated as LOCAL.

### `Project-main.ino` (Arduino Nano)
- Non-blocking `handleControlCommand()` parses commands from `Serial` (ESP on RX).
- `updateMotorPwm()` uses the potentiometer in LOCAL and the last valid remote speed in REMOTE.
- `sendTelemetry()` appends `,MODE:L|R`; OLED shows `SPD:<n>% LOC/REM`.
- Commands are applied immediately while the motor is running.

### `project-auxiliary.ino` (ESP32-S3)
- Subscribes to `prime-factory/control` with QoS 1 on connect; retained commands are delivered immediately.
- Validates `MODE`/`SPD`, forwards `MODE:L|R,SPD:<n>\n` to the Arduino on `Serial2`, and re-sends the last REMOTE command every 5 s so an Arduino reset cannot silently return to LOCAL.
- `parseTelemetry()` accepts the new `MODE` field and still accepts the old four-field format.
- Published JSON adds `control_mode` and `control_speed_pct`.
- `Serial2` keeps `RXD2 = GPIO44` (the telemetry path already proven on this board) and moves only the command TX to `TXD2 = GPIO17`. GPIO43 is UART0 TX used by the Serial Monitor and must not be reused for Arduino commands.
- New wiring: Arduino TX (Pin 1) → level shifter → ESP GPIO44 (`RXD2`, unchanged); ESP GPIO17 (`TXD2`) → Arduino RX (Pin 0); common ground required.
- `printNoData()` now distinguishes "no bytes on RX" from "bytes arrived but no valid 9600 line" to make wiring/baud faults obvious.
- A GPIO16/17 loopback test produced zero received bytes on this board, so both pins were reverted to the known-good RX pin 44 with only TX moved to GPIO17.
- The temporary `[RAW]` diagnostic proved the exact line `V:12.0,I:0.0,VIB:0.00,SPD:0,MODE:L` arrives intact, while `parseTelemetry()` still rejected it. The command parser uses `%d` and works, but telemetry used `sscanf(%f)`; ESP32 Arduino does not reliably link float conversions for `sscanf` without an extra linker flag. Telemetry parsing was replaced with `strtok_r()` + `atof()`/`atoi()`, so no special flag is needed and the old four-field format remains accepted.

### `backend/mqtt_subscriber.py` and `app.py`
- `publish_control()` publishes the retained QoS 1 command; `get_control_state()` tracks the last command; telemetry acknowledgements update that state.
- `SensorReading` gained `control_mode` and `control_speed_pct`.
- Real Mode gained a **Speed Control** card: LOCAL/REMOTE selector, 100 / 80 / 50 / 0% presets, custom 0–100 input with Apply, and a hardware-acknowledgement line.
- LOCAL disables all remote inputs; REMOTE enables them. All Real Mode callbacks are still guarded by `pathname == "/real"`.
- `/real` is now split into five top tabs: **Overview**, **Speed Control**, **Live Charts**, **Analytics** and **Energy Log**. `switch_real_tab()` only toggles pane styles; every component stays mounted and no callback guard changed. The sticky header/tab bar was added in `assets/custom.css`, and the Real charts now use `responsive=True`.
- Global visual refresh: shared `COLORS` tokens and `apply_plot_style()` give every Plotly figure the same slate/teal palette; `assets/custom.css` softens cards, buttons, badges, tabs, inputs and scrollbars. The six Real Mode KPI cards are now a vertical `.reading-stack` on the Overview tab instead of a six-column row.
- Added `start-platform.bat` and a Desktop shortcut **PRIME-Factory.lnk**. The launcher checks/starts the Mosquitto service, starts Dash only if port 8050 is free, waits for readiness, then opens `/real`. No terminal commands are needed for daily use.
- Added a **read-only sharing mode**: `/real?view=readonly` hides the Speed Control tab, disables all speed inputs, and `send_speed_command()` rejects any command from such a link. The normal `/real` page keeps full control. This makes it safe to share a public tunnel link with a supervisor or teammates who should only watch.
- ESP Wi-Fi/MQTT retry intervals were reduced from 10 s / 5 s to 2 s / 2 s, with retries also on `WL_IDLE_STATUS` and `WL_NO_SSID_AVAIL`, so `ONLINE` appears quickly after power returns. ESP display-only low-voltage constant was aligned with Arduino's 9.0 V alarm. Arduino low-voltage alarm is now `≤9.0 V` with recovery at `≥10.2 V`.

### Verification
- Arduino Nano compile: OK. ESP32-S3 compile: OK (also after replacing `sscanf(%f)` with manual parsing). `py_compile` for Python files: OK.
- MQTT watcher received `MODE:R,SPD:0`, `MODE:R,SPD:80`, `MODE:R,SPD:65` and `MODE:L,SPD:65` at QoS 1 from the dashboard.
- Browser on `/real`: REMOTE enabled the controls; 80% and custom 65% updated the command status; LOCAL disabled the controls and published `MODE:L,SPD:65`; console had no errors.
- Browser check after the tab split: clicking **Speed Control** and **Energy Log** showed only the selected pane, all other panes stayed `display:none`, and the console had no errors.
- Browser check after the palette change: body `rgb(15,23,42)`, cards `rgb(30,41,59)`, selected tab `rgb(56,189,248)`, six stacked `.reading-card` elements with `flex-direction: column`; no console errors on `/real` or `/simulation`.
- Launcher tested from a stopped state and from an already-running state: both paths ended with port 8050 listening and `HTTP 200` on `/real`; no timeout/input-redirection errors after switching waits to `ping`.
- Browser on `/real?view=readonly`: the Speed Control tab became `display:none`, all six speed inputs were `disabled`, and the status read `🔒 Read-only view — monitoring only`; `/real` kept the tab visible. No console errors.
- Both modified sketches must be re-uploaded by the user; no hardware upload was performed here.
- Follow-up: with the command wire on GPIO43, the ESP reported "no data" while still forwarding MQTT commands. Moved `Serial2` to GPIO16/17 and added RX-byte diagnostics; ESP32-S3 compile remained OK.
- The local work was committed as `c67c281` and pushed to `origin/main`; no database or firmware sketch was uploaded.
- Added `PROJECT-REFERENCE.html` and generated `PROJECT-REFERENCE.pdf`: an Arabic reference covering every tool, protocol, wiring rule, change, and the full troubleshooting log reported by the user.
