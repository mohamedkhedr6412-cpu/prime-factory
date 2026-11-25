# ================================================================
# PRIME-Factory v1.0 — Main Dashboard Application
# File: app.py
# ================================================================
# Dual-mode dashboard: Real (Arduino Serial) + Simulation (JSON)
# Tech: Dash + Plotly + Bootstrap
# Port: http://127.0.0.1:8050
# Constitution: Software Constitution v1.0, Section 17
# ================================================================

import dash
from dash import dcc, html, Input, Output, State, callback, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import csv
import io
import json
import threading
import sqlite3
from datetime import datetime, timedelta
from dataclasses import asdict
from pathlib import Path
from collections import deque
from urllib.parse import quote

from backend.machine_profiles import MACHINE_PROFILES
from backend.financial_calculator import FinancialCalculator
from backend.comparison_engine import ComparisonEngine
from backend.serial_reader import SerialReader, SensorReading
from backend.simulation_engine import SimulationEngine
from backend.mes_calculator import MESCalculator
from backend.ems_calculator import EMSCalculator
from backend.pdm_calculator import PdMCalculator
from backend.rule_based_ai import RuleBasedAI

# ================================================================
# 1) App Initialization
# ================================================================
app = dash.Dash(__name__,
                external_stylesheets=[dbc.themes.DARKLY],
                title="PRIME-Factory | Condition Monitoring",
                suppress_callback_exceptions=True)
server = app.server

# ================================================================
# 2) Global State & SQLite Cache (Real Mode, last 300 seconds)
# ================================================================
CACHE_DB_PATH = Path("data/cache/real_mode_cache.db")
CACHE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Real Mode state
serial_reader = SerialReader(port="COM3", baud=9600)
real_data_buffer = deque(maxlen=300)  # Last 300 seconds in memory

# Calculator instances (Real Mode)
mes_calc = MESCalculator()
ems_calc = EMSCalculator()
pdm_calc = PdMCalculator(baseline_vibration_g=0.05)
ai_calc = RuleBasedAI()


