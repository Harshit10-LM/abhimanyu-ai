import React, { useState, useEffect, useRef } from 'react';
import { Streamlit } from 'streamlit-component-lib';
import { CircuitDocument, CircuitPart, CircuitWire, SimulationFrame } from './types';
import { CircuitCanvas } from './components/CircuitCanvas';
import { ComponentLibrary } from './components/ComponentLibrary';
import { ComponentInspector } from './components/ComponentInspector';
import { SimulationToolbar } from './components/SimulationToolbar';
import { SimulationTimeline } from './components/SimulationTimeline';

// Default initial circuit if none provided
const DEFAULT_CIRCUIT: CircuitDocument = {
  board: 'arduino_uno',
  parts: [
    { id: 'mcu1', type: 'arduino_uno', x: 80, y: 120, rotation: 0, properties: { label: 'Arduino Uno' } },
    { id: 'bb1', type: 'breadboard_half', x: 450, y: 100, rotation: 0, properties: { label: 'Half Breadboard' } },
    { id: 'led1', type: 'led', x: 560, y: 180, rotation: 0, properties: { color: 'red', label: 'Red LED' } },
    { id: 'r1', type: 'resistor', x: 560, y: 260, rotation: 90, properties: { resistance: 220, unit: 'Ω' } },
  ],
  wires: [
    { id: 'w1', source: { part_id: 'mcu1', pin_id: '13' }, target: { part_id: 'bb1', pin_id: '10a' }, color: '#22c55e', style: 'solid', confidence: 'confirmed' },
    { id: 'w2', source: { part_id: 'led1', pin_id: 'anode' }, target: { part_id: 'bb1', pin_id: '10e' }, color: '#22c55e', style: 'solid', confidence: 'confirmed' },
    { id: 'w3', source: { part_id: 'led1', pin_id: 'cathode' }, target: { part_id: 'bb1', pin_id: '11e' }, color: '#3b82f6', style: 'solid', confidence: 'confirmed' },
    { id: 'w4', source: { part_id: 'r1', pin_id: 'pin1' }, target: { part_id: 'bb1', pin_id: '11a' }, color: '#3b82f6', style: 'solid', confidence: 'confirmed' },
    { id: 'w5', source: { part_id: 'r1', pin_id: 'pin2' }, target: { part_id: 'bb1', pin_id: 'bot_neg' }, color: '#111827', style: 'solid', confidence: 'confirmed' },
    { id: 'w6', source: { part_id: 'mcu1', pin_id: 'GND' }, target: { part_id: 'bb1', pin_id: 'bot_neg' }, color: '#111827', style: 'solid', confidence: 'confirmed' },
  ],
  suggested: true,
  notes: ['Default Arduino Uno + Blinking LED Circuit Workspace'],
};

