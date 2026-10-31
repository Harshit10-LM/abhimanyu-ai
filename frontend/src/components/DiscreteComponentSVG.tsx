import React from 'react';
import { CircuitPart } from '../types';

interface DiscreteProps {
  part: CircuitPart;
  selected: boolean;
  onPinClick: (partId: string, pinId: string, clientX: number, clientY: number) => void;
  componentState?: any;
  onPropertyChange?: (partId: string, properties: Record<string, any>) => void;
}

export const DiscreteComponentSVG: React.FC<DiscreteProps> = ({
  part,
  selected,
  onPinClick,
  componentState,
  onPropertyChange,
}) => {
  switch (part.type) {
    case 'led':
      return renderLED(part, selected, onPinClick, componentState);
    case 'resistor':
      return renderResistor(part, selected, onPinClick);
    case 'button':
      return renderButton(part, selected, onPinClick, componentState, onPropertyChange);
    case 'potentiometer':
      return renderPotentiometer(part, selected, onPinClick, componentState, onPropertyChange);
    case 'buzzer':
      return renderBuzzer(part, selected, onPinClick, componentState);
    case 'servo':
      return renderServo(part, selected, onPinClick, componentState);
    case 'dht11':
    case 'hcsr04':
    case 'ldr':
      return renderSensor(part, selected, onPinClick);
    default:
      return null;
  }
};

// --- LED ---
function renderLED(
  part: CircuitPart,
  selected: boolean,
  onPinClick: (partId: string, pinId: string, x: number, y: number) => void,
  state?: any
) {
  const color = (part.properties.color || 'red').toLowerCase();
  const isPowered = state?.is_powered || state?.state === 'ON';
  const brightness = state?.brightness || (isPowered ? 255 : 0);

  const colorMap: Record<string, { off: string; on: string; glow: string }> = {
    red: { off: '#7f1d1d', on: '#ef4444', glow: 'rgba(239, 68, 68, 0.8)' },
    green: { off: '#14532d', on: '#22c55e', glow: 'rgba(34, 197, 94, 0.8)' },
    blue: { off: '#1e3a8a', on: '#3b82f6', glow: 'rgba(59, 130, 246, 0.8)' },
    yellow: { off: '#78350f', on: '#eab308', glow: 'rgba(234, 179, 8, 0.8)' },
    white: { off: '#64748b', on: '#f8fafc', glow: 'rgba(248, 250, 252, 0.9)' },
  };

  const scheme = colorMap[color] || colorMap.red;
  const bulbFill = isPowered ? scheme.on : scheme.off;

  return (
    <g transform={`translate(${part.x}, ${part.y}) rotate(${part.rotation})`}>
      {/* Selection Ring */}
      {selected && (
        <circle cx={15} cy={15} r={24} fill="none" stroke="#781d32" strokeWidth={2} strokeDasharray="4 2" />
      )}

      {/* LED Leads */}
      {/* Anode (Longer / bent lead) */}
      <line x1={8} y1={25} x2={8} y2={45} stroke="#94a3b8" strokeWidth={2.5} strokeLinecap="round" />
      <circle
        cx={8}
        cy={45}
        r={5}
        fill="#0f172a"
        stroke="#94a3b8"
        strokeWidth={1.5}
        style={{ cursor: 'pointer' }}
        onClick={(e) => {
          e.stopPropagation();
          onPinClick(part.id, 'anode', e.clientX, e.clientY);
        }}
      />
      <text x={8} y={57} fill="#cbd5e1" fontSize="7" textAnchor="middle">A (+)</text>

      {/* Cathode (Shorter lead / flat side) */}
      <line x1={22} y1={25} x2={22} y2={42} stroke="#94a3b8" strokeWidth={2.5} strokeLinecap="round" />
      <circle
        cx={22}
        cy={42}
        r={5}
        fill="#0f172a"
        stroke="#94a3b8"
        strokeWidth={1.5}
        style={{ cursor: 'pointer' }}
        onClick={(e) => {
          e.stopPropagation();
          onPinClick(part.id, 'cathode', e.clientX, e.clientY);
        }}
      />
      <text x={22} y={57} fill="#cbd5e1" fontSize="7" textAnchor="middle">K (-)</text>

      {/* LED Bulb Glow if Powered */}
      {isPowered && (
        <circle
          cx={15}
          cy={12}
          r={18}
          fill={scheme.glow}
          opacity={brightness / 255}
          filter="blur(4px)"
        />
      )}

      {/* LED Bulb Body */}
      <path
        d="M 5 22 L 5 15 C 5 7 25 7 25 15 L 25 22 Z"
        fill={bulbFill}
        stroke="#334155"
        strokeWidth={1}
      />
      {/* Specular highlight */}
      <ellipse cx={11} cy={11} rx={3} ry={5} fill="#ffffff" opacity={isPowered ? 0.6 : 0.2} transform="rotate(-20 11 11)" />
    </g>
  );
}

