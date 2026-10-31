import React from 'react';
import { Trash2, RotateCw, X, AlertTriangle } from 'lucide-react';
import { CircuitDocument, CircuitPart, CircuitWire } from '../types';

interface InspectorProps {
  selectedPart: CircuitPart | null;
  selectedWire: CircuitWire | null;
  circuit: CircuitDocument;
  onUpdatePartProps: (partId: string, newProps: Record<string, any>) => void;
  onRotatePart: (partId: string) => void;
  onDeletePart: (partId: string) => void;
  onUpdateWireColor: (wireId: string, color: string) => void;
  onDeleteWire: (wireId: string) => void;
  onClose?: () => void;
  componentState?: any;
  disabled?: boolean;
}

export const ComponentInspector: React.FC<InspectorProps> = ({
  selectedPart,
  selectedWire,
  onUpdatePartProps,
  onRotatePart,
  onDeletePart,
  onUpdateWireColor,
  onDeleteWire,
  onClose,
  componentState,
  disabled = false,
}) => {
  // If nothing is selected, take 0 space!
  if (!selectedPart && !selectedWire) {
    return null;
  }

  // --- WIRE INSPECTION (Compact Floating Card) ---
  if (selectedWire) {
    const wireColors = [
      { name: 'Signal (Green)', hex: '#2e7d32' },
      { name: 'Ground (Black)', hex: '#212121' },
      { name: 'Supply (Red)', hex: '#c62828' },
      { name: 'Control (Amber)', hex: '#d97706' },
      { name: 'Analog (Navy)', hex: '#1565c0' },
    ];

    return (
      <div
        style={{
          position: 'absolute',
          top: 10,
          right: 10,
          width: 190,
          backgroundColor: '#fbf8f3',
          border: '1px solid #d8c6b0',
          borderRadius: 8,
          padding: '10px 12px',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
          zIndex: 20,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 11, fontWeight: 800, color: '#781d32', letterSpacing: '0.4px' }}>
            WIRE {selectedWire.id}
          </span>
          {onClose && (
            <button
              onClick={onClose}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: '#8a7d75',
                padding: 2,
                display: 'flex',
                alignItems: 'center',
              }}
              title="Close Inspector"
            >
              <X size={13} />
            </button>
          )}
        </div>

        <div style={{ fontSize: 10, color: '#5e524d', fontFamily: 'monospace', backgroundColor: '#ffffff', border: '1px solid #e5dac9', padding: '6px 8px', borderRadius: 4 }}>
          <div>FROM: <strong style={{ color: '#781d32' }}>{selectedWire.source.part_id}:{selectedWire.source.pin_id}</strong></div>
          <div style={{ marginTop: 2 }}>TO: <strong style={{ color: '#781d32' }}>{selectedWire.target.part_id}:{selectedWire.target.pin_id}</strong></div>
        </div>

        {/* Wire Color Picker */}
        <div>
          <div style={{ fontSize: 9, fontWeight: 700, color: '#8a7d75', textTransform: 'uppercase', marginBottom: 4 }}>
            Color
          </div>
          <div style={{ display: 'flex', gap: 5 }}>
            {wireColors.map((c) => (
              <button
                key={c.hex}
                disabled={disabled}
                onClick={() => onUpdateWireColor(selectedWire.id, c.hex)}
                style={{
                  width: 20,
                  height: 20,
                  borderRadius: '50%',
                  backgroundColor: c.hex,
                  border: selectedWire.color === c.hex ? '2.5px solid #781d32' : '1px solid #d8c6b0',
                  cursor: disabled ? 'not-allowed' : 'pointer',
                }}
                title={c.name}
              />
            ))}
          </div>
        </div>

        {/* Delete Wire */}
        <button
          disabled={disabled}
          onClick={() => onDeleteWire(selectedWire.id)}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 4,
            padding: '5px 8px',
            backgroundColor: '#fae8e8',
            color: '#9e2a2b',
            border: '1px solid #f0b8b8',
            borderRadius: 5,
            fontSize: 10,
            fontWeight: 700,
            cursor: disabled ? 'not-allowed' : 'pointer',
          }}
        >
          <Trash2 size={11} /> Delete Wire
        </button>
      </div>
    );
  }

  // --- PART INSPECTION (Compact Floating Card) ---
  const part = selectedPart!;
  const isProtected = ['arduino_uno', 'esp32_devkit', 'stm32_bluepill', 'breadboard_half', 'breadboard_full'].includes(part.type);

  return (
    <div
      style={{
        position: 'absolute',
        top: 10,
        right: 10,
        width: 195,
        backgroundColor: '#fbf8f3',
        border: '1px solid #d8c6b0',
        borderRadius: 8,
        padding: '10px 12px',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
        zIndex: 20,
      }}
    >
      {/* Title & Controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span style={{ fontSize: 11, fontWeight: 800, color: '#781d32', textTransform: 'uppercase' }}>
            {part.type.replace('_', ' ')}
          </span>
          <span style={{ fontSize: 9, color: '#8a7d75', marginLeft: 4, fontFamily: 'monospace' }}>
            ({part.id})
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <button
            disabled={disabled}
            onClick={() => onRotatePart(part.id)}
            style={{
              padding: '2px 5px',
              backgroundColor: '#ede2d3',
              border: '1px solid #d8c6b0',
              borderRadius: 4,
              color: '#2b2523',
              fontSize: 10,
              cursor: disabled ? 'not-allowed' : 'pointer',
            }}
            title="Rotate (R)"
          >
            <RotateCw size={11} />
          </button>
          {onClose && (
            <button
              onClick={onClose}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: '#8a7d75',
                padding: 2,
                display: 'flex',
                alignItems: 'center',
              }}
              title="Close"
            >
              <X size={13} />
            </button>
          )}
        </div>
      </div>

      {/* Live Physical State from Simulation */}
      {componentState && (
        <div style={{ backgroundColor: '#ffffff', padding: '6px 8px', borderRadius: 4, border: '1px solid #e5dac9', fontSize: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#5e524d' }}>Status:</span>
            <strong style={{ color: componentState.state === 'ON' || componentState.state === 'ACTIVE' ? '#2e7d32' : '#8a7d75' }}>
              {componentState.state}
            </strong>
          </div>
          {componentState.current_ma !== undefined && (
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}>
              <span style={{ color: '#5e524d' }}>Current:</span>
              <span style={{ color: '#b45309', fontFamily: 'monospace', fontWeight: 700 }}>
                {componentState.current_ma} mA
              </span>
            </div>
          )}
          {componentState.warnings && componentState.warnings.length > 0 && (
            <div style={{ marginTop: 4, color: '#9e2a2b', fontSize: 9, display: 'flex', gap: 3, backgroundColor: '#fae8e8', padding: '2px 4px', borderRadius: 3 }}>
              <AlertTriangle size={10} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>{componentState.warnings[0]}</span>
            </div>
          )}
        </div>
      )}

      {/* Component Specific Parameter Inputs */}
      {/* LED */}
      {part.type === 'led' && (
        <div>
          <label style={{ fontSize: 9, fontWeight: 700, color: '#8a7d75', display: 'block', marginBottom: 2 }}>
            Color
          </label>
          <select
            disabled={disabled}
            value={part.properties.color || 'red'}
            onChange={(e) => onUpdatePartProps(part.id, { color: e.target.value })}
            style={{
              width: '100%',
              padding: '3px 6px',
              backgroundColor: '#ffffff',
              border: '1px solid #d8c6b0',
              borderRadius: 4,
              color: '#2b2523',
              fontSize: 10,
              outline: 'none',
            }}
          >
            <option value="red">Red (2.0V)</option>
            <option value="green">Green (2.2V)</option>
            <option value="blue">Blue (3.2V)</option>
            <option value="yellow">Yellow (2.1V)</option>
            <option value="white">White (3.2V)</option>
          </select>
        </div>
      )}

      {/* Resistor */}
      {part.type === 'resistor' && (
        <div>
          <label style={{ fontSize: 9, fontWeight: 700, color: '#8a7d75', display: 'block', marginBottom: 2 }}>
            Resistance
          </label>
          <div style={{ display: 'flex', gap: 4 }}>
            <input
              type="number"
              disabled={disabled}
              value={part.properties.resistance || 220}
              onChange={(e) => onUpdatePartProps(part.id, { resistance: Number(e.target.value) })}
              style={{
                flex: 1,
                padding: '3px 6px',
                backgroundColor: '#ffffff',
                border: '1px solid #d8c6b0',
                borderRadius: 4,
                color: '#2b2523',
                fontSize: 10,
                outline: 'none',
              }}
            />
            <select
              disabled={disabled}
              value={part.properties.unit || 'Ω'}
              onChange={(e) => onUpdatePartProps(part.id, { unit: e.target.value })}
              style={{
                width: 48,
                padding: '3px 4px',
                backgroundColor: '#ffffff',
                border: '1px solid #d8c6b0',
                borderRadius: 4,
                color: '#2b2523',
                fontSize: 10,
                outline: 'none',
              }}
            >
              <option value="Ω">Ω</option>
              <option value="kΩ">kΩ</option>
            </select>
          </div>
        </div>
      )}

      {/* Button */}
      {part.type === 'button' && (
        <button
          onClick={() => onUpdatePartProps(part.id, { is_pressed: !part.properties.is_pressed })}
          style={{
            width: '100%',
            padding: '5px 8px',
            backgroundColor: part.properties.is_pressed ? '#781d32' : '#ede2d3',
            color: part.properties.is_pressed ? '#ffffff' : '#2b2523',
            border: '1px solid #d8c6b0',
            borderRadius: 5,
            fontSize: 10,
            fontWeight: 700,
            cursor: 'pointer',
          }}
        >
          {part.properties.is_pressed ? 'RELEASE BUTTON' : 'PRESS BUTTON'}
        </button>
      )}

      {/* Potentiometer */}
      {part.type === 'potentiometer' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#8a7d75', marginBottom: 2 }}>
            <span>Wiper</span>
            <span style={{ color: '#781d32', fontWeight: 700 }}>{Math.round((part.properties.ratio ?? 0.5) * 100)}%</span>
          </div>
          <input
            type="range"
            min="0"
            max="1"
            step="0.02"
            value={part.properties.ratio ?? 0.5}
            onChange={(e) => onUpdatePartProps(part.id, { ratio: parseFloat(e.target.value) })}
            style={{ width: '100%', cursor: 'pointer', accentColor: '#781d32' }}
          />
        </div>
      )}

      {/* Delete Component Button */}
      {!isProtected && (
        <button
          disabled={disabled}
          onClick={() => onDeletePart(part.id)}
          style={{
            marginTop: 2,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 4,
            padding: '4px 8px',
            backgroundColor: '#fae8e8',
            color: '#9e2a2b',
            border: '1px solid #f0b8b8',
            borderRadius: 5,
            fontSize: 10,
            fontWeight: 700,
            cursor: disabled ? 'not-allowed' : 'pointer',
          }}
        >
          <Trash2 size={10} /> Delete Part
        </button>
      )}
    </div>
  );
};