export const App: React.FC = () => {
  const [circuit, setCircuit] = useState<CircuitDocument>(DEFAULT_CIRCUIT);
  const [frames, setFrames] = useState<SimulationFrame[]>([]);
  const [currentFrameIdx, setCurrentFrameIdx] = useState<number>(0);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [isPaused, setIsPaused] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1.0);

  const [selectedPartId, setSelectedPartId] = useState<string | null>(null);
  const [selectedWireId, setSelectedWireId] = useState<string | null>(null);
  const [activeWireColor, setActiveWireColor] = useState<string>('#22c55e');

  const timerRef = useRef<any>(null);

  // 1. Listen for Streamlit RENDER_EVENT
  useEffect(() => {
    const onRender = (event: Event) => {
      const customEvent = event as CustomEvent;
      const args = customEvent.detail?.args;

      if (args) {
        if (args.circuit) {
          setCircuit(args.circuit);
        }
        if (args.simulation_frames && args.simulation_frames.length > 0) {
          setFrames(args.simulation_frames);
        }
        if (args.is_running !== undefined) {
          setIsSimulating(args.is_running);
        }
        if (args.current_frame_idx !== undefined) {
          setCurrentFrameIdx(args.current_frame_idx);
        }
      }

      // Tell Streamlit our desired height
      Streamlit.setFrameHeight(700);
    };

    Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender);
    Streamlit.setComponentReady();
    Streamlit.setFrameHeight(700);

    return () => {
      Streamlit.events.removeEventListener(Streamlit.RENDER_EVENT, onRender);
    };
  }, []);

  // 2. Playback Timer
  useEffect(() => {
    if (isSimulating && !isPaused && frames.length > 0) {
      const intervalMs = Math.max(30, 100 / playbackSpeed);
      timerRef.current = setInterval(() => {
        setCurrentFrameIdx((prev) => {
          if (prev >= frames.length - 1) {
            return 0; // Loop back
          }
          return prev + 1;
        });
      }, intervalMs);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isSimulating, isPaused, frames, playbackSpeed]);

  // Sync circuit change to Streamlit
  const handleCircuitChange = (newCircuit: CircuitDocument) => {
    setCircuit(newCircuit);
    try {
      Streamlit.setComponentValue({
        action: 'circuit_updated',
        circuit: newCircuit,
      });
    } catch (e) {
      // Standalone mode outside iframe
    }
  };

  // Add component
  const handleAddComponent = (type: string, defaultProps?: Record<string, any>) => {
    const id = `${type}_${Date.now().toString().slice(-4)}`;
    const newPart: CircuitPart = {
      id,
      type,
      x: 520,
      y: 160,
      rotation: 0,
      properties: defaultProps || {},
    };

    handleCircuitChange({
      ...circuit,
      parts: [...circuit.parts, newPart],
    });
    setSelectedPartId(id);
  };

  // Delete component
  const handleDeletePart = (partId: string) => {
    handleCircuitChange({
      ...circuit,
      parts: circuit.parts.filter((p) => p.id !== partId),
      wires: circuit.wires.filter(
        (w) => w.source.part_id !== partId && w.target.part_id !== partId
      ),
    });
    setSelectedPartId(null);
  };

  // Rotate component
  const handleRotatePart = (partId: string) => {
    handleCircuitChange({
      ...circuit,
      parts: circuit.parts.map((p) =>
        p.id === partId ? { ...p, rotation: (p.rotation + 90) % 360 } : p
      ),
    });
  };

  // Update properties
  const handleUpdatePartProps = (partId: string, props: Record<string, any>) => {
    handleCircuitChange({
      ...circuit,
      parts: circuit.parts.map((p) =>
        p.id === partId ? { ...p, properties: { ...p.properties, ...props } } : p
      ),
    });
  };

  // Delete wire
  const handleDeleteWire = (wireId: string) => {
    handleCircuitChange({
      ...circuit,
      wires: circuit.wires.filter((w) => w.id !== wireId),
    });
    setSelectedWireId(null);
  };

  // Update wire color
  const handleUpdateWireColor = (wireId: string, color: string) => {
    handleCircuitChange({
      ...circuit,
      wires: circuit.wires.map((w) => (w.id === wireId ? { ...w, color } : w)),
    });
  };

  // Reset circuit
  const handleResetCircuit = () => {
    const blankCircuit: CircuitDocument = {
      board: circuit.board,
      parts: [
        { id: 'mcu1', type: circuit.board, x: 80, y: 120, rotation: 0, properties: {} },
        { id: 'bb1', type: 'breadboard_half', x: 450, y: 100, rotation: 0, properties: {} },
      ],
      wires: [],
      suggested: false,
      notes: ['Workspace reset.'],
    };
    handleCircuitChange(blankCircuit);
    setSelectedPartId(null);
    setSelectedWireId(null);
    setIsSimulating(false);
  };

  const currentFrame = frames[currentFrameIdx] || null;
  const pinStates = currentFrame?.pin_states || {};
  const componentStates = currentFrame?.component_states || {};

  const selectedPart = circuit.parts.find((p) => p.id === selectedPartId) || null;
  const selectedWire = circuit.wires.find((w) => w.id === selectedWireId) || null;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        height: '100vh',
        backgroundColor: '#fbf8f3',
        color: '#2b2523',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      }}
    >
      {/* 1. TOP TOOLBAR */}
      <SimulationToolbar
        isSimulating={isSimulating}
        isPaused={isPaused}
        currentTimeMs={currentFrame?.t_ms || 0}
        totalDurationMs={frames.length > 0 ? frames[frames.length - 1].t_ms : 0}
        playbackSpeed={playbackSpeed}
        onTogglePlay={() => {
          if (!isSimulating) {
            setIsSimulating(true);
            setIsPaused(false);
          } else {
            setIsPaused(!isPaused);
          }
        }}
        onStop={() => {
          setIsSimulating(false);
          setIsPaused(false);
          setCurrentFrameIdx(0);
        }}
        onStepForward={() => {
          if (frames.length > 0) {
            setCurrentFrameIdx((prev) => Math.min(frames.length - 1, prev + 1));
          }
        }}
        onResetCircuit={handleResetCircuit}
        onChangeSpeed={setPlaybackSpeed}
        activeWireColor={activeWireColor}
        onChangeWireColor={setActiveWireColor}
      />

      {/* 2. MAIN WORKSPACE */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Left: Collapsible Component Library */}
        <ComponentLibrary onAddComponent={handleAddComponent} disabled={isSimulating} />

        {/* Center: Circuit Canvas with Floating Inspector */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          <CircuitCanvas
            circuit={circuit}
            onCircuitChange={handleCircuitChange}
            selectedPartId={selectedPartId}
            onSelectPart={setSelectedPartId}
            selectedWireId={selectedWireId}
            onSelectWire={setSelectedWireId}
            activeWireColor={activeWireColor}
            pinStates={pinStates}
            componentStates={componentStates}
            isSimulating={isSimulating}
          />

          {/* Floating Compact Selected Component Inspector */}
          <ComponentInspector
            selectedPart={selectedPart}
            selectedWire={selectedWire}
            circuit={circuit}
            onUpdatePartProps={handleUpdatePartProps}
            onRotatePart={handleRotatePart}
            onDeletePart={handleDeletePart}
            onUpdateWireColor={handleUpdateWireColor}
            onDeleteWire={handleDeleteWire}
            onClose={() => {
              setSelectedPartId(null);
              setSelectedWireId(null);
            }}
            componentState={selectedPart ? componentStates[selectedPart.id] : undefined}
            disabled={isSimulating}
          />
        </div>
      </div>

      {/* 3. BOTTOM TIMELINE & CONSOLE */}
      <SimulationTimeline
        frames={frames}
        currentFrameIdx={currentFrameIdx}
        onSelectFrame={setCurrentFrameIdx}
      />
    </div>
  );
};

