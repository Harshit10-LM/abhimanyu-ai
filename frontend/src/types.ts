export interface PinReference {
  part_id: string;
  pin_id: string;
}

export interface CircuitPart {
  id: string;
  type: string;
  x: number;
  y: number;
  rotation: number;
  properties: Record<string, any>;
}

export interface CircuitWire {
  id: string;
  source: PinReference;
  target: PinReference;
  color: string;
  route?: [number, number][];
  style?: 'solid' | 'dashed';
  confidence?: 'confirmed' | 'uncertain' | 'unknown';
}

export interface CircuitDocument {
  board: string;
  parts: CircuitPart[];
  wires: CircuitWire[];
  suggested?: boolean;
  notes?: string[];
}

export interface PinSnapshot {
  pin: string;
  mode: string;
  digital_state: 'HIGH' | 'LOW' | 'UNKNOWN';
  analog_value?: number | null;
  pwm_duty?: number | null;
  component_hint?: string | null;
}

export interface SimulationFrame {
  t_ms: number;
  pin_states: Record<string, PinSnapshot>;
  active_event_description?: string | null;
  component_states?: Record<string, {
    state: 'OFF' | 'ON' | 'ACTIVE' | 'IDLE' | 'ERROR';
    is_powered?: boolean;
    brightness?: number;
    voltage_drop_v?: number;
    current_ma?: number;
    angle_deg?: number;
    analog_reading?: number;
    warnings?: string[];
    details?: Record<string, any>;
  }>;
}

export interface StreamlitRenderArgs {
  circuit: CircuitDocument;
  simulation_frames?: SimulationFrame[];
  is_running?: boolean;
  current_frame_idx?: number;
  mode?: 'edit' | 'simulate';
}