// --- RESISTOR ---
function renderResistor(
  part: CircuitPart,
  selected: boolean,
  onPinClick: (partId: string, pinId: string, x: number, y: number) => void
) {
  const resVal = part.properties.resistance || 220;

  return (
    <g transform={`translate(${part.x}, ${part.y}) rotate(${part.rotation})`}>
      {selected && (
        <rect x={-8} y={-8} width={66} height={26} rx={4} fill="none" stroke="#781d32" strokeWidth={2} strokeDasharray="3 2" />
      )}
      {/* Lead 1 */}
      <line x1={-15} y1={5} x2={0} y2={5} stroke="#94a3b8" strokeWidth={2} />
      <circle
        cx={-15}
        cy={5}
        r={4.5}
        fill="#0f172a"
        stroke="#94a3b8"
        strokeWidth={1.2}
        style={{ cursor: 'pointer' }}
        onClick={(e) => {
          e.stopPropagation();
          onPinClick(part.id, 'pin1', e.clientX, e.clientY);
        }}
      />

      {/* Ceramic body */}
      <rect x={0} y={0} width={50} height={10} rx={3} fill="#fef3c7" stroke="#d97706" strokeWidth={0.8} />

      {/* Color bands (e.g. 220 ohm: Red, Red, Brown, Gold) */}
      <rect x={8} y={0} width={3} height={10} fill="#ef4444" />
      <rect x={16} y={0} width={3} height={10} fill="#ef4444" />
      <rect x={24} y={0} width={3} height={10} fill="#78350f" />
      <rect x={38} y={0} width={3.5} height={10} fill="#eab308" />

      {/* Lead 2 */}
      <line x1={50} y1={5} x2={65} y2={5} stroke="#94a3b8" strokeWidth={2} />
      <circle
        cx={65}
        cy={5}
        r={4.5}
        fill="#0f172a"
        stroke="#94a3b8"
        strokeWidth={1.2}
        style={{ cursor: 'pointer' }}
        onClick={(e) => {
          e.stopPropagation();
          onPinClick(part.id, 'pin2', e.clientX, e.clientY);
        }}
      />
      <text x={25} y={-4} fill="#cbd5e1" fontSize="7" textAnchor="middle">
        {resVal}Ω
      </text>
    </g>
  );
}

// --- PUSH BUTTON ---
function renderButton(
  part: CircuitPart,
  selected: boolean,
  onPinClick: (partId: string, pinId: string, x: number, y: number) => void,
  state?: any,
  onPropertyChange?: (partId: string, prop: any) => void
) {
  const isPressed = part.properties.is_pressed || state?.is_powered || false;

  return (
    <g transform={`translate(${part.x}, ${part.y}) rotate(${part.rotation})`}>
      {selected && (
        <rect x={-4} y={-4} width={48} height={48} rx={6} fill="none" stroke="#781d32" strokeWidth={2} strokeDasharray="3 2" />
      )}
      {/* 4 Terminals */}
      {/* 1a & 1b */}
      <circle cx={0} cy={6} r={4} fill="#0f172a" stroke="#94a3b8" strokeWidth={1} style={{ cursor: 'pointer' }} onClick={(e) => { e.stopPropagation(); onPinClick(part.id, 'pin1a', e.clientX, e.clientY); }} />
      <circle cx={40} cy={6} r={4} fill="#0f172a" stroke="#94a3b8" strokeWidth={1} style={{ cursor: 'pointer' }} onClick={(e) => { e.stopPropagation(); onPinClick(part.id, 'pin1b', e.clientX, e.clientY); }} />
      {/* 2a & 2b */}
      <circle cx={0} cy={34} r={4} fill="#0f172a" stroke="#94a3b8" strokeWidth={1} style={{ cursor: 'pointer' }} onClick={(e) => { e.stopPropagation(); onPinClick(part.id, 'pin2a', e.clientX, e.clientY); }} />
      <circle cx={40} cy={34} r={4} fill="#0f172a" stroke="#94a3b8" strokeWidth={1} style={{ cursor: 'pointer' }} onClick={(e) => { e.stopPropagation(); onPinClick(part.id, 'pin2b', e.clientX, e.clientY); }} />

      {/* Button Plastic Body */}
      <rect x={4} y={4} width={32} height={32} rx={4} fill="#1e293b" stroke="#475569" strokeWidth={1.5} />

      {/* Button Cap (Clickable!) */}
      <circle
        cx={20}
        cy={20}
        r={isPressed ? 10 : 12}
        fill={isPressed ? '#38bdf8' : '#ef4444'}
        stroke="#ffffff"
        strokeWidth={1}
        filter="drop-shadow(0 2px 4px rgba(0,0,0,0.5))"
        style={{ cursor: 'pointer' }}
        onClick={(e) => {
          e.stopPropagation();
          if (onPropertyChange) {
            onPropertyChange(part.id, { is_pressed: !isPressed });
          }
        }}
      />
      <text x={20} y={48} fill="#94a3b8" fontSize="7" textAnchor="middle">
        {isPressed ? 'PRESSED' : 'CLICK ME'}
      </text>
    </g>
  );
}

