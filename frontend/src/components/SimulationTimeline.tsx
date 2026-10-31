import React from 'react';
import { SimulationFrame } from '../types';
import { Clock, Activity } from 'lucide-react';

interface TimelineProps {
  frames: SimulationFrame[];
  currentFrameIdx: number;
  onSelectFrame: (frameIdx: number) => void;
}

export const SimulationTimeline: React.FC<TimelineProps> = ({
  frames,
  currentFrameIdx,
  onSelectFrame,
}) => {
  if (!frames || frames.length === 0) {
    return (
      <div
        style={{
          height: 100,
          backgroundColor: '#fbf8f3',
          borderTop: '1px solid #dfd3c2',
          padding: '12px 16px',
          color: '#8a7d75',
          fontSize: 12,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontWeight: 500,
        }}
      >
        No simulation events loaded. Submit verified firmware to generate deterministic timeline frames.
      </div>
    );
  }

  const currentFrame = frames[currentFrameIdx] || frames[0];

  return (
    <div
      style={{
        height: 125,
        backgroundColor: '#fbf8f3',
        borderTop: '1px solid #dfd3c2',
        display: 'flex',
        flexDirection: 'column',
        padding: '8px 16px',
        gap: 6,
      }}
    >
      {/* Top Header: Scrubber and Active Event */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 11, fontWeight: 800, color: '#781d32', letterSpacing: '0.4px', textTransform: 'uppercase' }}>
            Simulation Timeline
          </span>
          <span style={{ fontSize: 11, color: '#5e524d', fontFamily: 'monospace', fontWeight: 600 }}>
            t = {currentFrame.t_ms} ms
          </span>
        </div>
        <div style={{ fontSize: 11, color: '#2b2523', fontFamily: 'monospace', fontWeight: 600 }}>
          {currentFrame.active_event_description || 'Idle / Steady State'}
        </div>
      </div>

      {/* Scrub Slider */}
      <input
        type="range"
        min={0}
        max={frames.length - 1}
        value={currentFrameIdx}
        onChange={(e) => onSelectFrame(parseInt(e.target.value, 10))}
        style={{ width: '100%', cursor: 'pointer', accentColor: '#781d32' }}
      />

      {/* Bottom split: Clickable Event Pills & Live GPIO Monitor */}
      <div style={{ display: 'flex', gap: 12, flex: 1, overflow: 'hidden' }}>
        {/* Event Pills */}
        <div
          style={{
            flex: 2,
            display: 'flex',
            gap: 6,
            overflowX: 'auto',
            alignItems: 'center',
            paddingBottom: 4,
          }}
        >
          {frames
            .filter((f, idx) => f.active_event_description && idx % 3 === 0)
            .map((f, idx) => {
              const frameRealIdx = frames.indexOf(f);
              const isSelected = currentFrameIdx === frameRealIdx;
              return (
                <button
                  key={`evt_${f.t_ms}_${idx}`}
                  onClick={() => onSelectFrame(frameRealIdx)}
                  style={{
                    padding: '4px 8px',
                    borderRadius: 4,
                    border: '1px solid',
                    borderColor: isSelected ? '#781d32' : '#dfd3c2',
                    backgroundColor: isSelected ? '#781d32' : '#ffffff',
                    color: isSelected ? '#ffffff' : '#5e524d',
                    fontSize: 10,
                    fontFamily: 'monospace',
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
                  }}
                >
                  {f.t_ms}ms: {f.active_event_description?.slice(0, 24)}...
                </button>
              );
            })}
        </div>

        {/* Live Pin States Mini Monitor */}
        <div
          style={{
            flex: 1,
            backgroundColor: '#ffffff',
            border: '1px solid #dfd3c2',
            borderRadius: 5,
            padding: '4px 8px',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            overflowX: 'auto',
          }}
        >
          <span style={{ fontSize: 10, fontWeight: 700, color: '#8a7d75', textTransform: 'uppercase' }}>
            Pins:
          </span>
          {Object.entries(currentFrame.pin_states || {}).map(([pName, pSnap]) => (
            <div
              key={pName}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 3,
                fontSize: 10,
                fontFamily: 'monospace',
                padding: '2px 5px',
                borderRadius: 3,
                backgroundColor: pSnap.digital_state === 'HIGH' ? 'rgba(46, 125, 50, 0.12)' : '#f5efe6',
                border: '1px solid',
                borderColor: pSnap.digital_state === 'HIGH' ? '#2e7d32' : '#dfd3c2',
                color: pSnap.digital_state === 'HIGH' ? '#2e7d32' : '#5e524d',
                fontWeight: 600,
              }}
            >
              <span>{pName}:</span>
              <span>{pSnap.digital_state}</span>
              {pSnap.pwm_duty !== null && pSnap.pwm_duty !== undefined && pSnap.pwm_duty > 0 && (
                <span style={{ color: '#b45309' }}>({pSnap.pwm_duty})</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
