import React from 'react';
import { CircuitPart } from '../types';

interface BoardSVGProps {
  part: CircuitPart;
  selected: boolean;
  onPinClick: (partId: string, pinId: string, clientX: number, clientY: number) => void;
  pinStates?: Record<string, any>;
}

export const BoardSVG: React.FC<BoardSVGProps> = ({
  part,
  selected,
  onPinClick,
  pinStates = {},
}) => {
  const type = part.type;

  if (type === 'esp32_devkit') {
    return renderESP32(part, selected, onPinClick, pinStates);
  }
  if (type === 'stm32_bluepill') {
    return renderSTM32(part, selected, onPinClick, pinStates);
  }
  return renderArduinoUno(part, selected, onPinClick, pinStates);
};

// --- ARDUINO UNO R3 ---
function renderArduinoUno(
  part: CircuitPart,
  selected: boolean,
  onPinClick: (partId: string, pinId: string, x: number, y: number) => void,
  pinStates: Record<string, any>
) {
  const width = 280;
  const height = 210;

  // Digital header pins (D0-D13, GND, AREF)
  const digitalPins = [
    'AREF', 'GND', '13', '12', '11', '10', '9', '8',
    '7', '6', '5', '4', '3', '2', '1', '0'
  ];

  // Analog & Power header pins
  const powerPins = ['IOREF', 'RESET', '3.3V', '5V', 'GND', 'GND', 'VIN'];
  const analogPins = ['A0', 'A1', 'A2', 'A3', 'A4', 'A5'];

  return (
    <g transform={`translate(${part.x}, ${part.y}) rotate(${part.rotation})`}>
      {/* PCB Body */}
      <rect
        width={width}
        height={height}
        rx={12}
        fill="#005b60"
        stroke={selected ? '#781d32' : '#003a3d'}
        strokeWidth={selected ? 3 : 1.5}
        filter="drop-shadow(0 4px 6px rgba(0,0,0,0.5))"
      />
      {/* USB Port */}
      <rect x={-8} y={30} width={42} height={32} fill="#94a3b8" rx={2} stroke="#64748b" />
      {/* Power Jack */}
      <rect x={-10} y={130} width={45} height={42} fill="#1e293b" rx={3} />

      {/* Main ATmega328P IC */}
      <rect x={120} y={120} width={90} height={26} fill="#0f172a" rx={2} stroke="#334155" />
      <text x={165} y={137} fill="#94a3b8" fontSize="8" fontFamily="monospace" textAnchor="middle">
        ATMEGA328P
      </text>

      {/* Board Label */}
      <text x={140} y={90} fill="#ffffff" fontSize="13" fontWeight="bold" letterSpacing="1">
        ARDUINO UNO
      </text>
      <text x={140} y={104} fill="#5eead4" fontSize="8" fontWeight="600">
        ITALY • R3 COMPATIBLE
      </text>

      {/* Built-in LED L (Pin 13 indicator) */}
      <circle
        cx={108}
        cy={70}
        r={4}
        fill={pinStates['13']?.digital_state === 'HIGH' ? '#fbbf24' : '#78350f'}
        filter={pinStates['13']?.digital_state === 'HIGH' ? 'drop-shadow(0 0 6px #f59e0b)' : 'none'}
      />
      <text x={116} y={73} fill="#cbd5e1" fontSize="7" fontFamily="sans-serif">L (D13)</text>

      {/* ON Power LED */}
      <circle cx={108} cy={88} r={3} fill="#22c55e" filter="drop-shadow(0 0 4px #22c55e)" />
      <text x={116} y={91} fill="#cbd5e1" fontSize="7" fontFamily="sans-serif">ON</text>

      {/* Top Header Socket Bar */}
      <rect x={70} y={10} width={195} height={18} fill="#1e293b" rx={2} />
      {digitalPins.map((p, idx) => {
        const px = 82 + idx * 11.5;
        const py = 19;
        const isHigh = pinStates[p]?.digital_state === 'HIGH';
        return (
          <g
            key={`dig_${p}_${idx}`}
            onClick={(e) => {
              e.stopPropagation();
              onPinClick(part.id, p, e.clientX, e.clientY);
            }}
            style={{ cursor: 'pointer' }}
          >
            <circle
              cx={px}
              cy={py}
              r={4}
              fill={isHigh ? '#38bdf8' : '#0f172a'}
              stroke="#64748b"
              strokeWidth={1}
            />
            <text x={px} y={38} fill="#94a3b8" fontSize="7" textAnchor="middle" fontFamily="monospace">
              {p}
            </text>
          </g>
        );
      })}

      {/* Bottom Header Sockets: Power */}
      <rect x={70} y={180} width={90} height={18} fill="#1e293b" rx={2} />
      {powerPins.map((p, idx) => {
        const px = 78 + idx * 12;
        const py = 189;
        return (
          <g
            key={`pwr_${p}_${idx}`}
            onClick={(e) => {
              e.stopPropagation();
              onPinClick(part.id, p, e.clientX, e.clientY);
            }}
            style={{ cursor: 'pointer' }}
          >
            <circle cx={px} cy={py} r={4} fill="#0f172a" stroke="#64748b" strokeWidth={1} />
            <text x={px} y={175} fill="#cbd5e1" fontSize="6.5" textAnchor="middle" fontFamily="monospace">
              {p}
            </text>
          </g>
        );
      })}

      {/* Bottom Header Sockets: Analog */}
      <rect x={180} y={180} width={85} height={18} fill="#1e293b" rx={2} />
      {analogPins.map((p, idx) => {
        const px = 190 + idx * 12.5;
        const py = 189;
        return (
          <g
            key={`ana_${p}_${idx}`}
            onClick={(e) => {
              e.stopPropagation();
              onPinClick(part.id, p, e.clientX, e.clientY);
            }}
            style={{ cursor: 'pointer' }}
          >
            <circle cx={px} cy={py} r={4} fill="#0f172a" stroke="#64748b" strokeWidth={1} />
            <text x={px} y={175} fill="#38bdf8" fontSize="6.5" textAnchor="middle" fontFamily="monospace">
              {p}
            </text>
          </g>
        );
      })}
    </g>
  );
}