// --- POTENTIOMETER ---
function renderPotentiometer(
  part: CircuitPart,
  selected: boolean,
  onPinClick: (partId: string, pinId: string, x: number, y: number) => void,
  state?: any,
  onPropertyChange?: (partId: string, prop: any) => void
) {
  const ratio = part.properties.ratio ?? 0.5;
  const angle = -135 + ratio * 270;

  return (
    <g transform={`translate(${part.x}, ${part.y}) rotate(${part.rotation})`}>
      {selected && (
        <rect x={-4} y={-4} width={58} height={68} rx={6} fill="none" stroke="#781d32" strokeWidth={2} strokeDasharray="3 2" />
      )}
      {/* 3 Terminals: pin1 (GND), wiper (Analog Out), pin2 (VCC) */}
      <circle cx={8} cy={55} r={4.5} fill="#0f172a" stroke="#94a3b8" strokeWidth={1.2} style={{ cursor: 'pointer' }} onClick={(e) => { e.stopPropagation(); onPinClick(part.id, 'pin1', e.clientX, e.clientY); }} />
      <circle cx={25} cy={55} r={4.5} fill="#0f172a" stroke="#38bdf8" strokeWidth={1.5} style={{ cursor: 'pointer' }} onClick={(e) => { e.stopPropagation(); onPinClick(part.id, 'wiper', e.clientX, e.clientY); }} />
      <circle cx={42} cy={55} r={4.5} fill="#0f172a" stroke="#94a3b8" strokeWidth={1.2} style={{ cursor: 'pointer' }} onClick={(e) => { e.stopPropagation(); onPinClick(part.id, 'pin2', e.clientX, e.clientY); }} />

      <text x={8} y={66} fill="#94a3b8" fontSize="6" textAnchor="middle">1</text>
      <text x={25} y={66} fill="#38bdf8" fontSize="6" textAnchor="middle">WIP</text>
      <text x={42} y={66} fill="#94a3b8" fontSize="6" textAnchor="middle">2</text>

      {/* Potentiometer Body */}
      <rect x={2} y={2} width={46} height={46} rx={6} fill="#0284c7" stroke="#0369a1" strokeWidth={1} />
      <circle cx={25} cy={24} r={16} fill="#e2e8f0" stroke="#94a3b8" strokeWidth={1.5} />

      {/* Rotating Dial Knob */}
      <g transform={`rotate(${angle} 25 24)`}>
        <line x1={25} y1={24} x2={25} y2={10} stroke="#ef4444" strokeWidth={3} strokeLinecap="round" />
      </g>
      <text x={25} y={-2} fill="#cbd5e1" fontSize="7" textAnchor="middle">
        {Math.round(ratio * 100)}%
      </text>
    </g>
  );
}

// --- BUZZER ---
function renderBuzzer(
  part: CircuitPart,
  selected: boolean,
  onPinClick: (partId: string, pinId: string, x: number, y: number) => void,
  state?: any
) {
  const isSounding = state?.state === 'ACTIVE' || state?.is_powered;

  return (
    <g transform={`translate(${part.x}, ${part.y}) rotate(${part.rotation})`}>
      {selected && (
        <circle cx={25} cy={25} r={28} fill="none" stroke="#781d32" strokeWidth={2} strokeDasharray="3 2" />
      )}
      {/* Sound Waves if active */}
      {isSounding && (
        <g stroke="#f59e0b" strokeWidth={2} fill="none">
          <path d="M 2 15 A 25 25 0 0 1 2 35" strokeDasharray="3 3" />
          <path d="M 48 15 A 25 25 0 0 0 48 35" strokeDasharray="3 3" />
        </g>
      )}
      {/* Body */}
      <circle cx={25} cy={25} r={22} fill="#1e293b" stroke="#475569" strokeWidth={2} />
      <circle cx={25} cy={25} r={6} fill="#0f172a" />
      <text x={14} y={18} fill="#ef4444" fontSize="10" fontWeight="bold">+</text>

      {/* Positive & Negative Leads */}
      <circle cx={14} cy={52} r={4.5} fill="#0f172a" stroke="#ef4444" strokeWidth={1.5} style={{ cursor: 'pointer' }} onClick={(e) => { e.stopPropagation(); onPinClick(part.id, 'positive', e.clientX, e.clientY); }} />
      <circle cx={36} cy={52} r={4.5} fill="#0f172a" stroke="#94a3b8" strokeWidth={1.5} style={{ cursor: 'pointer' }} onClick={(e) => { e.stopPropagation(); onPinClick(part.id, 'negative', e.clientX, e.clientY); }} />
    </g>
  );
}