# ================================================================
# 3) SQLite Cache Helpers (Real Mode)
# ================================================================
def init_cache_db():
    """Initialize SQLite cache table for Real Mode readings."""
    conn = sqlite3.connect(str(CACHE_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            state TEXT,
            rpm REAL,
            units INTEGER,
            current_a REAL,
            voltage_v REAL,
            temp_c REAL,
            vib_rms REAL,
            setpoint_rpm INTEGER
        )
    """)
    conn.commit()
    conn.close()


def save_reading_to_cache(reading: SensorReading):
    """Save a single reading to SQLite cache and keep only last 300 seconds."""
    conn = sqlite3.connect(str(CACHE_DB_PATH))
    conn.execute(
        "INSERT INTO readings (timestamp, state, rpm, units, current_a, voltage_v, temp_c, vib_rms, setpoint_rpm) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (reading.timestamp.isoformat(), reading.state, reading.rpm, reading.units,
         reading.current_a, reading.voltage_v, reading.temp_c, reading.vib_rms, reading.setpoint_rpm)
    )
    # Keep only last 300 seconds
    cutoff = (datetime.now() - timedelta(seconds=300)).isoformat()
    conn.execute("DELETE FROM readings WHERE timestamp < ?", (cutoff,))
    conn.commit()
    conn.close()


def load_cache_readings():
    """Load up to 300 most recent readings from SQLite cache."""
    conn = sqlite3.connect(str(CACHE_DB_PATH))
    rows = conn.execute(
        "SELECT timestamp, state, rpm, units, current_a, voltage_v, temp_c, vib_rms, setpoint_rpm "
        "FROM readings ORDER BY id DESC LIMIT 300"
    ).fetchall()
    conn.close()
    # Return in chronological order
    return [
        {
            "timestamp": r[0], "state": r[1], "rpm": r[2], "units": r[3],
            "current_a": r[4], "voltage_v": r[5], "temp_c": r[6],
            "vibration_rms_g": r[7], "setpoint_rpm": r[8]
        }
        for r in reversed(rows)
    ]


# Initialize cache on startup
init_cache_db()


# ================================================================
# 4) Helper: Empty Chart
# ================================================================
def empty_chart(title="No data yet"):
    fig = go.Figure()
    fig.update_layout(title=title, template="plotly_dark")
    return fig


# ================================================================
# 5) Layout — Landing Page
# ================================================================
app.layout = dbc.Container([
    # Header
    dbc.Row([
        dbc.Col([
            html.H1("🏭 PRIME-Factory", className="text-center mb-2"),
            html.P("Rotating Machinery Condition Monitoring Platform",
                   className="text-center text-muted"),
            html.P("Python 3.14 + Dash/Plotly | Dual-Mode: Real Hardware + Industrial Simulation",
                   className="text-center text-muted small")
        ], width=12)
    ], className="mt-4"),

    # Mode Selection
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H3("🔌 Real Hardware Mode", className="card-title"),
                    html.P("Connect to Arduino Uno via Serial Port (9600 baud)",
                           className="card-text"),
                    html.P("Live data from physical prototype (GA25-370 + 4 sensors)",
                           className="text-muted small"),
                    dbc.Button("Enter Real Mode",
                               id="btn-real-mode",
                               color="primary",
                               className="w-100 mt-3")
                ])
            ], className="mb-4"),
        ], width=6),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H3("🏭 Industrial Simulation Mode",
                            className="card-title"),
                    html.P("Demonstrate PRIME-Factory value on real scenarios",
                           className="card-text"),
                    html.P("Fertilizer & Packaging industries — 9 scenarios",
                           className="text-muted small"),
                    dbc.Button("Enter Simulation Mode",
                               id="btn-sim-mode",
                               color="success",
                               className="w-100 mt-3")
                ])
            ], className="mb-4"),
        ], width=6),
    ], justify="center"),

    # Dynamic Content Area
    html.Div(id="dynamic-content"),

    # Intervals, Stores & Download (Simulation playback state lives here)
    dcc.Interval(id="interval-real", interval=1000, n_intervals=0),
    dcc.Interval(id="interval-sim-play", interval=1000, n_intervals=0, disabled=True),
    dcc.Store(id="store-sim-data", data={}),
    dcc.Store(id="store-sim-play", data={"index": 0, "playing": False}),
    dcc.Download(id="download-report"),

], fluid=True, className="bg-dark text-light")


# ================================================================
# 6) Callbacks — Mode Switching
# ================================================================
@callback(
    Output("dynamic-content", "children"),
    [Input("btn-real-mode", "n_clicks"),
     Input("btn-sim-mode", "n_clicks")],
    prevent_initial_call=True
)
def switch_mode(real_clicks, sim_clicks):
    ctx = dash.callback_context
    if not ctx.triggered:
        return ""

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if button_id == "btn-real-mode":
        return build_real_mode_layout()
    elif button_id == "btn-sim-mode":
        return build_sim_mode_layout()

    return ""


# ================================================================
# 7) Real Mode Layout
# ================================================================
def build_real_mode_layout():
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H2("🔌 Real Hardware Monitor"),
                html.Div(id="serial-status",
                         children="🔴 Disconnected",
                         className="badge bg-danger")
            ], width=8),
            dbc.Col([
                dbc.Button("← Back to Home",
                           id="btn-back-real",
                           color="secondary",
                           className="float-end")
            ], width=4)
        ], className="mb-4"),

        # KPI Cards
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("State", className="card-title"),
                    html.H3(id="kpi-state", children="IDLE")
                ])
            ]), width=2),
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("RPM", className="card-title"),
                    html.H3(id="kpi-rpm", children="0")
                ])
            ]), width=2),
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("Current (A)", className="card-title"),
                    html.H3(id="kpi-current", children="0.00")
                ])
            ]), width=2),
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("Voltage (V)", className="card-title"),
                    html.H3(id="kpi-voltage", children="0.0")
                ])
            ]), width=2),
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("Vibration (g)", className="card-title"),
                    html.H3(id="kpi-vib", children="0.000")
                ])
            ]), width=2),
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H6("Temperature (°C)", className="card-title"),
                    html.H3(id="kpi-temp", children="0.0")
                ])
            ]), width=2),
        ], className="mb-4"),

        # Charts
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H5("Current & Voltage (Last 60s)"),
                        dcc.Graph(id="chart-current-voltage")
                    ])
                ])
            ], width=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H5("Vibration & Temperature (Last 60s)"),
                        dcc.Graph(id="chart-vib-temp")
                    ])
                ])
            ], width=6),
        ], className="mb-4"),

        # MES/EMS/PdM Cards
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H5("📊 MES Metrics"),
                    html.P(id="mes-oee", children="OEE: ---%"),
                    html.P(id="mes-units", children="Units: 0"),
                    html.P(id="mes-cycle", children="Cycle: ---s")
                ])
            ]), width=4),
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H5("⚡ EMS Metrics"),
                    html.P(id="ems-energy", children="Energy: --- kWh"),
                    html.P(id="ems-power", children="Power: --- W"),
                    html.P(id="ems-eff", children="Wh/unit: ---")
                ])
            ]), width=4),
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.H5("🔧 PdM Metrics"),
                    html.P(id="pdm-health", children="Health Score: ---"),
                    html.P(id="pdm-trend", children="Trend: ---"),
                    html.P(id="pdm-alert", children="Alert Level: ---")
                ])
            ]), width=4),
        ]),

        # Alert Panel
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H5("🚨 Live Alerts (Rule-Based AI)"),
                        html.Div(id="alert-panel",
                                 children="No alerts yet.",
                                 className="text-muted")
                    ])
                ])
            ], width=12)
        ])
    ], fluid=True)


# ================================================================
# 8) Simulation Mode Layout
# ================================================================
def build_sim_mode_layout():
    kpi_defs = [
        ("State", "🔧", "kpi-sim-state"),
        ("RPM", "⚙️", "kpi-sim-rpm"),
        ("Current", "⚡", "kpi-sim-current"),
        ("Voltage", "🔌", "kpi-sim-voltage"),
        ("Power", "🔋", "kpi-sim-power"),
        ("Temp", "🌡️", "kpi-sim-temp"),
        ("Vibration", "📳", "kpi-sim-vibration"),
        ("Energy", "⚡", "kpi-sim-energy"),
        ("Units", "📦", "kpi-sim-units"),
        ("OEE", "📊", "kpi-sim-oee"),
    ]

    return dbc.Container([
        # ---------- 1. Header: title, phase, timer, progress, markers ----------
        dbc.Row([
            dbc.Col([
                html.H2("🏭 PRIME-Factory", className="mb-0"),
                html.Div(id="phase-banner", className="small text-muted"),
            ], width=4),
            dbc.Col([
                html.Div(id="sim-timer-text", children="Elapsed 0s / 0s",
                         className="fw-bold"),
                dbc.Progress(id="sim-progress", value=0, color="success",
                             striped=True, animated=True,
                             style={"height": "10px"}),
            ], width=5, className="pt-2"),
            dbc.Col([
                html.Div([
                    dbc.Switch(id="mute-switch", label="🔇 Mute", value=False,
                               className="d-inline-block me-2"),
                    dbc.Button("📥 Export CSV", id="btn-export-report",
                               color="success", size="sm",
                               style={"display": "none"}),
                ], className="d-flex align-items-center justify-content-end"),
            ], width=3),
        ], className="mb-2 align-items-center"),

        html.Div(id="timeline-markers", className="d-flex gap-4 small text-muted mb-3"),

        # ---------- 2. KPI row (10 cards) ----------
        dbc.Row([_kpi_card(label, icon, cid) for label, icon, cid in kpi_defs],
                id="sim-kpi-row", className="g-2 mb-3"),

        # ---------- 3. Digital twin + AI log ----------
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("🔧 Digital Twin", className="text-muted mb-2"),
                html.Div(id="machine-viz",
                         style={"width": "200px", "height": "200px"}),
            ])), width=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("🤖 AI Event Log", className="text-muted mb-2"),
                html.Div(id="ai-log", children="No events yet.",
                         style={"maxHeight": "400px", "overflowY": "auto",
                                "fontFamily": "Consolas, monospace",
                                "fontSize": "12px"}),
            ])), width=9),
        ], className="g-2 mb-3"),

        # ---------- 4. Tabbed graphs (3 tabs x 3 graphs) ----------
        dcc.Tabs(id="graph-tabs", value="tab-electrical", className="mb-2", children=[
            dcc.Tab(label="⚡ Electrical", value="tab-electrical"),
            dcc.Tab(label="⚙️ Mechanical", value="tab-mechanical"),
            dcc.Tab(label="📊 Performance", value="tab-performance"),
        ]),
        html.Div(dbc.Row([
            _graph_col("graph-current", "⚡ Current (A)"),
            _graph_col("graph-voltage", "🔌 Voltage (V)"),
            _graph_col("graph-power", "🔋 Power (kW)"),
        ], className="g-2"), id="pane-electrical", style={"display": "block"}),
        html.Div(dbc.Row([
            _graph_col("graph-rpm", "⚙️ RPM"),
            _graph_col("graph-vibration", "📳 Vibration (g)"),
            _graph_col("graph-temp", "🌡️ Temperature (°C)"),
        ], className="g-2"), id="pane-mechanical", style={"display": "none"}),
        html.Div(dbc.Row([
            _graph_col("graph-energy", "⚡ Energy (Wh)"),
            _graph_col("graph-oee", "📊 OEE (%)"),
            _graph_col("graph-units", "📦 Units"),
        ], className="g-2"), id="pane-performance", style={"display": "none"}),

        # ---------- 5. MES / EMS / PdM ----------
        dbc.Row([
            dbc.Col(dbc.Card(id="mes-panel", children=dbc.CardBody(
                html.P("Waiting for data...", className="text-muted mb-0"))), width=4),
            dbc.Col(dbc.Card(id="ems-panel", children=dbc.CardBody(
                html.P("Waiting for data...", className="text-muted mb-0"))), width=4),
            dbc.Col(dbc.Card(id="pdm-panel", children=dbc.CardBody(
                html.P("Waiting for data...", className="text-muted mb-0"))), width=4),
        ], className="g-2 mb-3"),

        # ---------- Scenario selection + controls ----------
        dbc.Card(dbc.CardBody([
            html.H5("Select Scenario", className="mb-3"),
            dbc.Row([
                dbc.Col([
                    html.Label("Industry:", className="small text-muted"),
                    dcc.Dropdown(
                        id="dropdown-industry",
                        options=[
                            {"label": "🏭 Fertilizer Industry", "value": "Fertilizer"},
                            {"label": "📦 Packaging Industry", "value": "Packaging"},
                        ],
                        value="Fertilizer", clearable=False,
                        style={"color": "#000000", "backgroundColor": "#ffffff"},
                    ),
                ], width=4),
                dbc.Col([
                    html.Label("Equipment:", className="small text-muted"),
                    dcc.Dropdown(
                        id="dropdown-equipment", options=[],
                        placeholder="Select industry first",
                        style={"color": "#000000", "backgroundColor": "#ffffff"},
                    ),
                ], width=4),
                dbc.Col([
                    html.Label("Fault Type:", className="small text-muted"),
                    dcc.Dropdown(
                        id="dropdown-fault", options=[],
                        placeholder="Select equipment first",
                        style={"color": "#000000", "backgroundColor": "#ffffff"},
                    ),
                ], width=4),
            ], className="g-2"),
        ]), className="mb-3"),

        dbc.Row([
            dbc.Col(dbc.Button("▶ Start", id="btn-start-scenario",
                               color="success", className="w-100"), width=3),
            dbc.Col(dbc.Button("Phase B", id="btn-phase-b",
                               color="info", className="w-100",
                               style={"display": "none"}), width=3),
            dbc.Col(dbc.Button("Report", id="btn-comparison",
                               color="warning", className="w-100",
                               style={"display": "none"}), width=3),
            dbc.Col(dbc.Button("🔄 Run Another", id="btn-run-another",
                               color="primary", className="w-100",
                               style={"display": "none"}), width=3),
        ], className="g-2 mb-3"),

        # ---------- Banner + report + toast/sound plumbing ----------
        html.Div(id="scenario-banner", className="mb-2"),
        html.Div(id="comparison-report"),
        html.Div(id="toast-container"),
        html.Audio(id="beep-audio", src="/assets/alert_beep.wav",
                   controls=False, autoPlay=False, style={"display": "none"}),
        html.Div(id="alert-signal", style={"display": "none"}),
        html.Div(id="beep-out", style={"display": "none"}),
    ], fluid=True)


# ================================================================
# 9) Real Mode Callbacks
# ================================================================
@callback(
    [Output("kpi-state", "children"),
     Output("kpi-rpm", "children"),
     Output("kpi-current", "children"),
     Output("kpi-voltage", "children"),
     Output("kpi-vib", "children"),
     Output("kpi-temp", "children"),
     Output("serial-status", "children"),
     Output("serial-status", "className")],
    Input("interval-real", "n_intervals")
)
def update_real_kpis(n):
    """Update Real Mode KPIs every second."""
    reading = serial_reader.get_latest()

    if reading is None:
        return ("IDLE", "0", "0.00", "0.0", "0.000", "0.0",
                "🔴 Disconnected", "badge bg-danger")

    status_class = "badge bg-success" if serial_reader.is_connected else "badge bg-danger"
    status_text = "🟢 Connected" if serial_reader.is_connected else "🔴 Disconnected"

    # Save to in-memory buffer + SQLite cache
    real_data_buffer.append(asdict(reading))
    try:
        save_reading_to_cache(reading)
    except Exception as e:
        print(f"[RealMode] Cache save error: {e}")

    # Update calculators
    mes_metrics = mes_calc.update(reading)
    ems_metrics = ems_calc.update(reading)
    pdm_metrics = pdm_calc.update(reading)
    ai_result = ai_calc.check_anomaly(reading)

    # Store latest calculator results in a hidden div for MES/EMS/PdM callback
    # We return them via separate outputs using a shared store pattern below
    # For simplicity, KPI callback returns basic KPIs; MES/EMS/PdM handled separately

    return (reading.state,
            f"{reading.rpm:.1f}",
            f"{reading.current_a:.3f}",
            f"{reading.voltage_v:.1f}",
            f"{reading.vib_rms:.3f}",
            f"{reading.temp_c:.1f}",
            status_text,
            status_class)


@callback(
    [Output("mes-oee", "children"),
     Output("mes-units", "children"),
     Output("mes-cycle", "children"),
     Output("ems-energy", "children"),
     Output("ems-power", "children"),
     Output("ems-eff", "children"),
     Output("pdm-health", "children"),
     Output("pdm-trend", "children"),
     Output("pdm-alert", "children"),
     Output("alert-panel", "children"),
     Output("alert-panel", "className")],
    Input("interval-real", "n_intervals")
)
def update_real_metrics(n):
    """Update MES/EMS/PdM/AI metrics every second."""
    reading = serial_reader.get_latest()

    if reading is None:
        return ("OEE: ---%", "Units: 0", "Cycle: ---s",
                "Energy: --- kWh", "Power: --- W", "Wh/unit: ---",
                "Health Score: ---", "Trend: ---", "Alert Level: ---",
                "No alerts yet.", "text-muted")

    mes_metrics = mes_calc.update(reading)
    ems_metrics = ems_calc.update(reading)
    pdm_metrics = pdm_calc.update(reading)
    ai_result = ai_calc.check_anomaly(reading)

    # Alert panel
    if ai_result["has_anomaly"]:
        alert_text = " | ".join(ai_result["anomalies"])
        alert_class = f"text-{ai_result['severity']}"
        alert_html = html.Div([
            html.Strong(f"[{ai_result['severity'].upper()}] "),
            html.Span(alert_text)
        ])
    else:
        alert_html = "No alerts yet."
        alert_class = "text-muted"

    return (
        f"OEE: {mes_metrics['oee_pct']}%",
        f"Units: {mes_metrics['units_total']}",
        f"Cycle: {mes_metrics['avg_cycle_time_s']:.2f}s",
        f"Energy: {ems_metrics['energy_wh_total']} Wh",
        f"Power: {ems_metrics['power_w']} W",
        f"Wh/unit: {ems_metrics['wh_per_unit']}",
        f"Health Score: {pdm_metrics['health_score']}",
        f"Trend: {pdm_metrics['vibration_trend']}",
        f"Alert Level: {pdm_metrics['alert_level'].upper()}",
        alert_html,
        alert_class
    )


@callback(
    [Output("chart-current-voltage", "figure"),
     Output("chart-vib-temp", "figure")],
    Input("interval-real", "n_intervals")
)
def update_real_charts(n):
    """Update Real Mode charts from in-memory buffer + SQLite cache."""
    # Use in-memory buffer first, fallback to cache
    data = list(real_data_buffer)
    if len(data) == 0:
        cached = load_cache_readings()
        if cached:
            data = cached

    if len(data) == 0:
        empty_fig = empty_chart("Waiting for serial data...")
        return empty_fig, empty_fig

    # Current & Voltage chart
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(
        x=[d.get("timestamp", "") for d in data],
        y=[d.get("current_a", 0) for d in data],
        mode='lines',
        name='Current (A)',
        line=dict(color='blue')
    ))
    fig1.add_trace(go.Scatter(
        x=[d.get("timestamp", "") for d in data],
        y=[d.get("voltage_v", 0) for d in data],
        mode='lines',
        name='Voltage (V)',
        yaxis='y2',
        line=dict(color='orange')
    ))
    fig1.update_layout(
        title="Current & Voltage (Last 60s)",
        yaxis=dict(title="Current (A)"),
        yaxis2=dict(title="Voltage (V)", overlaying="y", side="right"),
        template="plotly_dark"
    )

    # Vibration & Temperature chart
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=[d.get("timestamp", "") for d in data],
        y=[d.get("vibration_rms_g", d.get("vib_rms", 0)) for d in data],
        mode='lines',
        name='Vibration (g)',
        line=dict(color='red')
    ))
    fig2.add_trace(go.Scatter(
        x=[d.get("timestamp", "") for d in data],
        y=[d.get("temp_c", 0) for d in data],
        mode='lines',
        name='Temperature (°C)',
        yaxis='y2',
        line=dict(color='green')
    ))
    fig2.update_layout(
        title="Vibration & Temperature (Last 60s)",
        yaxis=dict(title="Vibration (g)"),
        yaxis2=dict(title="Temperature (°C)", overlaying="y", side="right"),
        template="plotly_dark"
    )

    return fig1, fig2


# ================================================================
# 10) Simulation Mode Callbacks
# ================================================================
@callback(
    Output("dropdown-equipment", "options"),
    Input("dropdown-industry", "value")
)
def update_equipment_dropdown(industry):
    """Update equipment options based on industry."""
    if industry is None:
        return []

    options = []
    for machine_id, machine in MACHINE_PROFILES.items():
        if machine["industry"] == industry:
            options.append({
                "label": machine["name"],
                "value": machine_id
            })
    return options


@callback(
    Output("dropdown-fault", "options"),
    Input("dropdown-equipment", "value")
)
def update_fault_dropdown(equipment_id):
    """Update fault options based on equipment."""
    if equipment_id is None or equipment_id not in MACHINE_PROFILES:
        return []

    machine = MACHINE_PROFILES[equipment_id]
    options = []
    for fault_id, fault in machine["faults"].items():
        options.append({
            "label": fault["name"],
            "value": fault_id
        })
    return options


HIDDEN = {"display": "none"}
SHOWN = {"display": "block"}


@callback(
    Output("pane-electrical", "style"),
    Output("pane-mechanical", "style"),
    Output("pane-performance", "style"),
    Input("graph-tabs", "value"),
)
def switch_graph_tab(active):
    """Show only the pane of the selected graph tab (all graphs stay mounted)."""
    show, hide = {"display": "block"}, {"display": "none"}
    return (
        show if active == "tab-electrical" else hide,
        show if active == "tab-mechanical" else hide,
        show if active == "tab-performance" else hide,
    )


def _markers(t_inject, t_detect, t_fail):
    """Timeline markers rendered under the progress bar."""
    def chip(label, value, color):
        return html.Div([
            html.Span("● ", style={"color": color}),
            html.Span(f"{label}: t={value}s"),
        ])
    items = [chip("Fault Injected", t_inject, "#ffb703")]
    if t_detect is not None:
        items.insert(1, chip("AI Detection", t_detect, "#2a9d8f"))
    items.append(chip("Failure", t_fail, "#e63946"))
    return items


@callback(
    Output("store-sim-data", "data"),
    Output("interval-sim-play", "disabled"),
    Output("scenario-banner", "children"),
    Output("comparison-report", "children"),
    Output("phase-banner", "children"),
    Output("timeline-markers", "children"),
    Output("btn-phase-b", "style"),
    Output("btn-comparison", "style"),
    Output("btn-run-another", "style"),
    Output("btn-export-report", "style"),
    Input("btn-start-scenario", "n_clicks"),
    Input("btn-phase-b", "n_clicks"),
    Input("btn-run-another", "n_clicks"),
    State("dropdown-equipment", "value"),
    State("dropdown-fault", "value"),
    State("store-sim-data", "data"),
    prevent_initial_call=True,
)
def cb_control(start_clicks, phase_b_clicks, run_another_clicks,
               equipment_id, fault_id, store):
    """Start Phase A, start Phase B, or reset the whole scenario."""
    triggered = dash.ctx.triggered_id
    store = store or {}

    # ---- Reset ----
    if triggered == "btn-run-another":
        return ({}, True, "", "", "", "", HIDDEN, HIDDEN, HIDDEN, HIDDEN)

    # ---- Phase A: legacy system, no AI/PdM ----
    if triggered == "btn-start-scenario":
        if not equipment_id or not fault_id:
            return (store, True,
                    dbc.Alert("⚠️ Please select equipment and fault first.",
                              color="warning"),
                    "", "", "", HIDDEN, HIDDEN, HIDDEN, HIDDEN)

        machine = MACHINE_PROFILES[equipment_id]
        fault = machine["faults"][fault_id]
        duration_s = 90 if fault_id in ["unbalance", "loosening", "speed_droop"] else (
            120 if fault_id == "thermal_overload" else 60
        )
        injection_s = fault["injection_time_s"]

        data_a = SimulationEngine(equipment_id, fault_id,
                                  duration_s=duration_s).generate_without_pf()
        new_store = {
            "machine_id": equipment_id,
            "fault_id": fault_id,
            "duration_s": duration_s,
            "phase": "A",
            "data": data_a,
            "data_a": data_a,
            "index": 0,
            "playing": True,
        }
        banner = dbc.Alert([
            html.H5("⚠️ MONITORING: LEGACY SYSTEM", className="alert-heading"),
            html.P(f"No AI / no PdM — watching {fault['name']} progress blindly "
                   f"({duration_s}s scenario).", className="mb-0"),
        ], color="warning")
        phase_banner = html.Div("⚠️ Phase A: Without PRIME-Factory",
                                className="text-warning fw-bold")
        markers = _markers(injection_s, None, duration_s)
        return (new_store, False, banner, "", phase_banner, markers,
                HIDDEN, HIDDEN, HIDDEN, HIDDEN)

    # ---- Phase B: PRIME-Factory active ----
    if triggered == "btn-phase-b":
        if not store or store.get("phase") != "A":
            raise PreventUpdate

        duration_s = store["duration_s"]
        machine = MACHINE_PROFILES[store["machine_id"]]
        fault = machine["faults"][store["fault_id"]]
        detection_s = min(int(fault["time_to_detection_with_pf_min"] * 60),
                          int(duration_s * 0.5))

        data_b = SimulationEngine(store["machine_id"], store["fault_id"],
                                  duration_s=duration_s).generate_with_pf()
        new_store = dict(store)
        new_store.update({"phase": "B", "data": data_b,
                          "index": 0, "playing": True})
        banner = dbc.Alert([
            html.H5("✅ MONITORING: PRIME-FACTORY ACTIVE", className="alert-heading"),
            html.P("Rule-Based AI + PdM online — early detection and planned "
                   "maintenance in action.", className="mb-0"),
        ], color="success")
        phase_banner = html.Div("✅ Phase B: With PRIME-Factory",
                                className="text-success fw-bold")
        markers = _markers(fault["injection_time_s"], detection_s, duration_s)
        return (new_store, False, banner, "", phase_banner, markers,
                HIDDEN, HIDDEN, HIDDEN, HIDDEN)

    raise PreventUpdate


@callback(
    Output("store-sim-data", "data", allow_duplicate=True),
    Output("interval-sim-play", "disabled", allow_duplicate=True),
    Output("btn-phase-b", "style", allow_duplicate=True),
    Output("btn-comparison", "style", allow_duplicate=True),
    Output("btn-run-another", "style", allow_duplicate=True),
    Output("btn-export-report", "style", allow_duplicate=True),
    Output("phase-banner", "children", allow_duplicate=True),
    Output("sim-timer-text", "children"),
    Output("sim-progress", "value"),
    Output("sim-progress", "color"),
    Output("kpi-sim-state", "children"),
    Output("kpi-sim-rpm", "children"),
    Output("kpi-sim-current", "children"),
    Output("kpi-sim-voltage", "children"),
    Output("kpi-sim-power", "children"),
    Output("kpi-sim-temp", "children"),
    Output("kpi-sim-vibration", "children"),
    Output("kpi-sim-energy", "children"),
    Output("kpi-sim-units", "children"),
    Output("kpi-sim-oee", "children"),
    Output("machine-viz", "children"),
    Output("ai-log", "children"),
    Output("toast-container", "children"),
    Output("alert-signal", "children"),
    Output("mes-panel", "children"),
    Output("ems-panel", "children"),
    Output("pdm-panel", "children"),
    Output("graph-current", "figure"),
    Output("graph-voltage", "figure"),
    Output("graph-power", "figure"),
    Output("graph-rpm", "figure"),
    Output("graph-vibration", "figure"),
    Output("graph-temp", "figure"),
    Output("graph-energy", "figure"),
    Output("graph-oee", "figure"),
    Output("graph-units", "figure"),
    Input("interval-sim-play", "n_intervals"),
    State("store-sim-data", "data"),
    prevent_initial_call=True,
)
def cb_playback_tick(n_intervals, store):
    """Advance one second and redraw only the elapsed window."""
    if not store or not store.get("data"):
        raise PreventUpdate

    data = store["data"]
    idx = min(store.get("index", 0) + 1, len(data))
    window = data[:idx]                 # animated window, NOT the whole timeline
    point = window[-1]
    prev = window[-2] if idx > 1 else None
    duration_s = store.get("duration_s", len(data))
    phase = store.get("phase", "A")
    finished = idx >= len(data)

    machine = MACHINE_PROFILES.get(store.get("machine_id"), {})
    fault = machine.get("faults", {}).get(store.get("fault_id"), {})
    lim = _limits(machine)

    # ---- latest values ----
    state = point.get("state", "N/A")
    rpm = _get_val(point, "rpm", default=0)
    cur = _get_val(point, "current_a", "current", default=0)
    volt = _get_val(point, "voltage_v", "voltage", default=0)
    power = _get_val(point, "power_w", "power_kw", "power", default=0)
    temp = _get_val(point, "temp_c", "temperature", "temp", default=0)
    vib = _get_val(point, "vibration_rms_g", "vibration_g", "vib_rms", default=0)
    energy = _get_val(point, "energy_wh", "energy", default=0)
    units = int(_get_val(point, "units_produced", "units", default=0))
    oee = _get_val(point, "oee_pct", "oee", default=0)

    p_rpm = _get_val(prev, "rpm", default=0) if prev else None
    p_cur = _get_val(prev, "current_a", "current", default=0) if prev else None
    p_volt = _get_val(prev, "voltage_v", "voltage", default=0) if prev else None
    p_power = _get_val(prev, "power_w", "power_kw", "power", default=0) if prev else None
    p_temp = _get_val(prev, "temp_c", "temperature", "temp", default=0) if prev else None
    p_vib = _get_val(prev, "vibration_rms_g", "vibration_g", "vib_rms", default=0) if prev else None
    p_energy = _get_val(prev, "energy_wh", "energy", default=0) if prev else None
    p_units = int(_get_val(prev, "units_produced", "units", default=0)) if prev else None
    p_oee = _get_val(prev, "oee_pct", "oee", default=0) if prev else None

    # ---- severity ----
    cur_status = _status_for(cur, lim["warning"], lim["critical"])
    temp_status = _status_for(temp, lim["temp_base"] + 15, lim["temp_base"] + 35)
    vib_status = _status_for(vib, lim["vib_base"] * 2.5, lim["vib_base"] * 4)
    ai_entries = build_ai_entries(window, machine, fault, phase)
    has_critical = any(e["sev"] == "critical" for e in ai_entries)
    has_warning = any(e["sev"] == "warning" for e in ai_entries)

    if state == "FAULT":
        state_status = "critical"
    elif has_critical:
        state_status = "critical"
    elif has_warning:
        state_status = "warning"
    else:
        state_status = "normal"

    # ---- KPI cards (dynamic colour + arrows + thresholds) ----
    kpi_state = kpi_body(
        "State", "🔧", state, "", state_status, delta=None,
        threshold=f"{phase} · {'AI online' if phase == 'B' else 'no AI'}")

    kpi_rpm = kpi_body(
        "RPM", "⚙️", f"{rpm:,.1f}", "rpm",
        "critical" if rpm < machine.get("rated_rpm", 0) * 0.2 else "normal",
        _delta_span(rpm, p_rpm, " rpm"),
        f"Rated {machine.get('rated_rpm', 0):,.0f} rpm")

    kpi_current = kpi_body(
        "Current", "⚡", f"{cur:,.1f}", "A", cur_status,
        _delta_span(cur, p_cur, " A"),
        f"Normal {lim['normal']:.0f}A | Warn {lim['warning']:.0f}A | "
        f"Crit {lim['critical']:.0f}A")

    kpi_voltage = kpi_body(
        "Voltage", "🔌", f"{volt:,.1f}", "V", "normal",
        _delta_span(volt, p_volt, " V"), "Nominal 380 V")

    kpi_power = kpi_body(
        "Power", "🔋", f"{power:,.2f}", "kW", "normal",
        _delta_span(power, p_power, " kW"),
        f"Rated {machine.get('rated_power_kw', 0)} kW")

    kpi_temp = kpi_body(
        "Temp", "🌡️", f"{temp:,.1f}", "°C", temp_status,
        _delta_span(temp, p_temp, " °C"),
        f"Normal {lim['temp_base']:.0f}°C | Warn "
        f"{lim['temp_base'] + 15:.0f}°C | Crit {lim['temp_base'] + 35:.0f}°C")

    kpi_vib = kpi_body(
        "Vibration", "📳", f"{vib:,.3f}", "g", vib_status,
        _delta_span(vib, p_vib, " g"),
        f"Normal {lim['vib_base']:.2f}g | Warn "
        f"{lim['vib_base'] * 2.5:.2f}g | Crit {lim['vib_base'] * 4:.2f}g")

    kpi_energy = kpi_body(
        "Energy", "⚡", f"{energy:,.2f}", "Wh", "normal",
        _delta_span(energy, p_energy, " Wh"), "Cumulative per second")

    kpi_units = kpi_body(
        "Units", "📦", f"{units:,}", "", "normal",
        _delta_span(units, p_units, " u"), "Cumulative output")

    kpi_oee = kpi_body(
        "OEE", "📊", f"{oee:,.1f}", "%",
        "critical" if oee < 50 else ("warning" if oee < 75 else "normal"),
        _delta_span(oee, p_oee, "%"), "Target ≥ 85%")

    # ---- MES / EMS / PdM panels ----
    readings = [_to_reading(p) for p in window]
    mes, ems, pdm = MESCalculator(), EMSCalculator(), PdMCalculator(
        baseline_vibration_g=lim["vib_base"])
    mes.setpoint_rpm = machine.get("rated_rpm", mes.setpoint_rpm)
    mes_m = ems_m = pdm_m = {}
    for r in readings:
        mes_m = mes.update(r)
        ems_m = ems.update(r)
        pdm_m = pdm.update(r)

    mes_panel = dbc.CardBody([
        html.H6("📊 MES Panel", className="text-muted"),
        html.P(f"Availability: {mes_m.get('availability_pct', 0)}%", className="mb-1"),
        html.P(f"Performance: {mes_m.get('performance_pct', 0)}%", className="mb-1"),
        html.P(f"Quality: {mes_m.get('quality_pct', 0)}%", className="mb-1"),
        html.H5(f"OEE: {mes_m.get('oee_pct', 0)}%", className="text-info mb-0"),
    ])
    waste = ems_m.get("current_a", 0) > machine.get("rated_current_a", 999)
    ems_panel = dbc.CardBody([
        html.H6("⚡ EMS Panel", className="text-muted"),
        html.P(f"Energy: {ems_m.get('energy_wh_total', 0):.3f} Wh", className="mb-1"),
        html.P(f"Wh / unit: {ems_m.get('wh_per_unit', 0):.4f}", className="mb-1"),
        html.P(f"Power: {ems_m.get('power_w', 0):.1f} W", className="mb-1"),
        html.P("⚠ Energy waste detected" if waste else "Energy within limits",
               className="text-danger mb-0" if waste else "text-success mb-0"),
    ])
    pdm_panel = dbc.CardBody([
        html.H6("🔧 PdM Panel", className="text-muted"),
        html.H5(f"Health: {pdm_m.get('health_score', 0)}/100",
                className="text-info mb-1"),
        html.P(f"Vibration: {pdm_m.get('vibration_rms_g', 0)} g "
               f"({pdm_m.get('vibration_trend', 'n/a')})", className="mb-1"),
        html.P(f"Alert: {pdm_m.get('alert_level', 'n/a')}", className="mb-0"),
    ])

    # ---- digital twin, log, toast ----
    viz_status = ("critical" if (state == "FAULT" or has_critical)
                  else "warning" if has_warning else "normal")
    viz = build_machine_viz(viz_status, machine.get("name", "Machine"),
                            FAULT_LOCATION.get(store.get("fault_id"), "Machine"),
                            "PHASE " + phase)
    ai_log = render_ai_log(ai_entries)
    toast = render_toast(ai_entries)

    crit_t = next((e["t"] for e in ai_entries if e["sev"] == "critical"), None)
    signal = (f"{store.get('machine_id')}:{store.get('fault_id')}:{crit_t:.1f}"
              if crit_t is not None else "")

    # ---- header + buttons ----
    pct = round((idx - 1) / duration_s * 100, 1) if duration_s else 0
    color = "success" if pct < 30 else ("warning" if pct < 60 else "danger")
    timer = f"Elapsed {idx - 1}s / {duration_s}s"
    phase_banner = html.Div(
        f"{'⚠️ Phase A: Without PRIME-Factory' if phase == 'A' else '✅ Phase B: With PRIME-Factory'}"
        f" · {machine.get('name', '')}",
        className=("text-warning" if phase == "A" else "text-success") + " fw-bold")

    btn_phase_b = SHOWN if (finished and phase == "A") else HIDDEN
    btn_comparison = SHOWN if (finished and phase == "B") else HIDDEN
    btn_run_another = SHOWN if finished else HIDDEN
    btn_export = SHOWN if (finished and phase == "B") else HIDDEN

    new_store = dict(store)
    new_store.update({"index": idx, "playing": not finished})

    # ---- 9 graphs (3 tabs) ----
    thr_current = [(lim["warning"], "#ffb703", f"Warning {lim['warning']:.0f}A"),
                   (lim["critical"], "#e63946", f"Critical {lim['critical']:.0f}A")]
    thr_vib = [(lim["vib_base"] * 2.5, "#ffb703", "Warning"),
               (lim["vib_base"] * 4, "#e63946", "Critical")]
    thr_temp = [(lim["temp_base"] + 15, "#ffb703", "Warning"),
                (lim["temp_base"] + 35, "#e63946", "Critical")]

    figs = [
        build_param_figure(window, ["current_a", "current"], "⚡ Current (A)", "A",
                           "#00b4d8", thr_current),
        build_param_figure(window, ["voltage_v", "voltage"], "🔌 Voltage (V)", "V",
                           "#f4a261"),
        build_param_figure(window, ["power_w", "power_kw", "power"], "🔋 Power (kW)",
                           "kW", "#e76f51"),
        build_param_figure(window, ["rpm"], "⚙️ RPM", "RPM", "#2a9d8f"),
        build_param_figure(window, ["vibration_rms_g", "vibration_g", "vib_rms"],
                           "📳 Vibration (g)", "g", "#e63946", thr_vib),
        build_param_figure(window, ["temp_c", "temperature", "temp"],
                           "🌡️ Temperature (°C)", "°C", "#ffb703", thr_temp),
        build_param_figure(window, ["energy_wh", "energy"], "⚡ Energy (Wh)", "Wh",
                           "#8ecae6"),
        build_param_figure(window, ["oee_pct", "oee"], "📊 OEE (%)", "%", "#00cc96"),
        build_param_figure(window, ["units_produced", "units"], "📦 Units", "units",
                           "#ffa15a"),
    ]

    return (new_store, finished, btn_phase_b, btn_comparison, btn_run_another,
            btn_export, phase_banner, timer, pct, color,
            kpi_state, kpi_rpm, kpi_current, kpi_voltage, kpi_power, kpi_temp,
            kpi_vib, kpi_energy, kpi_units, kpi_oee,
            viz, ai_log, toast, signal,
            mes_panel, ems_panel, pdm_panel,
            *figs)


@callback(
    Output("comparison-report", "children", allow_duplicate=True),
    Input("btn-comparison", "n_clicks"),
    State("store-sim-data", "data"),
    prevent_initial_call=True,
)
def cb_comparison(n_clicks, store):
    """Build the financial/technical comparison report."""
    if not n_clicks or not store or store.get("phase") != "B":
        raise PreventUpdate
    report = ComparisonEngine.generate_report(
        store["machine_id"], store["fault_id"],
        store.get("data_a", []), store["data"],
    )
    return build_comparison_ui(report)


@callback(
    Output("download-report", "data"),
    Input("btn-export-report", "n_clicks"),
    State("store-sim-data", "data"),
    prevent_initial_call=True,
)
def cb_export_report(n_clicks, store):
    """Professional CSV export: header, both timelines, financials, AI log."""
    if not n_clicks or not store or not store.get("data"):
        raise PreventUpdate

    machine = MACHINE_PROFILES[store["machine_id"]]
    fault = machine["faults"][store["fault_id"]]
    report = ComparisonEngine.generate_report(
        store["machine_id"], store["fault_id"],
        store.get("data_a", []), store["data"],
    )
    fin = report["financial_comparison"]
    tech = report["technical_comparison"]

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["PRIME-Factory v1.0 — Simulation Export"])
    w.writerow([])
    w.writerow(["FIELD", "VALUE"])
    w.writerow(["Scenario", fault["name"]])
    w.writerow(["Machine", machine["name"]])
    w.writerow(["Machine ID", store["machine_id"]])
    w.writerow(["Fault ID", store["fault_id"]])
    w.writerow(["Industry", machine["industry"]])
    w.writerow(["Generated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    w.writerow(["Duration (s)", store.get("duration_s")])
    w.writerow(["Phase A points", len(store.get("data_a", []))])
    w.writerow(["Phase B points", len(store["data"])])
    w.writerow([])

    w.writerow(["FINANCIAL SUMMARY", "WITHOUT PF", "WITH PF"])
    w.writerow(["Detection time (min)",
                fin["without_pf"]["detection_time_min"],
                fin["with_pf"]["detection_time_min"]])
    w.writerow(["Downtime (min)",
                fin["without_pf"]["downtime_min"],
                fin["with_pf"]["downtime_min"]])
    w.writerow(["Repair cost (EGP)",
                fin["without_pf"]["repair_cost_egp"],
                fin["with_pf"]["repair_cost_egp"]])
    w.writerow(["Energy waste (EGP)",
                fin["without_pf"]["energy_waste_egp"],
                fin["with_pf"]["energy_waste_egp"]])
    w.writerow(["Scrap cost (EGP)",
                fin["without_pf"]["scrap_cost_egp"],
                fin["with_pf"]["scrap_cost_egp"]])
    w.writerow(["Total loss (EGP)",
                fin["without_pf"]["total_loss_egp"],
                fin["with_pf"]["total_loss_egp"]])
    w.writerow([])
    w.writerow(["Total savings (EGP)", fin["total_savings_egp"]])
    w.writerow(["Cost reduction (%)", fin["savings_pct"]])
    w.writerow(["Downtime reduction (%)", tech["downtime_reduction_pct"]])
    w.writerow(["Units saved", tech["units_saved"]])
    w.writerow([])

    columns = ["t_s", "state", "rpm", "current_a", "voltage_v", "power_kw",
               "temp_c", "vibration_g", "energy_wh", "units", "oee_pct", "alert"]
    for title, points in (("PHASE A — WITHOUT PRIME-FACTORY", store.get("data_a", [])),
                          ("PHASE B — WITH PRIME-FACTORY", store["data"])):
        w.writerow([title])
        w.writerow(columns)
        for p in points:
            w.writerow([
                p.get("t_s"), p.get("state", ""),
                _get_val(p, "rpm", default=""),
                _get_val(p, "current_a", "current", default=""),
                _get_val(p, "voltage_v", "voltage", default=""),
                _get_val(p, "power_w", "power_kw", "power", default=""),
                _get_val(p, "temp_c", "temperature", "temp", default=""),
                _get_val(p, "vibration_rms_g", "vibration_g", "vib_rms", default=""),
                _get_val(p, "energy_wh", "energy", default=""),
                _get_val(p, "units_produced", "units", default=""),
                _get_val(p, "oee_pct", "oee", default=""),
                p.get("alert") or "",
            ])
        w.writerow([])

    w.writerow(["AI LOG — PHASE B (severity, message, explanation)"])
    for e in build_ai_entries(store["data"], machine, fault, "B"):
        w.writerow([f"t={e['t']:.1f}s", e["sev"], e["title"], e["detail"]])

    name = f"prime_factory_{store['machine_id']}_{store['fault_id']}.csv"
    return dict(content=buf.getvalue(), filename=name)


# ================================================================
# 11) Helper Functions (Simulation UI)
# ================================================================
FAULT_LOCATION = {
    "mechanical_jam": "Bearing / Coupling",
    "thermal_overload": "Motor Winding",
    "unbalance": "Drum / Shaft",
    "loosening": "Mounting Bolts",
    "voltage_sag": "Power Supply",
    "speed_droop": "Drive Belt",
}

STATUS_COLORS = {"normal": "#2a9d8f", "warning": "#ffb703", "critical": "#e63946"}
STATUS_TEXT = {"normal": "text-success", "warning": "text-warning", "critical": "text-danger"}
STATUS_ICON = {"normal": "🟢", "warning": "🟡", "critical": "🔴"}


def _get_val(d, *keys, default=0):
    """Safely get a value from dict trying multiple alternative key names."""
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _to_reading(p):
    """Convert a simulation data point into a SensorReading for MES/EMS/PdM."""
    ts = p.get("timestamp")
    try:
        ts = datetime.fromisoformat(ts) if isinstance(ts, str) else datetime.now()
    except ValueError:
        ts = datetime.now()
    return SensorReading(
        timestamp=ts,
        state=p.get("state", "RUNNING"),
        rpm=_get_val(p, "rpm", default=0),
        units=int(_get_val(p, "units_produced", "units", default=0)),
        current_a=_get_val(p, "current_a", "current", default=0),
        voltage_v=_get_val(p, "voltage_v", "voltage", default=0),
        temp_c=_get_val(p, "temp_c", "temperature", "temp", default=0),
        vib_rms=_get_val(p, "vibration_rms_g", "vibration_g", "vib_rms", default=0),
        setpoint_rpm=int(_get_val(p, "rpm", default=0)),
    )


def _limits(machine):
    """Machine-relative current thresholds (granulator: 68 / 102 / 153 A)."""
    rated = machine.get("rated_current_a", 85.0)
    load = machine.get("typical_load_pct", 0.8)
    return {
        "normal": round(rated * load, 1),
        "warning": round(rated * 1.2, 0),
        "critical": round(rated * 1.8, 0),
        "temp_base": machine.get("baseline_temp_c", 45.0),
        "vib_base": machine.get("baseline_vibration_g", 0.1),
    }


def _status_for(value, warn, crit):
    if value >= crit:
        return "critical"
    if value >= warn:
        return "warning"
    return "normal"


def _delta_span(current, previous, unit=""):
    """Arrow + coloured delta versus the previous second."""
    if previous is None or current is None:
        return html.Span("—", className="text-muted")
    diff = current - previous
    if abs(diff) < 1e-9:
        return html.Span("→ stable", className="text-muted")
    up = diff > 0
    return html.Span(
        f"{'▲' if up else '▼'} {abs(diff):,.2f}{unit}",
        className="text-danger" if up else "text-success",
    )


def kpi_body(label, icon, value, unit="", status="normal", delta=None, threshold=""):
    """One KPI card body: icon+label, coloured value, arrow, thresholds."""
    return dbc.CardBody([
        html.Div([html.Span(icon), html.Span(label, className="kpi-label")]),
        html.H3([
            html.Span(value, className="kpi-value " + STATUS_TEXT[status]),
            html.Span((" " + unit) if unit else "", className="kpi-unit"),
        ], className="mb-0"),
        html.Div(delta if delta is not None else "", className="kpi-delta"),
        html.Div(threshold, className="kpi-threshold"),
    ], className="kpi-card-body")


def _kpi_card(label, icon, cid):
    return dbc.Col(dbc.Card(
        kpi_body(label, icon, "—", "", "normal", None, ""),
        id=cid, className="kpi-card",
    ), width=1)


def _graph_col(gid, title):
    return dbc.Col([
        dcc.Graph(id=gid, figure=empty_chart(title),
                  config={"displayModeBar": False},
                  style={"height": "300px"}),
    ], width=4)


def build_param_figure(window, keys, title, y_title, color="#00b4d8",
                       thresholds=None):
    """Single-parameter graph for the elapsed window + optional threshold lines."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[p.get("t_s", 0) for p in window],
        y=[_get_val(p, *keys, default=0) for p in window],
        mode="lines",
        name=title,
        line=dict(width=2.4, color=color),
    ))
    for y, tcolor, label in (thresholds or []):
        fig.add_hline(y=y, line_dash="dot", line_color=tcolor,
                      annotation_text=label, annotation_position="top left",
                      annotation_font=dict(size=9, color=tcolor))
    fig.update_layout(
        title=dict(text=title, font=dict(size=13)),
        margin=dict(l=40, r=15, t=38, b=28),
        xaxis=dict(title="t (s)"),
        yaxis=dict(title=y_title),
        template="plotly_dark",
        showlegend=False,
        uirevision="keep",
    )
    return fig


