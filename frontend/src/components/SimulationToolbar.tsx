import React from 'react';
import { Play, Pause, Square, SkipForward, RotateCcw, Clock, Activity, AlertCircle } from 'lucide-react';

interface ToolbarProps {
  isSimulating: boolean;
  isPaused: boolean;
  currentTimeMs: number;
  totalDurationMs: number;
  playbackSpeed: number;
  onTogglePlay: () => void;
  onStop: () => void;
  onStepForward: () => void;
  onResetCircuit: () => void;
  onChangeSpeed: (speed: number) => void;
  activeWireColor: string;
  onChangeWireColor: (color: string) => void;
  notes?: string[];
}

export const SimulationToolbar: React.FC<ToolbarProps> = ({
  isSimulating,
  isPaused,
  currentTimeMs,
  totalDurationMs,
  playbackSpeed,
  onTogglePlay,
  onStop,
  onStepForward,
  onResetCircuit,
  onChangeSpeed,
  activeWireColor,
  onChangeWireColor,
}) => {
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
        height: 52,
        backgroundColor: '#f7f1e7',
        borderBottom: '1px solid #dfd3c2',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 16px',
        gap: 12,
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
      }}
    >
      {/* Simulation Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {/* Play/Pause */}
        <button
          onClick={onTogglePlay}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '6px 14px',
            backgroundColor: isSimulating && !isPaused ? '#b45309' : '#781d32',
            color: '#ffffff',
            border: 'none',
            borderRadius: 6,
            fontSize: 12,
            fontWeight: 700,
            letterSpacing: '0.4px',
            cursor: 'pointer',
            boxShadow: '0 1px 2px rgba(0,0,0,0.1)',
          }}
        >
          {isSimulating && !isPaused ? <Pause size={13} /> : <Play size={13} />}
          {isSimulating && !isPaused ? 'PAUSE' : isPaused ? 'RESUME' : 'START SIMULATION'}
        </button>

        {/* Stop */}
        <button
          onClick={onStop}
          disabled={!isSimulating && !isPaused}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            padding: '6px 10px',
            backgroundColor: '#ede2d3',
            color: !isSimulating && !isPaused ? '#9c8e85' : '#9e2a2b',
            border: '1px solid #d8c6b0',
            borderRadius: 6,
            fontSize: 12,
            fontWeight: 600,
            cursor: !isSimulating && !isPaused ? 'not-allowed' : 'pointer',
          }}
        >
          <Square size={12} /> STOP
        </button>

        {/* Step Forward */}
        <button
          onClick={onStepForward}
          disabled={isSimulating && !isPaused}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            padding: '6px 10px',
            backgroundColor: '#ede2d3',
            color: isSimulating && !isPaused ? '#9c8e85' : '#2b2523',
            border: '1px solid #d8c6b0',
            borderRadius: 6,
            fontSize: 12,
            cursor: isSimulating && !isPaused ? 'not-allowed' : 'pointer',
          }}
          title="Step Forward (100ms)"
        >
          <SkipForward size={12} /> STEP
        </button>

        {/* Reset Circuit */}
        <button
          onClick={onResetCircuit}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            padding: '6px 10px',
            backgroundColor: '#ede2d3',
            color: '#5e524d',
            border: '1px solid #d8c6b0',
            borderRadius: 6,
            fontSize: 12,
            cursor: 'pointer',
          }}
          title="Reset Workspace"
        >
          <RotateCcw size={12} /> RESET
        </button>

        {/* Speed Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginLeft: 8 }}>
          {[0.5, 1, 2].map((s) => (
            <button
              key={s}
              onClick={() => onChangeSpeed(s)}
              style={{
                padding: '4px 8px',
                fontSize: 10,
                fontWeight: 700,
                borderRadius: 4,
                border: '1px solid',
                borderColor: playbackSpeed === s ? '#781d32' : '#d8c6b0',
                cursor: 'pointer',
                backgroundColor: playbackSpeed === s ? '#781d32' : '#ede2d3',
                color: playbackSpeed === s ? '#ffffff' : '#5e524d',
              }}
            >
              {s}x
            </button>
          ))}
        </div>
      </div>

      {/* Time & State Indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '4px 10px',
            borderRadius: 4,
            backgroundColor: '#ede2d3',
            fontSize: 11,
            fontFamily: 'monospace',
            color: '#781d32',
            fontWeight: 600,
            border: '1px solid #d8c6b0',
          }}
        >
          <Clock size={12} /> {currentTimeMs} ms / {totalDurationMs} ms
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            fontSize: 10,
            fontWeight: 700,
            padding: '4px 8px',
            borderRadius: 4,
            textTransform: 'uppercase',
            letterSpacing: '0.4px',
            backgroundColor:
              isSimulating && !isPaused
                ? 'rgba(46, 125, 50, 0.12)'
                : isPaused
                ? 'rgba(180, 83, 9, 0.12)'
                : 'rgba(100, 90, 85, 0.12)',
            color:
              isSimulating && !isPaused
                ? '#2e7d32'
                : isPaused
                ? '#b45309'
                : '#5e524d',
            border: '1px solid',
            borderColor:
              isSimulating && !isPaused
                ? '#2e7d32'
                : isPaused
                ? '#b45309'
                : '#c8b6a0',
          }}
        >
          {isSimulating && !isPaused ? (
            <>
              <Activity size={11} /> RUNNING
            </>
          ) : isPaused ? (
            <>
              <Pause size={11} /> PAUSED
            </>
          ) : (
            <>
              <Square size={11} /> STOPPED
            </>
          )}
        </div>
      </div>

      {/* Wire Tool & Color Selection */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: '#5e524d' }}>Wire:</span>
        <div style={{ display: 'flex', gap: 5 }}>
          {wireColors.map((wc) => (
            <button
              key={wc.hex}
              onClick={() => onChangeWireColor(wc.hex)}
              style={{
                width: 20,
                height: 20,
                borderRadius: '50%',
                backgroundColor: wc.hex,
                border: activeWireColor === wc.hex ? '2.5px solid #781d32' : '1px solid #c8b6a0',
                cursor: 'pointer',
                boxShadow: activeWireColor === wc.hex ? '0 0 0 1px #781d32' : 'none',
              }}
              title={wc.name}
            />
          ))}
        </div>
      </div>
    </div>
  );
};
