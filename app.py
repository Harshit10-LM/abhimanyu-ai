"""Firmware-Alchemist: Unified Embedded AI Co-Pilot & Interactive Circuit Simulator.

Integrates conditional firmware code auditing, agentic self-correction loop (AI.duino & Tiesta),
pin conflict analysis and memory advising (Arduino-Copilot), PlatformIO/Arduino project awareness (Cyrena),
Wokwi/Tinkercad-inspired interactive circuit editing, and AI-powered visual circuit reconstruction.
"""

import json
import os
from typing import Dict, List, Optional
from PIL import Image
import streamlit as st
import streamlit.components.v1 as components

from core.board_database import BOARDS, BoardSpec, get_board, list_boards
from core.circuit_graph import (
    CircuitGraph,
    build_suggested_circuit,
    export_circuit_json,
    import_circuit_json,
    reset_circuit,
)
from core.circuit_reconstructor import reconstruct_circuit_from_vision
from core.circuit_validator import CircuitValidator
from core.code_parser import CodeParser
from core.image_processor import ImageProcessor
from core.agentic_patcher import AgenticPatcher, CompilerDiagnostic, PatchProposal, SelfCorrectionAttempt
from core.architecture_mapper import ArchitectureMapper
from core.memory_advisor import MemoryAdvisor
from core.optimizer import NonBlockingOptimizer
from core.pin_conflict_analyzer import PinConflictAnalyzer
from core.serial_diagnostics import SerialDiagnostics
from core.llm_client import (
    DEFAULT_MODEL,
    DEFAULT_OLLAMA_HOST,
    OllamaClientManager,
)
from core.renderer import HardwareRenderer
from core.schemas import (
    AuditResponse,
    CircuitDocument,
    CodeIssue,
    DiagnosisResult,
    InventoryResult,
    SimulationFrame,
    SimulationPlan,
)
from core.simulator import HardwareSimulator
from core.static_analyzer import StaticAnalyzer
from core.vision_debugger import VisionDebugger