def build_machine_viz(status, machine_name, fault_location, phase):
    """200x200 SVG digital twin (motor drum + fault marker)."""
    color = STATUS_COLORS.get(status, "#2a9d8f")
    label = STATUS_ICON.get(status, "🟢") + " " + status.upper()
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">
  <rect x="0" y="0" width="200" height="200" rx="14" fill="#111820"/>
  <circle cx="100" cy="92" r="62" fill="none" stroke="{color}" stroke-width="5" opacity="0.85"/>
  <circle cx="100" cy="92" r="46" fill="{color}" opacity="0.16"/>
  <circle cx="100" cy="92" r="22" fill="none" stroke="{color}" stroke-width="3"/>
  <line x1="30" y1="92" x2="8" y2="92" stroke="{color}" stroke-width="9" stroke-linecap="round"/>
  <circle cx="100" cy="92" r="6" fill="{color}"/>
  <circle cx="151" cy="42" r="8" fill="{color}" opacity="0.95"/>
  <circle cx="151" cy="42" r="15" fill="none" stroke="{color}" stroke-width="2" opacity="0.6"/>
  <text x="151" y="20" font-size="10" fill="{color}" text-anchor="middle" font-family="Arial">FAULT</text>
  <text x="100" y="170" font-size="10" fill="#cbd5e1" text-anchor="middle" font-family="Arial">{phase}</text>
  <text x="100" y="185" font-size="9" fill="{color}" text-anchor="middle" font-family="Arial">{label} · {fault_location}</text>