// --- SERVO ---
function renderServo(
  part: CircuitPart,
  selected: boolean,
  onPinClick: (partId: string, pinId: string, x: number, y: number) => void,
  state?: any
) {
  const angle = state?.angle_deg ?? 90;

  return (
    <g transform={`translate(${part.x}, ${part.y}) rotate(${part.rotation})`}>
      {selected && (
        <rect x={-4} y={-4} width={78} height={48} rx={6} fill="none" stroke="#781d32" strokeWidth={2} strokeDasharray="3 2" />
      )}
      {/* Blue Servo Body */}
      <rect x={0} y={0} width={70} height={40} rx={4} fill="#2563eb" stroke="#1d4ed8" strokeWidth={1} />
      {/* Main Gear Spline */}
      <circle cx={22} cy={20} r={14} fill="#1e3a8a" />

      {/* Rotating Servo Horn */}
      <g transform={`rotate(${angle - 90} 22 20)`}>
        <path d="M 22 20 L 50 14 A 6 6 0 0 1 50 26 Z" fill="#ffffff" stroke="#94a3b8" strokeWidth={1} />
        <circle cx={22} cy={20} r={5} fill="#cbd5e1" />
      </g>

      {/* Pins: GND (Brown), VCC (Red), Signal (Orange) */}
      <circle cx={52} cy={48} r={4} fill="#111827" stroke="#94a3b8" style={{ cursor: 'pointer' }} onClick={(e) => { e.stopPropagation(); onPinClick(part.id, 'gnd', e.clientX, e.clientY); }} />
      <circle cx={60} cy={48} r={4} fill="#ef4444" stroke="#94a3b8" style={{ cursor: 'pointer' }} onClick={(e) => { e.stopPropagation(); onPinClick(part.id, 'vcc', e.clientX, e.clientY); }} />
      <circle cx={68} cy={48} r={4} fill="#f59e0b" stroke="#94a3b8" style={{ cursor: 'pointer' }} onClick={(e) => { e.stopPropagation(); onPinClick(part.id, 'signal', e.clientX, e.clientY); }} />
      <text x={35} y={-3} fill="#cbd5e1" fontSize="7" textAnchor="middle">SERVO {angle}°</text>
    </g>
  );
}

// --- SENSOR (DHT11, HC-SR04, LDR) ---
function renderSensor(
  part: CircuitPart,
  selected: boolean,
  onPinClick: (partId: string, pinId: string, x: number, y: number) => void
) {
  return (
    <g transform={`translate(${part.x}, ${part.y}) rotate(${part.rotation})`}>
      {selected && (
        <rect x={-4} y={-4} width={58} height={68} rx={6} fill="none" stroke="#781d32" strokeWidth={2} strokeDasharray="3 2" />
      )}
      {/* Sensor body */}
      <rect x={0} y={0} width={50} height={50} rx={4} fill="#0284c7" stroke="#0369a1" strokeWidth={1} />
      <text x={25} y={28} fill="#ffffff" fontSize="9" fontWeight="bold" textAnchor="middle">
        {part.type.toUpperCase()}
      </text>

      {/* VCC, DATA, GND */}
      <circle cx={10} cy={58} r={4} fill="#ef4444" stroke="#94a3b8" style={{ cursor: 'pointer' }} onClick={(e) => { e.stopPropagation(); onPinClick(part.id, 'vcc', e.clientX, e.clientY); }} />
      <circle cx={25} cy={58} r={4} fill="#eab308" stroke="#94a3b8" style={{ cursor: 'pointer' }} onClick={(e) => { e.stopPropagation(); onPinClick(part.id, 'data', e.clientX, e.clientY); }} />
      <circle cx={40} cy={58} r={4} fill="#111827" stroke="#94a3b8" style={{ cursor: 'pointer' }} onClick={(e) => { e.stopPropagation(); onPinClick(part.id, 'gnd', e.clientX, e.clientY); }} />
    </g>
  );
}