# Set Streamlit Page Configuration (No emojis)
st.set_page_config(
    page_title="Firmware-Alchemist | Unified Embedded AI Co-Pilot & Circuit Simulator",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Beige & Maroon Engineering CSS
st.markdown(
    """
    <style>
    :root {
        --bg-main: #fbf8f3;
        --bg-card: #f5efe6;
        --bg-subtle: #ede2d3;
        --border-color: #dcd0bf;
        --border-accent: #c8b6a0;
        --text-primary: #2b2523;
        --text-secondary: #5e524d;
        --text-muted: #8a7d75;
        --maroon-primary: #781d32;
        --maroon-dark: #501322;
        --maroon-light: #9e2a44;
        --maroon-bg: rgba(120, 29, 50, 0.08);
        --green-accent: #2e7d32;
        --green-bg: rgba(46, 125, 50, 0.10);
        --amber-accent: #b45309;
        --amber-bg: rgba(180, 83, 9, 0.10);
        --red-accent: #9e2a2b;
        --red-bg: rgba(158, 42, 43, 0.10);
    }

    body, .stApp {
        background-color: var(--bg-main) !important;
        color: var(--text-primary) !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    }

    .main .block-container {
        padding-top: 1.0rem;
        padding-bottom: 2.0rem;
        max-width: 1600px;
    }

    .app-header {
        background: linear-gradient(135deg, #f5efe6 0%, #ede2d3 100%);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 14px 20px;
        margin-bottom: 14px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }
    .app-title {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 22px;
        font-weight: 800;
        color: var(--maroon-primary);
        letter-spacing: 0.6px;
        margin: 0;
    }
    .app-subtitle {
        color: var(--text-secondary);
        font-size: 12px;
        margin-top: 3px;
    }
    .status-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    .badge-online {
        background-color: var(--green-bg);
        color: var(--green-accent);
        border: 1px solid var(--green-accent);
    }
    .badge-offline {
        background-color: var(--amber-bg);
        color: var(--amber-accent);
        border: 1px solid var(--amber-accent);
    }
    .badge-alert {
        background-color: var(--red-bg);
        color: var(--red-accent);
        border: 1px solid var(--red-accent);
    }
    .badge-maroon {
        background-color: var(--maroon-bg);
        color: var(--maroon-primary);
        border: 1px solid var(--maroon-primary);
    }
    .panel-card {
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 6px;
        padding: 12px 16px;
        margin-bottom: 12px;
    }
    .demo-banner {
        background-color: var(--maroon-bg);
        border: 1px solid #c88292;
        border-radius: 6px;
        padding: 8px 14px;
        margin-bottom: 12px;
        color: var(--maroon-dark);
        font-weight: 600;
        font-size: 12px;
    }

    button[kind="primary"] {
        background-color: var(--maroon-primary) !important;
        color: #ffffff !important;
        border: none !important;
        font-weight: 700 !important;
    }
    button[kind="primary"]:hover {
        background-color: var(--maroon-dark) !important;
    }
    button[kind="secondary"] {
        background-color: #ede2d3 !important;
        color: var(--text-primary) !important;
        border: 1px solid #d8c6b0 !important;
        font-weight: 600 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Custom Component Declaration (points to built Vite bundle)
COMPONENT_DIST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")
if os.path.exists(COMPONENT_DIST_PATH):
    _circuit_editor_comp = components.declare_component("circuit_editor", path=COMPONENT_DIST_PATH)
else:
    _circuit_editor_comp = None


@st.cache_resource
def get_llm_manager() -> OllamaClientManager:
    return OllamaClientManager()


@st.cache_resource
def get_renderer() -> HardwareRenderer:
    return HardwareRenderer(assets_dir="assets")


# Initialize Session State
def init_session_state():
    if "source_code" not in st.session_state:
        st.session_state.source_code = """// Arduino / C++ Embedded Firmware
#define LED_PIN 13

void setup() {
  pinMode(LED_PIN, OUTPUT);
}

void loop() {
  digitalWrite(LED_PIN, HIGH);
  delay(1000);
  digitalWrite(LED_PIN, LOW);
  delay(1000);
}
"""

    if "expected_behavior" not in st.session_state:
        st.session_state.expected_behavior = ""

    if "target_board_id" not in st.session_state:
        st.session_state.target_board_id = "arduino_uno"

    # Gating & Audit Status: 'UNAUDITED', 'ERRORS_DETECTED', 'VALID'
    if "code_status" not in st.session_state:
        st.session_state.code_status = "UNAUDITED"
    if "audit_issues" not in st.session_state:
        st.session_state.audit_issues = []
    if "audit_summary" not in st.session_state:
        st.session_state.audit_summary = None
    if "significant_errors" not in st.session_state:
        st.session_state.significant_errors = []

    # Circuit Document & Simulation State
    if "simulation_plan" not in st.session_state:
        st.session_state.simulation_plan = None
    if "simulation_frames" not in st.session_state:
        st.session_state.simulation_frames = []
    if "current_frame_idx" not in st.session_state:
        st.session_state.current_frame_idx = 0
    if "virtual_pin_states" not in st.session_state:
        st.session_state.virtual_pin_states = {}
    if "circuit_doc" not in st.session_state or st.session_state.circuit_doc is None:
        parser = CodeParser(max_duration_ms=6000)
        init_plan = parser.parse(st.session_state.source_code)
        st.session_state.simulation_plan = init_plan
        st.session_state.circuit_doc = build_suggested_circuit(st.session_state.target_board_id, init_plan)

    # Agentic Patching & Self-Correction Loop
    if "proposed_patch" not in st.session_state:
        st.session_state.proposed_patch = None
    if "backup_code" not in st.session_state:
        st.session_state.backup_code = None
    if "self_correction_attempts" not in st.session_state:
        st.session_state.self_correction_attempts = []

    # Phase 2 Vision Debugger states
    if "phase2_image_bytes" not in st.session_state:
        st.session_state.phase2_image_bytes = None
    if "phase2_components" not in st.session_state:
        st.session_state.phase2_components = ""
    if "phase2_symptom" not in st.session_state:
        st.session_state.phase2_symptom = ""
    if "phase2_inventory" not in st.session_state:
        st.session_state.phase2_inventory = None
    if "phase2_diagnosis" not in st.session_state:
        st.session_state.phase2_diagnosis = None
    if "phase2_reconstructed_circuit" not in st.session_state:
        st.session_state.phase2_reconstructed_circuit = None
    if "phase2_is_demo" not in st.session_state:
        st.session_state.phase2_is_demo = False

    # Serial Diagnostics states
    if "serial_log_input" not in st.session_state:
        st.session_state.serial_log_input = ""
    if "serial_diagnosis" not in st.session_state:
        st.session_state.serial_diagnosis = None


init_session_state()
llm = get_llm_manager()
renderer = get_renderer()
is_ollama_alive = llm.check_connection()
local_models = llm.list_local_models() if is_ollama_alive else []

# SIDEBAR CONFIGURATION
with st.sidebar:
    st.markdown("### ENGINE CONFIGURATION")

    # Local Ollama Status
    if is_ollama_alive:
        st.markdown(
            '<div class="status-badge badge-online">OLLAMA CONNECTED (127.0.0.1:11434)</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="status-badge badge-offline">OLLAMA OFFLINE</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Local Ollama server not detected. Deterministic parsing, static audit, and interactive circuit simulation remain fully operational."
        )
        st.code("ollama serve", language="bash")

    st.markdown("---")

    # Target Microcontroller Board
    st.markdown("#### Microcontroller Target")
    board_options = list_boards()
    board_dict = {b[0]: b[1] for b in board_options}

    prev_board_id = st.session_state.target_board_id
    selected_board_id = st.selectbox(
        "Select Board Target",
        options=[b[0] for b in board_options],
        format_func=lambda bid: board_dict.get(bid, bid),
        index=[b[0] for b in board_options].index(prev_board_id),
    )
    if selected_board_id != prev_board_id:
        st.session_state.target_board_id = selected_board_id
        st.session_state.code_status = "UNAUDITED"
        st.session_state.circuit_doc = None
        st.session_state.simulation_plan = None
        st.session_state.simulation_frames = []
        st.session_state.proposed_patch = None
        st.session_state.self_correction_attempts = []
        st.rerun()

    current_board = get_board(selected_board_id)

    # Display Board Specs
    st.caption(
        f"**MCU:** {current_board.mcu}  \n"
        f"**Logic:** {current_board.logic_voltage}V  \n"
        f"**ADC:** {current_board.analog_resolution_bits}-bit | **PWM:** {current_board.pwm_resolution_bits}-bit"
    )

    st.markdown("---")

    # Local Model Selection
    st.markdown("#### Local AI Model")
    if local_models:
        default_idx = 0
        for i, m in enumerate(local_models):
            if "gemma4" in m.lower() or "gemma" in m.lower():
                default_idx = i
                break
        selected_model = st.selectbox("Active Local Model", options=local_models, index=default_idx)
    else:
        selected_model = st.text_input("Model Name", value=DEFAULT_MODEL)
        st.caption("To pull the recommended offline model:")
        st.code(f"ollama pull {DEFAULT_MODEL}", language="bash")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("Ping Ollama", width="stretch"):
            alive = llm.check_connection()
            if alive:
                st.success("Ollama OK!")
            else:
                st.error("Unreachable")
    with col_btn2:
        if st.button("Unload Model", width="stretch", help="Evict model from unified RAM"):
            if selected_model and is_ollama_alive:
                llm.unload_model(selected_model)
                st.info(f"Model '{selected_model}' evicted from RAM.")

    st.markdown("---")
    st.markdown("#### Reference Architectures")
    st.caption(
        "• **AI.duino:** Agentic coding loop, delay-to-millis optimizer, serial diagnosis.  \n"
        "• **Arduino-Copilot:** Pin conflict doctor, wiring table, memory advisor.  \n"
        "• **Cyrena:** Flat sketch model, PlatformIO indexer, embedded safety.  \n"
        "• **Tiesta:** Hardware-in-the-loop serial detection, bounded self-correction."
    )

# MAIN APP HEADER
st.markdown(
    f"""
    <div class="app-header">
        <div>
            <h1 class="app-title">FIRMWARE-ALCHEMIST</h1>
            <div class="app-subtitle">Offline Embedded AI Co-Pilot & Unified Interactive Circuit Simulator</div>
        </div>
        <div>
            <span class="status-badge {'badge-online' if is_ollama_alive else 'badge-offline'}">
                {'LOCAL INFERENCE ACTIVE' if is_ollama_alive else 'DETERMINISTIC OFFLINE MODE'}
            </span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

col_meta1, col_meta2, col_meta3, col_meta4 = st.columns(4)
with col_meta1:
    st.caption(f"**Target Board:** {current_board.display_name}")
with col_meta2:
    st.caption(f"**Inference Model:** `{selected_model}`")
with col_meta3:
    st.caption(f"**Host:** `127.0.0.1:11434` ({'UP' if is_ollama_alive else 'DOWN'})")
with col_meta4:
    st.caption(f"**Status:** `{st.session_state.code_status}`")


# Helper function to classify significant errors that block simulation
def is_significant_error(issue: CodeIssue) -> bool:
    """Identifies confirmed compilation, functional logic, or hardware configuration errors."""
    if issue.severity == "high":
        return True
    if issue.category in ("syntax", "hardware") and issue.confidence == "high":
        return True
    lower_iss = issue.issue.lower()
    if any(k in lower_iss for k in ("missing pinmode", "delay inside interrupt", "input-only", "invalid pwm", "non-existent pin")):
        return True
    return False


# =========================================================================
# UNIFIED MASTER WORKBENCH (DUAL CO-LOCATED MASTER COLUMNS)
# =========================================================================
col_left, col_right = st.columns([1.05, 1.35], gap="large")


# -------------------------------------------------------------------------
# MASTER LEFT COLUMN: FIRMWARE, AGENTIC SELF-CORRECTION & EMBEDDED METRICS
# -------------------------------------------------------------------------
with col_left:
    st.markdown("### Firmware & Agentic Co-Pilot")
    st.caption("Write embedded C++ firmware, run static and AI auditing, or trigger autonomous self-repair.")

    tpl_col1, tpl_col2 = st.columns([1.5, 1])
    with tpl_col1:
        st.markdown("#### Firmware Source Code")
    with tpl_col2:
        if "prev_tpl_choice" not in st.session_state:
            st.session_state.prev_tpl_choice = "-- Select Code Template --"

        tpl_choice = st.selectbox(
            "Load Template",
            options=[
                "-- Select Code Template --",
                "Demo Buggy Sketch (Missing pinMode & Stuck LED)",
                "Correct Blinking LED",
                "Interactive Button & LED",
                "PWM Analog Waveform",
            ],
            label_visibility="collapsed",
        )
        if tpl_choice != st.session_state.prev_tpl_choice:
            st.session_state.prev_tpl_choice = tpl_choice
            if tpl_choice == "Demo Buggy Sketch (Missing pinMode & Stuck LED)":
                demo_path = os.path.join("assets", "demo_buggy_sketch.ino")
                if os.path.exists(demo_path):
                    with open(demo_path, "r", encoding="utf-8") as f:
                        st.session_state.source_code = f.read()
                st.session_state.expected_behavior = "The LED should illuminate only while the button is pressed."
                st.session_state.code_status = "UNAUDITED"
                st.session_state.simulation_frames = []
                parser = CodeParser(max_duration_ms=6000)
                plan = parser.parse(source_code=st.session_state.source_code)
                st.session_state.simulation_plan = plan
                st.session_state.circuit_doc = build_suggested_circuit(current_board.id, plan)
                st.session_state.proposed_patch = None
                st.session_state.self_correction_attempts = []
                st.rerun()
            elif tpl_choice == "Correct Blinking LED":
                st.session_state.source_code = """// Correct Blinking LED
#define LED_PIN 13

void setup() {
  pinMode(LED_PIN, OUTPUT);
}

void loop() {
  digitalWrite(LED_PIN, HIGH);
  delay(1000);
  digitalWrite(LED_PIN, LOW);
  delay(1000);
}
"""
                st.session_state.expected_behavior = "Blink LED on Pin 13 at 1 second intervals."
                st.session_state.code_status = "UNAUDITED"
                st.session_state.simulation_frames = []
                parser = CodeParser(max_duration_ms=6000)
                plan = parser.parse(source_code=st.session_state.source_code)
                st.session_state.simulation_plan = plan
                st.session_state.circuit_doc = build_suggested_circuit(current_board.id, plan)
                st.session_state.proposed_patch = None
                st.session_state.self_correction_attempts = []
                st.rerun()
            elif tpl_choice == "Interactive Button & LED":
                st.session_state.source_code = """// Interactive Pushbutton & LED
#define BUTTON_PIN 2
#define LED_PIN 13

void setup() {
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);
}

void loop() {
  int buttonState = digitalRead(BUTTON_PIN);
  if (buttonState == LOW) {
    digitalWrite(LED_PIN, HIGH);
  } else {
    digitalWrite(LED_PIN, LOW);
  }
}
"""
                st.session_state.expected_behavior = "Light LED when pushbutton is pressed (active-low INPUT_PULLUP)."
                st.session_state.code_status = "UNAUDITED"
                st.session_state.simulation_frames = []
                parser = CodeParser(max_duration_ms=6000)
                plan = parser.parse(source_code=st.session_state.source_code)
                st.session_state.simulation_plan = plan
                st.session_state.circuit_doc = build_suggested_circuit(current_board.id, plan)
                st.session_state.proposed_patch = None
                st.session_state.self_correction_attempts = []
                st.rerun()
            elif tpl_choice == "PWM Analog Waveform":
                st.session_state.source_code = """// PWM Analog Waveform Output
#define PWM_PIN 9

void setup() {
  pinMode(PWM_PIN, OUTPUT);
}

void loop() {
  analogWrite(PWM_PIN, 64);   // ~25% Duty Cycle
  delay(1000);
  analogWrite(PWM_PIN, 200);  // ~78% Duty Cycle
  delay(1000);
}
"""
                st.session_state.expected_behavior = "Modulate PWM duty cycle on pin 9 between 25% and 78%."
                st.session_state.code_status = "UNAUDITED"
                st.session_state.simulation_frames = []
                parser = CodeParser(max_duration_ms=6000)
                plan = parser.parse(source_code=st.session_state.source_code)
                st.session_state.simulation_plan = plan
                st.session_state.circuit_doc = build_suggested_circuit(current_board.id, plan)
                st.session_state.proposed_patch = None
                st.session_state.self_correction_attempts = []
                st.rerun()

    code_input = st.text_area(
        "C++ / Arduino Sketch",
        value=st.session_state.source_code,
        height=280,
        key="code_editor_area",
    )
    st.session_state.source_code = code_input

    exp_input = st.text_input(
        "Expected Hardware Behavior (Optional)",
        value=st.session_state.expected_behavior,
        placeholder="e.g. The LED should blink only while the button is pressed.",
    )
    st.session_state.expected_behavior = exp_input

    # Action Buttons Deck
    act_col1, act_col2, act_col3 = st.columns([1.3, 1.5, 1])
    with act_col1:
        run_audit = st.button("Audit & Validate", width="stretch", type="primary")
    with act_col2:
        run_auto_loop = st.button("Run Auto-Fix Loop", width="stretch")
    with act_col3:
        clear_fw = st.button("Clear", width="stretch")

    if clear_fw:
        st.session_state.source_code = ""
        st.session_state.expected_behavior = ""
        st.session_state.code_status = "UNAUDITED"
        st.session_state.audit_issues = []
        st.session_state.significant_errors = []
        st.session_state.circuit_doc = None
        st.session_state.simulation_plan = None
        st.session_state.simulation_frames = []
        st.session_state.proposed_patch = None
        st.session_state.self_correction_attempts = []
        st.rerun()

    # AUTONOMOUS SELF-CORRECTION LOOP (AI.duino / Arduino-Copilot / Tiesta)
    if run_auto_loop:
        with st.spinner("Executing bounded compile-and-fix loop (Max 3 attempts)..."):
            patcher = AgenticPatcher(board=current_board)
            fixed_code, attempts, is_fixed = patcher.run_autonomous_loop(
                st.session_state.source_code, max_attempts=3
            )
            st.session_state.backup_code = st.session_state.source_code
            st.session_state.source_code = fixed_code
            st.session_state.self_correction_attempts = attempts

            if is_fixed:
                st.session_state.code_status = "VALID"
                parser = CodeParser(max_duration_ms=6000)
                plan = parser.parse(source_code=fixed_code, virtual_inputs=st.session_state.virtual_pin_states)
                st.session_state.simulation_plan = plan
                st.session_state.circuit_doc = build_suggested_circuit(current_board.id, plan)
                sim_engine = HardwareSimulator(step_ms=100, board_id=current_board.id)
                st.session_state.simulation_frames = sim_engine.simulate(
                    plan=plan, duration_ms=6000, circuit_doc=st.session_state.circuit_doc
                )
                st.session_state.current_frame_idx = 0
            else:
                st.session_state.code_status = "ERRORS_DETECTED"
        st.rerun()

    # STANDARD AUDIT EXECUTION
    if run_audit or st.session_state.code_status == "REANALYZE":
        with st.spinner("Analyzing firmware static rules and hardware constraints..."):
            analyzer = StaticAnalyzer(board=current_board)
            static_issues = analyzer.analyze(
                st.session_state.source_code,
                expected_behavior=st.session_state.expected_behavior,
            )

            ai_issues: List[CodeIssue] = []
            summary_text = ""

            if is_ollama_alive and llm.is_model_available(selected_model):
                try:
                    ai_resp: AuditResponse = llm.audit_firmware(
                        source_code=st.session_state.source_code,
                        board=current_board,
                        expected_behavior=st.session_state.expected_behavior,
                        model=selected_model,
                    )
                    summary_text = ai_resp.summary
                    ai_issues = StaticAnalyzer.validate_and_filter_ai_issues(
                        ai_resp.issues, st.session_state.source_code
                    )
                except Exception as exc:
                    st.caption(f"Local AI audit note: {exc}. Deterministic audit complete.")

            all_issues = analyzer._deduplicate_issues(static_issues + ai_issues)
            sig_errors = [iss for iss in all_issues if is_significant_error(iss)]

            st.session_state.audit_issues = all_issues
            st.session_state.significant_errors = sig_errors
            st.session_state.audit_summary = summary_text or "Deterministic audit complete."

            if sig_errors:
                st.session_state.code_status = "ERRORS_DETECTED"
                st.session_state.simulation_frames = []
            else:
                st.session_state.code_status = "VALID"
                parser = CodeParser(max_duration_ms=6000)
                plan = parser.parse(
                    source_code=st.session_state.source_code,
                    virtual_inputs=st.session_state.virtual_pin_states,
                )
                st.session_state.simulation_plan = plan
                st.session_state.circuit_doc = build_suggested_circuit(current_board.id, plan)
                sim_engine = HardwareSimulator(step_ms=100, board_id=current_board.id)
                st.session_state.simulation_frames = sim_engine.simulate(
                    plan=plan,
                    duration_ms=6000,
                    circuit_doc=st.session_state.circuit_doc,
                )
                st.session_state.current_frame_idx = 0
        st.rerun()

    # AUTONOMOUS LOOP ATTEMPT HISTORY DISPLAY
    if st.session_state.self_correction_attempts:
        with st.container():
            st.markdown("##### Autonomous Self-Correction Log")
            for att in st.session_state.self_correction_attempts:
                status_color = "var(--green-accent)" if att.success else "var(--amber-accent)"
                st.markdown(
                    f"""
                    <div style="background-color: #ffffff; border-left: 3px solid {status_color}; border: 1px solid var(--border-color); padding: 8px 12px; border-radius: 4px; margin-bottom: 6px; font-size: 11px;">
                        <strong>Attempt {att.attempt_number}:</strong> {att.status_message}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # AUDIT RESULTS & SUPERVISED PATCH PROPOSAL
    if st.session_state.code_status == "ERRORS_DETECTED":
        st.error("**CODE ISSUES DETECTED — RESOLVE BEFORE SIMULATION**")
        for iss in st.session_state.significant_errors:
            st.markdown(
                f"""
                <div style="background-color: #ffffff; border-left: 4px solid var(--red-accent); border: 1px solid var(--border-color); padding: 10px 14px; border-radius: 4px; margin-bottom: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <span style="color: var(--red-accent); font-weight: 700; font-size: 12px;">Problem: {iss.issue}</span>
                        <span style="background: var(--bg-subtle); color: var(--maroon-primary); padding: 2px 6px; border-radius: 4px; font-size: 10px; font-family: monospace; font-weight: 700;">Line {iss.line}</span>
                    </div>
                    <div style="font-size: 11px; color: var(--text-secondary); margin-bottom: 4px;">
                        <strong>Explanation:</strong> {iss.impact}
                    </div>
                    <div style="font-size: 11px; color: var(--green-accent);">
                        <strong>Suggested Fix:</strong> <code>{iss.fix}</code>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        p_col1, p_col2 = st.columns(2)
        with p_col1:
            if st.button("Synthesize Fix Patch", width="stretch", type="primary"):
                patcher = AgenticPatcher(board=current_board)
                diags = [
                    CompilerDiagnostic(file="sketch.ino", line=iss.line, column=1, severity="error", message=iss.issue)
                    for iss in st.session_state.significant_errors
                ]
                proposal = patcher.propose_fix_patch(st.session_state.source_code, diags)
                st.session_state.proposed_patch = proposal
                st.rerun()
        with p_col2:
            if st.button("Re-audit Source", width="stretch"):
                st.session_state.code_status = "REANALYZE"
                st.rerun()

    if st.session_state.proposed_patch:
        p = st.session_state.proposed_patch
        st.markdown("##### Supervised Code Patch Review")
        st.info(f"**Correction:** {p.reason}")
        st.code(p.diff, language="diff")

        app_col1, app_col2 = st.columns(2)
        with app_col1:
            if st.button("Approve & Apply Patch", width="stretch", type="primary", key="approve_patch_main"):
                st.session_state.backup_code = st.session_state.source_code
                st.session_state.source_code = p.proposed_code
                st.session_state.proposed_patch = None
                st.session_state.code_status = "REANALYZE"
                st.success("Patch applied! Re-analyzing code...")
                st.rerun()
        with app_col2:
            if st.button("Discard Proposal", width="stretch", key="discard_patch_main"):
                st.session_state.proposed_patch = None
                st.rerun()

    elif st.session_state.code_status == "VALID":
        st.success("**CODE VALID — SIMULATION UNLOCKED**")

    # NON-BLOCKING MILLIS() OPTIMIZER (AI.duino)
    with st.expander("Non-Blocking millis() State-Machine Optimizer (AI.duino)", expanded=False):
        st.caption("Converts blocking delay() calls into a non-blocking timestamp scheduler.")
        opt_res = NonBlockingOptimizer.analyze_and_optimize(st.session_state.source_code)
        if opt_res.is_optimizable:
            st.info(opt_res.explanation)
            st.code(opt_res.optimized_code, language="cpp")
            if st.button("Apply millis() Refactor to Editor", width="stretch"):
                st.session_state.backup_code = st.session_state.source_code
                st.session_state.source_code = opt_res.optimized_code
                st.session_state.code_status = "UNAUDITED"
                st.success("Applied non-blocking refactor! Click Audit to verify.")
                st.rerun()
        else:
            st.success("Sketch does not contain blocking delay() loops. It is already non-blocking!")

    # FLASH & SRAM MEMORY ADVISOR (Arduino-Copilot)
    with st.expander("Flash & SRAM Memory Advisor (Arduino-Copilot)", expanded=False):
        mem_advisor = MemoryAdvisor(board=current_board)
        mem_report = mem_advisor.analyze(st.session_state.source_code)
        st.markdown(f"**Target:** {mem_report.board_name}")
        st.markdown(f"**Flash Program:** `{mem_report.flash_used_bytes} / {mem_report.flash_total_bytes} bytes` ({mem_report.flash_pct}%)")
        st.progress(min(1.0, mem_report.flash_pct / 100.0))
        st.markdown(f"**SRAM Dynamic:** `{mem_report.sram_used_bytes} / {mem_report.sram_total_bytes} bytes` ({mem_report.sram_pct}%)")
        st.progress(min(1.0, mem_report.sram_pct / 100.0))
        for mo in mem_report.optimizations:
            st.caption(f"• Tip: {mo}")

    # PIN CONFLICTS & WIRING TABLE (Arduino-Copilot)
    with st.expander("Pin Conflict Doctor & Wiring Netlist (Arduino-Copilot)", expanded=False):
        pin_analyzer = PinConflictAnalyzer(board=current_board)
        conflicts, wiring_entries, buses = pin_analyzer.analyze(st.session_state.source_code)
        if buses:
            st.caption(f"**Buses:** {', '.join(buses)}")
        for c in conflicts:
            st.error(f"**{c.title}:** {c.description}")
        st.markdown("###### MCU Pin-to-Component Wiring Table")
        wiring_markdown = "| MCU Pin | Component | Component Pin | Purpose |\n|---|---|---|---|\n"
        for w in wiring_entries:
            wiring_markdown += f"| `{w.mcu_pin}` | {w.component_name} | `{w.component_pin}` | {w.purpose} |\n"
        st.markdown(wiring_markdown)

    # PROJECT ARCHITECTURE MAP (Cyrena & Tiesta)
    with st.expander("Project Architecture Topology Map (Cyrena / Tiesta)", expanded=False):
        arch_diagram = ArchitectureMapper.generate_mermaid_diagram(
            board=current_board,
            plan=st.session_state.simulation_plan,
            circuit_doc=st.session_state.circuit_doc,
        )
        st.markdown(f"```mermaid\n{arch_diagram}\n```")


# -------------------------------------------------------------------------
# MASTER RIGHT COLUMN: INTERACTIVE CIRCUIT SIMULATOR, VISION & SERIAL LAB
# -------------------------------------------------------------------------
with col_right:
    s_col1, s_col2 = st.columns([2.5, 1.2])
    with s_col1:
        st.markdown("### Interactive Circuit Studio & Live Digital Twin")
        st.caption("Full Wokwi/Tinkercad-inspired circuit workspace, physical netlist simulator, and vision reconstruction.")
    with s_col2:
        if st.button("Sync Circuit with Code", width="stretch", help="Rebuild breadboard wiring directly from active sketch"):
            parser = CodeParser(max_duration_ms=6000)
            plan = parser.parse(
                source_code=st.session_state.source_code,
                virtual_inputs=st.session_state.virtual_pin_states,
            )
            st.session_state.simulation_plan = plan
            st.session_state.circuit_doc = build_suggested_circuit(current_board.id, plan)
            sim_engine = HardwareSimulator(step_ms=100, board_id=current_board.id)
            st.session_state.simulation_frames = sim_engine.simulate(
                plan=plan,
                duration_ms=6000,
                circuit_doc=st.session_state.circuit_doc,
            )
            st.session_state.current_frame_idx = 0
            st.rerun()

    if st.session_state.code_status == "ERRORS_DETECTED":
        st.warning(
            "Circuit simulation paused while firmware errors remain unresolved. "
            "Click **'Run Auto-Fix Loop'** on the left to repair the sketch and initialize the breadboard."
        )

    elif st.session_state.code_status == "UNAUDITED":
        st.info("Click **'Audit & Validate'** on the left to initialize the digital twin.")

    # 1. RENDER REACT INTERACTIVE CIRCUIT CANVAS
    if _circuit_editor_comp is not None and st.session_state.circuit_doc:
        frames_payload = [f.model_dump() for f in st.session_state.simulation_frames]
        circuit_payload = st.session_state.circuit_doc.model_dump()

        editor_event = _circuit_editor_comp(
            circuit=circuit_payload,
            simulation_frames=frames_payload,
            is_running=st.session_state.code_status == "VALID",
            current_frame_idx=st.session_state.current_frame_idx,
            key="unified_circuit_editor",
        )

        if editor_event and isinstance(editor_event, dict):
            action = editor_event.get("action")
            if action == "circuit_updated" and editor_event.get("circuit"):
                new_circuit = CircuitDocument.model_validate(editor_event["circuit"])
                st.session_state.circuit_doc = new_circuit
                if st.session_state.simulation_plan:
                    sim_engine = HardwareSimulator(step_ms=100, board_id=current_board.id)
                    st.session_state.simulation_frames = sim_engine.simulate(
                        plan=st.session_state.simulation_plan,
                        duration_ms=6000,
                        circuit_doc=new_circuit,
                    )
    elif st.session_state.code_status == "VALID" and not st.session_state.circuit_doc:
        parser = CodeParser(max_duration_ms=6000)
        plan = parser.parse(source_code=st.session_state.source_code, virtual_inputs=st.session_state.virtual_pin_states)
        st.session_state.simulation_plan = plan
        st.session_state.circuit_doc = build_suggested_circuit(current_board.id, plan)
        sim_engine = HardwareSimulator(step_ms=100, board_id=current_board.id)
        st.session_state.simulation_frames = sim_engine.simulate(
            plan=plan,
            duration_ms=6000,
            circuit_doc=st.session_state.circuit_doc,
        )
        st.rerun()

    # Waveform & Export Controls
    exp_col1, exp_col2 = st.columns([1.5, 1])
    with exp_col1:
        if st.session_state.simulation_frames and st.session_state.simulation_plan:
            with st.expander("Logic Waveforms Over Time", expanded=False):
                active_pins = [p.pin for p in st.session_state.simulation_plan.pins] or ["13", "2"]
                wave_img = renderer.render_waveform_chart(
                    frames=st.session_state.simulation_frames,
                    pins=active_pins,
                    width=750,
                    height=160,
                )
                st.image(wave_img, width="stretch")
    with exp_col2:
        with st.expander("Circuit JSON Export / Reset", expanded=False):
            if st.session_state.circuit_doc:
                c_json = export_circuit_json(st.session_state.circuit_doc)
                st.download_button("Export Circuit JSON", data=c_json, file_name="circuit.json", mime="application/json", width="stretch")
            if st.button("Reset Circuit", width="stretch"):
                st.session_state.circuit_doc = reset_circuit(current_board.id)
                st.rerun()

    st.markdown("---")

    # 2. AI-POWERED VISUAL CIRCUIT DEBUGGER & RECONSTRUCTION (PHASE 2)
    st.markdown("### Visual Circuit Debugger & Reconstruction")
    st.caption("Upload breadboard photograph or load fixture to inspect connections, inventory parts, and sync into simulator.")

    vis_col1, vis_col2 = st.columns([1, 1.2], gap="medium")

    with vis_col1:
        uploaded_file = st.file_uploader(
            "Upload Breadboard Photograph",
            type=["jpg", "jpeg", "png"],
            key="unified_photo_uploader",
        )
        if uploaded_file is not None:
            st.session_state.phase2_image_bytes = uploaded_file.getvalue()
            st.session_state.phase2_is_demo = False

        v_btn1, v_btn2, v_btn3 = st.columns(3)
        with v_btn1:
            run_vision = st.button("Analyze Photo", width="stretch", type="primary")
        with v_btn2:
            load_demo_p2 = st.button("Load Preset", width="stretch")
        with v_btn3:
            clear_p2 = st.button("Clear Photo", width="stretch")

        if clear_p2:
            st.session_state.phase2_image_bytes = None
            st.session_state.phase2_inventory = None
            st.session_state.phase2_diagnosis = None
            st.session_state.phase2_reconstructed_circuit = None
            st.session_state.phase2_is_demo = False
            st.rerun()

        if load_demo_p2:
            demo_img_path = os.path.join("assets", "demo_breadboard.png")
            if os.path.exists(demo_img_path):
                with open(demo_img_path, "rb") as f:
                    st.session_state.phase2_image_bytes = f.read()
            st.session_state.phase2_components = "ESP32 DevKit, 5mm Red LED, 220Ω resistor, jumper wires"
            st.session_state.phase2_symptom = "The LED is not lighting up and GPIO 2 is driven HIGH."
            debugger = VisionDebugger(llm)
            inv, diag, label = debugger.get_reproducible_demo()
            st.session_state.phase2_inventory = inv
            st.session_state.phase2_diagnosis = diag
            st.session_state.phase2_reconstructed_circuit = reconstruct_circuit_from_vision(
                inv, diag, current_board.id
            )
            st.session_state.phase2_is_demo = True
            st.rerun()

        if run_vision:
            if not st.session_state.phase2_image_bytes:
                st.error("Upload a photograph or click 'Load Preset' first.")
            elif not is_ollama_alive:
                st.error("Local Ollama is offline. Run `ollama serve` or click 'Load Preset'.")
            else:
                with st.spinner("Analyzing circuit photo via local vision model..."):
                    try:
                        debugger = VisionDebugger(llm)
                        inv, diag = debugger.run_two_step_pipeline(
                            image_bytes=st.session_state.phase2_image_bytes,
                            user_symptom=st.session_state.phase2_symptom,
                            user_components=st.session_state.phase2_components,
                            board=current_board,
                            model=selected_model,
                        )
                        st.session_state.phase2_inventory = inv
                        st.session_state.phase2_diagnosis = diag
                        st.session_state.phase2_reconstructed_circuit = reconstruct_circuit_from_vision(
                            inv, diag, current_board.id
                        )
                        st.session_state.phase2_is_demo = False
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Vision inference note: {exc}")

        # 3 View Photographic Inspection
        if st.session_state.phase2_image_bytes:
            try:
                base_img, _ = ImageProcessor.process_upload(st.session_state.phase2_image_bytes)
                inv = st.session_state.phase2_inventory
                diag = st.session_state.phase2_diagnosis

                img_view_sel = st.selectbox("Inspection View", options=["Original", "Annotated Inventory", "Fault Highlights"], label_visibility="collapsed")
                if img_view_sel == "Original":
                    st.image(base_img, caption="Original Photograph", width="stretch")
                elif img_view_sel == "Annotated Inventory":
                    if inv:
                        annotated_inv = ImageProcessor.annotate_inventory(base_img, inv)
                        st.image(annotated_inv, caption="Inventory Annotations", width="stretch")
                    else:
                        st.caption("Run analysis to generate inventory bounding boxes.")
                elif img_view_sel == "Fault Highlights":
                    if inv and diag:
                        annotated_diag = ImageProcessor.annotate_diagnostic(base_img, inv, diag)
                        st.image(annotated_diag, caption="Fault Locations & Multimeter Checkpoints", width="stretch")
                    else:
                        st.caption("Run analysis to generate fault highlights.")
            except Exception as e:
                st.caption(f"Image display note: {e}")

    with vis_col2:
        inv = st.session_state.phase2_inventory
        diag = st.session_state.phase2_diagnosis
        recon_doc = st.session_state.phase2_reconstructed_circuit

        if recon_doc:
            st.markdown(
                """
                <div style="background-color: #ffffff; border: 1px solid var(--maroon-primary); border-radius: 6px; padding: 10px 14px; margin-bottom: 10px;">
                    <div style="color: var(--maroon-primary); font-weight: 700; font-size: 12px; margin-bottom: 2px;">
                        AI-GENERATED CIRCUIT RECONSTRUCTION READY
                    </div>
                    <div style="color: var(--text-secondary); font-size: 11px;">
                        Solid lines indicate confirmed connections; dashed amber lines represent uncertain connections.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Sync Reconstructed Circuit into Simulator Above", width="stretch", type="primary"):
                st.session_state.circuit_doc = recon_doc
                st.session_state.code_status = "VALID"
                parser = CodeParser(max_duration_ms=6000)
                plan = parser.parse(source_code=st.session_state.source_code, virtual_inputs=st.session_state.virtual_pin_states)
                st.session_state.simulation_plan = plan
                sim_engine = HardwareSimulator(step_ms=100, board_id=current_board.id)
                st.session_state.simulation_frames = sim_engine.simulate(
                    plan=plan, duration_ms=6000, circuit_doc=recon_doc
                )
                st.success("Synchronized into Interactive Circuit Canvas above!")
                st.rerun()

        if inv and diag:
            with st.expander("Component Inventory & Multimeter Verification", expanded=True):
                for comp in inv.components:
                    st.markdown(f"• **{comp.name}** (`{comp.location}`)")
                for finding in diag.findings:
                    st.markdown(f"**Finding:** {finding.finding} ({finding.confidence.upper()})")
                    st.caption(f"Multimeter Check: {finding.multimeter_verification}")
                    st.caption(f"Fix: {finding.fix}")
        else:
            st.info("Upload a breadboard photo or click 'Load Preset' to run circuit diagnostics.")

    st.markdown("---")

    # 3. SERIAL DIAGNOSTICS & HARDWARE LAB (AI.duino & Tiesta)
    st.markdown("### Serial Diagnostics & Hardware-in-the-Loop")
    st.caption("Analyze serial monitor logs (baud mismatch, brownouts, watchdog resets) and scan connected host COM/USB ports.")

    ser_col1, ser_col2 = st.columns([1.2, 1], gap="medium")
    with ser_col1:
        s_sm1, s_sm2, s_sm3 = st.columns(3)
        with s_sm1:
            if st.button("Sample: Brownout", width="stretch"):
                st.session_state.serial_log_input = """[00:00:01] Booting ESP32-WROOM-32...
[00:00:01] Brownout detector was triggered
rst:0x10 (RTCWDT_RTC_RESET),boot:0x13
waiting for download"""
                st.rerun()
        with s_sm2:
            if st.button("Sample: Baud Garble", width="stretch"):
                st.session_state.serial_log_input = """⸮⸮⸮x⸮??`??⸮⸮??!??⸮\n???Hello World????⸮⸮"""
                st.rerun()
        with s_sm3:
            if st.button("Sample: I2C Timeout", width="stretch"):
                st.session_state.serial_log_input = """[00:00:01] Connecting to BME280 on I2C...\nI2C Error 2: NACK on transmit\nDevice not found at 0x76!"""
                st.rerun()

        serial_text = st.text_area("Serial Monitor Log Buffer", value=st.session_state.serial_log_input, height=110, placeholder="Paste serial output...")
        st.session_state.serial_log_input = serial_text

        s_act1, s_act2 = st.columns([1.5, 1])
        with s_act1:
            if st.button("Diagnose Serial Log", width="stretch", type="primary"):
                st.session_state.serial_diagnosis = SerialDiagnostics.analyze_log(
                    st.session_state.serial_log_input, board_id=current_board.id
                )
                st.rerun()
        with s_act2:
            if st.button("Scan USB Ports", width="stretch"):
                ports = SerialDiagnostics.list_serial_ports()
                if ports:
                    st.success(f"Found {len(ports)} port(s):")
                    for p in ports:
                        st.caption(f"• `{p['port']}`: {p['description']}")
                else:
                    st.info("No active USB serial ports found.")

    with ser_col2:
        if st.session_state.serial_diagnosis:
            sdiag = st.session_state.serial_diagnosis
            if sdiag.identified_faults:
                st.error(f"**Identified Fault:** {', '.join(sdiag.identified_faults)}")
            for fact in sdiag.observed_facts:
                st.caption(f"• Fact: {fact}")
            for hypo in sdiag.hypotheses:
                st.caption(f"• Hypothesis: {hypo}")
            for chk in sdiag.recommended_checks:
                st.caption(f"• Verification: {chk}")
        else:
            st.caption("Paste serial monitor text or click a sample failure log to diagnose.")