</svg>"""
    return html.Div([
        html.Img(src="data:image/svg+xml;utf8," + quote(svg),
                 style={"width": "200px", "height": "200px"},
                 title=machine_name),
    ], className="d-flex justify-content-center")


def build_ai_entries(window, machine, fault, phase):
    """Severity-tagged AI explanations derived from the elapsed window."""
    limits = _limits(machine)
    warn, crit, base_t, base_v = (limits["warning"], limits["critical"],
                                  limits["temp_base"], limits["vib_base"])
    entries = []
    seen = {"current": False, "temp": False, "vib": False, "crit": False}

    for p in window:
        t = float(p.get("t_s", 0))
        cur = _get_val(p, "current_a", "current", default=0)
        temp = _get_val(p, "temp_c", "temperature", "temp", default=0)
        vib = _get_val(p, "vibration_rms_g", "vibration_g", "vib_rms", default=0)
        state = p.get("state", "RUNNING")
        alert = p.get("alert")

        if not entries:
            entries.append({
                "t": 0.0, "sev": "normal",
                "title": "🟢 System Normal",
                "detail": f"Baseline current {limits['normal']:.0f} A · "
                          f"vibration {vib:.3f} g · temperature {temp:.0f} °C",
            })

        if cur >= warn and not seen["current"]:
            seen["current"] = True
            pct = (cur / limits["normal"] - 1) * 100 if limits["normal"] else 0
            entries.append({
                "t": t, "sev": "critical" if cur >= crit else "warning",
                "title": "⚠️ Anomaly Detected — ⚡ Current spike",
                "detail": f"{cur:.0f} A (threshold {warn:.0f} A) → "
                          f"{pct:.0f}% above normal load",
            })

        if temp >= base_t + 15 and not seen["temp"]:
            seen["temp"] = True
            entries.append({
                "t": t, "sev": "critical" if temp >= base_t + 35 else "warning",
                "title": "⚠️ Anomaly Detected — 🌡️ Temperature rise",
                "detail": f"{temp:.1f} °C (baseline {base_t:.0f} °C) → "
                          f"+{temp - base_t:.1f} °C above normal",
            })

        if vib >= base_v * 2.5 and not seen["vib"]:
            seen["vib"] = True
            entries.append({
                "t": t, "sev": "critical" if vib >= base_v * 4 else "warning",
                "title": "⚠️ Anomaly Detected — 📳 Vibration",
                "detail": f"{vib:.3f} g (baseline {base_v:.3f} g) → "
                          f"{vib / base_v:.1f}× normal",
            })

        if not seen["crit"] and (state == "FAULT" or (alert and "detect" in str(alert).lower())):
            seen["crit"] = True
            entries.append({
                "t": t, "sev": "critical",
                "title": "🛑 CRITICAL — JAM DETECTED",
                "detail": alert or (f"Machine stopped at t={t:.0f}s — RPM 0, "
                                    f"current {cur:.0f} A"),
            })

    return entries


def render_ai_log(entries):
    if not entries:
        return html.Div("Waiting for the scenario to start…",
                        className="text-muted small p-2")
    colors = {"normal": "success", "warning": "warning", "critical": "danger"}
    return [dbc.Alert([
        html.Div([
            html.Span(f"[t={e['t']:.1f}s] ", className="ai-ts"),
            html.Strong(e["title"]),
        ]),
        html.Div(e["detail"], className="ai-detail"),
    ], color=colors[e["sev"]], className="py-1 px-2 mb-1 ai-entry")
        for e in entries[-40:]]


def render_toast(entries):
    crit = [e for e in entries if e["sev"] == "critical"]
    if not crit:
        return ""
    e = crit[-1]
    return html.Div([
        html.Strong(f"🛑 JAM DETECTED at t={e['t']:.0f}s"),
        html.Div(e["detail"], className="small"),
    ], className="pf-toast")


def build_comparison_ui(report):
    """Financial + technical comparison with charts instead of plain tables."""
    if not report:
        return ""

    fin = report["financial_comparison"]
    tech = report["technical_comparison"]
    scen = report.get("scenario", {})
    w, p = fin["without_pf"], fin["with_pf"]

    cost_fig = go.Figure(go.Bar(
        x=["Without PRIME-Factory", "With PRIME-Factory", "Savings"],
        y=[w["total_loss_egp"], p["total_loss_egp"], fin["total_savings_egp"]],
        marker_color=["#e63946", "#2a9d8f", "#90be6d"],
        text=[f"{w['total_loss_egp']:,.0f} EGP",
              f"{p['total_loss_egp']:,.0f} EGP",
              f"{fin['total_savings_egp']:,.0f} EGP"],
        textposition="outside",
    ))
    cost_fig.update_layout(title="💰 Total Cost Comparison", template="plotly_dark",
                           margin=dict(l=50, r=20, t=45, b=30),
                           yaxis_title="EGP")

    cats = ["Downtime", "Energy", "Scrap", "Repair"]
    breakdown = go.Figure([
        go.Bar(name="Without PF", x=cats,
               y=[w["downtime_cost_egp"], w["energy_waste_egp"],
                  w["scrap_cost_egp"], w["repair_cost_egp"]],
               marker_color="#e63946"),
        go.Bar(name="With PF", x=cats,
               y=[p["downtime_cost_egp"], p["energy_waste_egp"],
                  p["scrap_cost_egp"], p["repair_cost_egp"]],
               marker_color="#2a9d8f"),
    ])
    breakdown.update_layout(title="🔍 Loss Breakdown", barmode="group",
                            template="plotly_dark",
                            margin=dict(l=50, r=20, t=45, b=30),
                            yaxis_title="EGP", legend=dict(orientation="h"))

    timeline = go.Figure(go.Bar(
        x=[w["detection_time_min"], p["detection_time_min"]],
        y=["Without PF", "With PF"],
        orientation="h",
        marker_color=["#e63946", "#2a9d8f"],
        text=[f"{w['detection_time_min']:.0f} min", f"{p['detection_time_min']:.0f} min"],
        textposition="outside",
    ))
    timeline.update_layout(title="⏱️ Detection Time (Before / After)",
                           template="plotly_dark",
                           margin=dict(l=80, r=40, t=45, b=30),
                           xaxis_title="minutes")

    return dbc.Card(dbc.CardBody([
        html.H3("📊 Comparison Report", className="mb-1"),
        html.P(f"{scen.get('machine', '')} — {scen.get('fault', '')}",
               className="text-muted mb-4"),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=cost_fig, config={"displayModeBar": False}), width=6),
            dbc.Col(dcc.Graph(figure=timeline, config={"displayModeBar": False}), width=6),
        ], className="mb-3"),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=breakdown, config={"displayModeBar": False}), width=12),
        ], className="mb-3"),
        dbc.Card(dbc.CardBody([
            html.Div("💰 TOTAL SAVINGS", className="text-center text-muted small"),
            html.H1(f"{fin['total_savings_egp']:,.0f} EGP",
                    className="text-center text-success mb-1"),
            html.Div(f"{fin['savings_pct']:.1f}% cost reduction · "
                     f"{tech['downtime_reduction_pct']:.0f}% less downtime · "
                     f"{tech['units_saved']:,} units saved",
                     className="text-center text-muted"),
        ]), color="success", outline=True),
    ]))




# ================================================================
# 11b) Sound Alert (clientside, respects the Mute switch)
# ================================================================
app.clientside_callback(
    """
    function(signal, muted) {
        if (!signal || muted) { return ''; }
        var a = document.getElementById('beep-audio');
        if (a) { try { a.currentTime = 0; a.play(); } catch (e) {} }
        return '';
    }
    """,
    Output("beep-out", "children"),
    Input("alert-signal", "children"),
    State("mute-switch", "value"),
    prevent_initial_call=True,
)


# ================================================================
# 12) Run App
# ================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("PRIME-Factory Dashboard v1.0")
    print("Opening http://127.0.0.1:8050")
    print("=" * 60)
    app.run(debug=True, host="0.0.0.0", port=8050)