// --- ESP32 DEVKIT V1 ---
function renderESP32(
  part: CircuitPart,
  selected: boolean,
  onPinClick: (partId: string, pinId: string, x: number, y: number) => void,
  pinStates: Record<string, any>
) {
  const width = 160;
  const height = 260;

  const leftPins = [
    '3V3', 'EN', 'VP', 'VN', 'G34', 'G35', 'G32', 'G33',
    'G25', 'G26', 'G27', 'G14', 'G12', 'GND', 'G13'
  ];
  const rightPins = [
    'G23', 'G22', 'TX0', 'RX0', 'G21', 'GND', 'G19', 'G18',
    'G5', 'G17', 'G16', 'G4', 'G0', 'G2', 'G15'
  ];

  return (
    <g transform={`translate(${part.x}, ${part.y}) rotate(${part.rotation})`}>
      {/* PCB */}
      <rect
        width={width}
        height={height}
        rx={8}
        fill="#1e1e24"
        stroke={selected ? '#781d32' : '#334155'}
        strokeWidth={selected ? 3 : 1.5}
        filter="drop-shadow(0 4px 6px rgba(0,0,0,0.6))"
      />
      {/* Metal RF Shield */}
      <rect x={40} y={40} width={80} height={100} fill="#94a3b8" rx={4} stroke="#cbd5e1" />
      <text x={80} y={80} fill="#0f172a" fontSize="10" fontWeight="bold" textAnchor="middle">
        ESP-WROOM-32
      </text>
      <text x={80} y={95} fill="#1e293b" fontSize="7" textAnchor="middle">
        Wi-Fi + BLE MCU
      </text>

      {/* Micro-USB Port */}
      <rect x={60} y={235} width={40} height={25} fill="#64748b" rx={2} />

      {/* On-board Blue LED (GPIO 2) */}
      <circle
        cx={50}
        cy={165}
        r={3.5}
        fill={pinStates['G2']?.digital_state === 'HIGH' || pinStates['2']?.digital_state === 'HIGH' ? '#38bdf8' : '#0369a1'}
        filter={pinStates['G2']?.digital_state === 'HIGH' || pinStates['2']?.digital_state === 'HIGH' ? 'drop-shadow(0 0 6px #38bdf8)' : 'none'}
      />
      <text x={58} y={168} fill="#94a3b8" fontSize="6.5">LED (G2)</text>

      {/* Left Pin Header */}
      {leftPins.map((p, idx) => {
        const px = 14;
        const py = 20 + idx * 15.5;
        const isHigh = pinStates[p]?.digital_state === 'HIGH' || pinStates[p.replace('G', '')]?.digital_state === 'HIGH';
        return (
          <g
            key={`esp_l_${p}`}
            onClick={(e) => {
              e.stopPropagation();
              onPinClick(part.id, p, e.clientX, e.clientY);
            }}
            style={{ cursor: 'pointer' }}
          >
            <circle cx={px} cy={py} r={4.5} fill={isHigh ? '#22c55e' : '#0f172a'} stroke="#94a3b8" strokeWidth={1} />
            <text x={px + 8} y={py + 3} fill="#cbd5e1" fontSize="7" fontFamily="monospace">
              {p}
            </text>
          </g>
        );
      })}

      {/* Right Pin Header */}
      {rightPins.map((p, idx) => {
        const px = width - 14;
        const py = 20 + idx * 15.5;
        const isHigh = pinStates[p]?.digital_state === 'HIGH' || pinStates[p.replace('G', '')]?.digital_state === 'HIGH';
        return (
          <g
            key={`esp_r_${p}`}
            onClick={(e) => {
              e.stopPropagation();
              onPinClick(part.id, p, e.clientX, e.clientY);
            }}
            style={{ cursor: 'pointer' }}
          >
            <circle cx={px} cy={py} r={4.5} fill={isHigh ? '#22c55e' : '#0f172a'} stroke="#94a3b8" strokeWidth={1} />
            <text x={px - 8} y={py + 3} fill="#cbd5e1" fontSize="7" textAnchor="end" fontFamily="monospace">
              {p}
            </text>
          </g>
        );
      })}
    </g>
  );
}

