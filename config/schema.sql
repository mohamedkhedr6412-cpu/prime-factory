PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sensor_readings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    device_id   TEXT NOT NULL DEFAULT 'esp32_station',
    weight_g    REAL,
    current_a   REAL,
    temp_c      REAL,
    status      TEXT
);

CREATE INDEX IF NOT EXISTS idx_readings_device_time ON sensor_readings(device_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_readings_status ON sensor_readings(status, timestamp DESC);

CREATE TABLE IF NOT EXISTS production_units (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_start      DATETIME NOT NULL,
    cycle_end        DATETIME NOT NULL,
    cycle_time_s     REAL NOT NULL,
    target_weight_g  REAL NOT NULL,
    final_weight_g   REAL NOT NULL,
    error_weight_g   REAL GENERATED ALWAYS AS (final_weight_g - target_weight_g) STORED,
    quality          TEXT NOT NULL,
    energy_wh        REAL NOT NULL,
    peak_current_a   REAL,
    avg_current_a    REAL,
    max_temp_c       REAL,
    device_id        TEXT NOT NULL DEFAULT 'esp32_station'
);

CREATE INDEX IF NOT EXISTS idx_units_time ON production_units(cycle_end DESC);
CREATE INDEX IF NOT EXISTS idx_units_quality ON production_units(quality, cycle_end DESC);

CREATE TABLE IF NOT EXISTS anomalies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    severity        TEXT NOT NULL,
    source          TEXT NOT NULL,
    reason          TEXT NOT NULL,
    sensor_snapshot TEXT,
    action_taken    TEXT,
    acknowledged    INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_anomalies_time ON anomalies(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_severity ON anomalies(severity, timestamp DESC);

CREATE TABLE IF NOT EXISTS system_config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO system_config (key, value) VALUES
    ('target_weight_g',    '100.0'),
    ('cutoff_offset_g',    '5.0'),
    ('max_current_a',      '2.5'),
    ('max_temp_c',         '70.0'),
    ('overweight_limit',   '110.0'),
    ('voltage_nominal',    '12.0'),
    ('ideal_cycle_time_s', '10.0'),
    ('planned_runtime_min','480');