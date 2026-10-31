import React, { useState, useRef, useEffect } from 'react';
import { CircuitDocument, CircuitPart, CircuitWire, PinReference } from '../types';
import { BoardSVG } from './BoardSVG';
import { BreadboardSVG } from './BreadboardSVG';
import { DiscreteComponentSVG } from './DiscreteComponentSVG';

interface CircuitCanvasProps {
  circuit: CircuitDocument;
  onCircuitChange: (newCircuit: CircuitDocument) => void;
  selectedPartId: string | null;
  onSelectPart: (partId: string | null) => void;
  selectedWireId: string | null;
  onSelectWire: (wireId: string | null) => void;
  activeWireColor: string;
  pinStates?: Record<string, any>;
  componentStates?: Record<string, any>;
  isSimulating?: boolean;
}

export const CircuitCanvas: React.FC<CircuitCanvasProps> = ({
  circuit,
  onCircuitChange,
  selectedPartId,
  onSelectPart,
  selectedWireId,
  onSelectWire,
  activeWireColor,
  pinStates = {},
  componentStates = {},
  isSimulating = false,
}) => {
  const containerRef = useRef<SVGSVGElement | null>(null);

  // Viewport zoom & pan
  const [zoom, setZoom] = useState<number>(1.0);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 40, y: 30 });
  const [isPanning, setIsPanning] = useState<boolean>(false);
  const [panStart, setPanStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Dragging component
  const [draggingPartId, setDraggingPartId] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Wire creation state
  const [drawingWire, setDrawingWire] = useState<{
    source: PinReference;
    startX: number;
    startY: number;
    currentX: number;
    currentY: number;
  } | null>(null);

  // Convert client (screen) mouse coordinates to SVG canvas coordinates
  const getCanvasCoords = (clientX: number, clientY: number) => {
    if (!containerRef.current) return { x: 0, y: 0 };
    const rect = containerRef.current.getBoundingClientRect();
    const x = (clientX - rect.left - pan.x) / zoom;
    const y = (clientY - rect.top - pan.y) / zoom;
    return { x, y };
  };

  // Resolve absolute canvas coordinates for a given (part_id, pin_id)
  const getPinAbsoluteCoords = (partId: string, pinId: string): { x: number; y: number } => {
    const part = circuit.parts.find((p) => p.id === partId);
    if (!part) return { x: 0, y: 0 };

    const px = part.x;
    const py = part.y;

    // Breadboard coordinates
    if (part.type.startsWith('breadboard')) {
      const pid = pinId.toLowerCase().trim();
      if (pid.startsWith('top_+')) return { x: px + 120, y: py + 25 };
      if (pid.startsWith('top_-')) return { x: px + 120, y: py + 42 };
      if (pid.startsWith('bot_+')) return { x: px + 120, y: py + 188 };
      if (pid.startsWith('bot_-')) return { x: px + 120, y: py + 205 };

      // Row matching e.g. 10a, 15e, 10f
      const match = pid.match(/(\d+)\s*([a-j])/);
      if (match) {
        const row = parseInt(match[1], 10);
        const col = match[2];
        const hx = px + 45 + (row - 1) * 16.5;
        const leftCols = ['a', 'b', 'c', 'd', 'e'];
        const rightCols = ['f', 'g', 'h', 'i', 'j'];
        let hy = py + 80;
        if (leftCols.includes(col)) {
          hy = py + 65 + leftCols.indexOf(col) * 9.5;
        } else if (rightCols.includes(col)) {
          hy = py + 125 + rightCols.indexOf(col) * 9.5;
        }
        return { x: hx, y: hy };
      }
      return { x: px + 60, y: py + 60 };
    }

    // Microcontrollers
    if (part.type === 'arduino_uno') {
      const digPins = ['AREF', 'GND', '13', '12', '11', '10', '9', '8', '7', '6', '5', '4', '3', '2', '1', '0'];
      const dIdx = digPins.indexOf(pinId);
      if (dIdx !== -1) {
        return { x: px + 82 + dIdx * 11.5, y: py + 19 };
      }
      const pwrPins = ['IOREF', 'RESET', '3.3V', '5V', 'GND', 'GND', 'VIN'];
      const pIdx = pwrPins.indexOf(pinId);
      if (pIdx !== -1) {
        return { x: px + 78 + pIdx * 12, y: py + 189 };
      }
      const anaPins = ['A0', 'A1', 'A2', 'A3', 'A4', 'A5'];
      const aIdx = anaPins.indexOf(pinId);
      if (aIdx !== -1) {
        return { x: px + 190 + aIdx * 12.5, y: py + 189 };
      }
      return { x: px + 80, y: py + 20 };
    }

    if (part.type === 'esp32_devkit') {
      const leftPins = ['3V3', 'EN', 'VP', 'VN', 'G34', 'G35', 'G32', 'G33', 'G25', 'G26', 'G27', 'G14', 'G12', 'GND', 'G13'];
      const rightPins = ['G23', 'G22', 'TX0', 'RX0', 'G21', 'GND', 'G19', 'G18', 'G5', 'G17', 'G16', 'G4', 'G0', 'G2', 'G15'];
      const lIdx = leftPins.indexOf(pinId);
      if (lIdx !== -1) return { x: px + 14, y: py + 20 + lIdx * 15.5 };
      const rIdx = rightPins.indexOf(pinId);
      if (rIdx !== -1) return { x: px + 146, y: py + 20 + rIdx * 15.5 };
      return { x: px + 20, y: py + 20 };
    }

    // Discrete components
    if (part.type === 'led') {
      if (pinId === 'anode') return { x: px + 8, y: py + 45 };
      if (pinId === 'cathode') return { x: px + 22, y: py + 42 };
    }
    if (part.type === 'resistor') {
      if (pinId === 'pin1') return { x: px - 15, y: py + 5 };
      if (pinId === 'pin2') return { x: px + 65, y: py + 5 };
    }
    if (part.type === 'button') {
      if (pinId === 'pin1a') return { x: px + 0, y: py + 6 };
      if (pinId === 'pin1b') return { x: px + 40, y: py + 6 };
      if (pinId === 'pin2a') return { x: px + 0, y: py + 34 };
      if (pinId === 'pin2b') return { x: px + 40, y: py + 34 };
    }
    if (part.type === 'potentiometer') {
      if (pinId === 'pin1') return { x: px + 8, y: py + 55 };
      if (pinId === 'wiper') return { x: px + 25, y: py + 55 };
      if (pinId === 'pin2') return { x: px + 42, y: py + 55 };
    }
    if (part.type === 'buzzer') {
      if (pinId === 'positive') return { x: px + 14, y: py + 52 };
      if (pinId === 'negative') return { x: px + 36, y: py + 52 };
    }
    if (part.type === 'servo') {
      if (pinId === 'gnd') return { x: px + 52, y: py + 48 };
      if (pinId === 'vcc') return { x: px + 60, y: py + 48 };
      if (pinId === 'signal') return { x: px + 68, y: py + 48 };
    }

    return { x: px + 20, y: py + 20 };
  };

  // Wire click: start drawing or complete drawing
  const handlePinClick = (partId: string, pinId: string, clientX: number, clientY: number) => {
    if (isSimulating) return; // Read-only during live simulation

    if (!drawingWire) {
      // Start drawing new wire
      const coords = getPinAbsoluteCoords(partId, pinId);
      setDrawingWire({
        source: { part_id: partId, pin_id: pinId },
        startX: coords.x,
        startY: coords.y,
        currentX: coords.x,
        currentY: coords.y,
      });
    } else {
      // Finish drawing wire
      if (drawingWire.source.part_id === partId && drawingWire.source.pin_id === pinId) {
        // Clicked same pin: cancel
        setDrawingWire(null);
        return;
      }

      const newWire: CircuitWire = {
        id: `w_${Date.now()}`,
        source: drawingWire.source,
        target: { part_id: partId, pin_id: pinId },
        color: activeWireColor,
        style: 'solid',
        confidence: 'confirmed',
      };

      onCircuitChange({
        ...circuit,
        wires: [...circuit.wires, newWire],
      });
      setDrawingWire(null);
    }
  };

  // Mouse move on canvas (pan or update drawing wire)
  const handleMouseMove = (e: React.MouseEvent) => {
    if (isPanning) {
      setPan({
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y,
      });
      return;
    }

    if (drawingWire) {
      const { x, y } = getCanvasCoords(e.clientX, e.clientY);
      setDrawingWire((prev) => (prev ? { ...prev, currentX: x, currentY: y } : null));
      return;
    }

    if (draggingPartId && !isSimulating) {
      const { x, y } = getCanvasCoords(e.clientX, e.clientY);
      // 5px grid snapping
      const snapX = Math.round((x - dragOffset.x) / 5) * 5;
      const snapY = Math.round((y - dragOffset.y) / 5) * 5;

      const updatedParts = circuit.parts.map((p) =>
        p.id === draggingPartId ? { ...p, x: snapX, y: snapY } : p
      );
      onCircuitChange({ ...circuit, parts: updatedParts });
    }
  };

  // Mouse up
  const handleMouseUp = () => {
    setIsPanning(false);
    setDraggingPartId(null);
  };

  // Zoom with mouse wheel
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.1 : 0.9;
    setZoom((z) => Math.max(0.3, Math.min(2.5, z * factor)));
  };

  // Keyboard shortcut: Delete wire or rotate component
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedWireId && !isSimulating) {
          onCircuitChange({
            ...circuit,
            wires: circuit.wires.filter((w) => w.id !== selectedWireId),
          });
          onSelectWire(null);
        } else if (selectedPartId && !isSimulating) {
          const part = circuit.parts.find((p) => p.id === selectedPartId);
          // Don't delete main MCU or primary breadboard
          if (part && !part.type.startsWith('breadboard') && !['arduino_uno', 'esp32_devkit', 'stm32_bluepill'].includes(part.type)) {
            onCircuitChange({
              ...circuit,
              parts: circuit.parts.filter((p) => p.id !== selectedPartId),
              wires: circuit.wires.filter(
                (w) => w.source.part_id !== selectedPartId && w.target.part_id !== selectedPartId
              ),
            });
            onSelectPart(null);
          }
        }
      } else if (e.key === 'r' || e.key === 'R') {
        if (selectedPartId && !isSimulating) {
          const updatedParts = circuit.parts.map((p) =>
            p.id === selectedPartId ? { ...p, rotation: (p.rotation + 90) % 360 } : p
          );
          onCircuitChange({ ...circuit, parts: updatedParts });
        }
      } else if (e.key === 'Escape') {
        setDrawingWire(null);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedWireId, selectedPartId, circuit, isSimulating]);

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        backgroundColor: '#f5ede3',
        backgroundImage: 'radial-gradient(#dfd3c2 1.5px, transparent 1.5px)',
        backgroundSize: '20px 20px',
      }}
    >
      <svg
        ref={containerRef}
        style={{ width: '100%', height: '100%', cursor: isPanning ? 'grabbing' : 'default' }}
        onMouseDown={(e) => {
          if (e.button === 1 || e.target === containerRef.current) {
            setIsPanning(true);
            setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
            onSelectPart(null);
            onSelectWire(null);
          }
        }}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onWheel={handleWheel}
      >
        <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
          {/* 1. RENDER BOARDS & BREADBOARD */}
          {circuit.parts.map((part) => {
            const isSelected = selectedPartId === part.id;

            return (
              <g
                key={part.id}
                onMouseDown={(e) => {
                  e.stopPropagation();
                  onSelectPart(part.id);
                  onSelectWire(null);
                  if (!isSimulating) {
                    setDraggingPartId(part.id);
                    const coords = getCanvasCoords(e.clientX, e.clientY);
                    setDragOffset({ x: coords.x - part.x, y: coords.y - part.y });
                  }
                }}
              >
                {part.type.startsWith('breadboard') ? (
                  <BreadboardSVG part={part} selected={isSelected} onPinClick={handlePinClick} />
                ) : ['arduino_uno', 'esp32_devkit', 'stm32_bluepill'].includes(part.type) ? (
                  <BoardSVG
                    part={part}
                    selected={isSelected}
                    onPinClick={handlePinClick}
                    pinStates={pinStates}
                  />
                ) : (
                  <DiscreteComponentSVG
                    part={part}
                    selected={isSelected}
                    onPinClick={handlePinClick}
                    componentState={componentStates[part.id]}
                    onPropertyChange={(pId, props) => {
                      const updated = circuit.parts.map((p) =>
                        p.id === pId ? { ...p, properties: { ...p.properties, ...props } } : p
                      );
                      onCircuitChange({ ...circuit, parts: updated });
                    }}
                  />
                )}
              </g>
            );
          })}

          {/* 2. RENDER ELECTRICAL WIRES */}
          {circuit.wires.map((wire) => {
            const p1 = getPinAbsoluteCoords(wire.source.part_id, wire.source.pin_id);
            const p2 = getPinAbsoluteCoords(wire.target.part_id, wire.target.pin_id);

            const isSelected = selectedWireId === wire.id;
            const isDashed = wire.style === 'dashed';

            // Natural organic jumper wire curve
            const dx = p2.x - p1.x;
            const dy = p2.y - p1.y;
            const dist = Math.hypot(dx, dy);
            const sag = Math.min(80, Math.max(25, dist * 0.25));

            const pathD = `M ${p1.x} ${p1.y} C ${p1.x + dx * 0.25} ${p1.y + dy * 0.1 + sag}, ${p2.x - dx * 0.25} ${p2.y - dy * 0.1 + sag}, ${p2.x} ${p2.y}`;

            return (
              <g key={wire.id} style={{ cursor: 'pointer' }}>
                {/* Selection halo */}
                {isSelected && (
                  <path
                    d={pathD}
                    fill="none"
                    stroke="#781d32"
                    strokeWidth={8}
                    strokeLinecap="round"
                    opacity={0.65}
                  />
                )}
                {/* Wire Body */}
                <path
                  d={pathD}
                  fill="none"
                  stroke={wire.color || '#2e7d32'}
                  strokeWidth={3.8}
                  strokeLinecap="round"
                  strokeDasharray={isDashed ? '6 4' : 'none'}
                  filter="drop-shadow(0 2px 4px rgba(0,0,0,0.18))"
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectWire(wire.id);
                    onSelectPart(null);
                  }}
                />
                {/* End terminals */}
                <circle cx={p1.x} cy={p1.y} r={3.5} fill={wire.color} stroke="#2b2523" strokeWidth={1} />
                <circle cx={p2.x} cy={p2.y} r={3.5} fill={wire.color} stroke="#2b2523" strokeWidth={1} />
              </g>
            );
          })}

          {/* 3. RENDER CURRENTLY DRAWING WIRE */}
          {drawingWire && (
            <g>
              <line
                x1={drawingWire.startX}
                y1={drawingWire.startY}
                x2={drawingWire.currentX}
                y2={drawingWire.currentY}
                stroke={activeWireColor}
                strokeWidth={3}
                strokeDasharray="4 4"
                strokeLinecap="round"
              />
              <circle cx={drawingWire.startX} cy={drawingWire.startY} r={4.5} fill={activeWireColor} />
              <circle cx={drawingWire.currentX} cy={drawingWire.currentY} r={4.5} fill="#ffffff" />
            </g>
          )}
        </g>
      </svg>
    </div>
  );
};