// --- STM32 BLUE PILL ---
function renderSTM32(
  part: CircuitPart,
  selected: boolean,
  onPinClick: (partId: string, pinId: string, x: number, y: number) => void,
  pinStates: Record<string, any>
) {
  const width = 140;
  const height = 270;

  const leftPins = [
    'PB12', 'PB13', 'PB14', 'PB15', 'PA8', 'PA9', 'PA10', 'PA11',
    'PA12', 'PA15', 'PB3', 'PB4', 'PB5', 'PB6', 'PB7', 'PB8', 'PB9', '5V', 'GND', '3.3V'
  ];
  const rightPins = [
    'PB11', 'PB10', 'PB1', 'PB0', 'PA7', 'PA6', 'PA5', 'PA4',
    'PA3', 'PA2', 'PA1', 'PA0', 'PC15', 'PC14', 'PC13', 'VBAT', 'NRST', '3.3V', 'GND', 'GND'
  ];

  return (
    <g transform={`translate(${part.x}, ${part.y}) rotate(${part.rotation})`}>
      <rect
        width={width}
        height={height}
        rx={6}
        fill="#1e3a8a"
        stroke={selected ? '#781d32' : '#1e40af'}
        strokeWidth={selected ? 3 : 1.5}
        filter="drop-shadow(0 4px 6px rgba(0,0,0,0.6))"
      />
      {/* MCU chip */}
      <rect x={40} y={90} width={60} height={60} fill="#0f172a" rx={2} stroke="#475569" />
      <text x={70} y={124} fill="#cbd5e1" fontSize="8" fontWeight="bold" textAnchor="middle">
        STM32F103
      </text>

      {/* PC13 LED */}
      <circle
        cx={50}
        cy={70}
        r={3.5}
        fill={pinStates['PC13']?.digital_state === 'HIGH' ? '#22c55e' : '#14532d'}
        filter={pinStates['PC13']?.digital_state === 'HIGH' ? 'drop-shadow(0 0 5px #22c55e)' : 'none'}
      />
      <text x={58} y={73} fill="#93c5fd" fontSize="6.5">LED (PC13)</text>

      {/* Left Pins */}
      {leftPins.map((p, idx) => {
        const px = 12;
        const py = 16 + idx * 12.2;
        return (
          <g
            key={`stm_l_${p}_${idx}`}
            onClick={(e) => {
              e.stopPropagation();
              onPinClick(part.id, p, e.clientX, e.clientY);
            }}
            style={{ cursor: 'pointer' }}
          >
            <circle cx={px} cy={py} r={3.8} fill="#0f172a" stroke="#94a3b8" strokeWidth={1} />
            <text x={px + 6} y={py + 2.5} fill="#e2e8f0" fontSize="6" fontFamily="monospace">
              {p}
            </text>
          </g>
        );
      })}

      {/* Right Pins */}
      {rightPins.map((p, idx) => {
        const px = width - 12;
        const py = 16 + idx * 12.2;
        return (
          <g
            key={`stm_r_${p}_${idx}`}
            onClick={(e) => {
              e.stopPropagation();
              onPinClick(part.id, p, e.clientX, e.clientY);
            }}
            style={{ cursor: 'pointer' }}
          >
            <circle cx={px} cy={py} r={3.8} fill="#0f172a" stroke="#94a3b8" strokeWidth={1} />
            <text x={px - 6} y={py + 2.5} fill="#e2e8f0" fontSize="6" textAnchor="end" fontFamily="monospace">
              {p}
            </text>
          </g>
        );
      })}
    </g>
  );
}

