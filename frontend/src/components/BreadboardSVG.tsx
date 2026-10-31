import React, { useState } from 'react';
import { CircuitPart } from '../types';

interface BreadboardSVGProps {
  part: CircuitPart;
  selected: boolean;
  onPinClick: (partId: string, pinId: string, clientX: number, clientY: number) => void;
}

export const BreadboardSVG: React.FC<BreadboardSVGProps> = ({
  part,
  selected,
  onPinClick,
}) => {
  const [hoveredPin, setHoveredPin] = useState<string | null>(null);

  const numRows = part.type === 'breadboard_full' ? 60 : 30;
  const colSpacing = 16.5;
  const width = 80 + numRows * colSpacing;
  const height = 230;

  const rowNumbers = Array.from({ length: numRows }, (_, i) => i + 1);
  const leftCols = ['a', 'b', 'c', 'd', 'e'];
  const rightCols = ['f', 'g', 'h', 'i', 'j'];

  return (
    <g transform={`translate(${part.x}, ${part.y}) rotate(${part.rotation})`}>
      {/* Plastic Breadboard Body */}
      <rect
        width={width}
        height={height}
        rx={10}
        fill="#fbf9f5"
        stroke={selected ? '#781d32' : '#d8c6b0'}
        strokeWidth={selected ? 3 : 1.5}
        filter="drop-shadow(0 4px 8px rgba(0,0,0,0.12))"
      />

      {/* Center Divider Trench */}
      <rect x={35} y={112} width={width - 70} height={6} fill="#94a3b8" rx={2} />

      {/* Top Power Rails Lines */}
      {/* Positive (Red) */}
      <line x1={40} y1={25} x2={width - 40} y2={25} stroke="#ef4444" strokeWidth={2} strokeLinecap="round" />
      <text x={26} y={28} fill="#ef4444" fontSize="12" fontWeight="bold" textAnchor="middle">+</text>
      {/* Negative (Blue) */}
      <line x1={40} y1={42} x2={width - 40} y2={42} stroke="#3b82f6" strokeWidth={2} strokeLinecap="round" />
      <text x={26} y={45} fill="#3b82f6" fontSize="12" fontWeight="bold" textAnchor="middle">-</text>

      {/* Bottom Power Rails Lines */}
      {/* Positive (Red) */}
      <line x1={40} y1={188} x2={width - 40} y2={188} stroke="#ef4444" strokeWidth={2} strokeLinecap="round" />
      <text x={26} y={191} fill="#ef4444" fontSize="12" fontWeight="bold" textAnchor="middle">+</text>
      {/* Negative (Blue) */}
      <line x1={40} y1={205} x2={width - 40} y2={205} stroke="#3b82f6" strokeWidth={2} strokeLinecap="round" />
      <text x={26} y={208} fill="#3b82f6" fontSize="12" fontWeight="bold" textAnchor="middle">-</text>

      {/* Breadboard Row Numbers Header */}
      {rowNumbers.map((r) => {
        if (r % 5 === 0 || r === 1) {
          const rx = 45 + (r - 1) * colSpacing;
          return (
            <text key={`num_${r}`} x={rx} y={56} fill="#64748b" fontSize="8" fontFamily="sans-serif" textAnchor="middle">
              {r}
            </text>
          );
        }
        return null;
      })}

      {/* Top Power Rail Holes */}
      {rowNumbers.map((r) => {
        const hx = 45 + (r - 1) * colSpacing;
        const posId = `top_+_${r}`;
        const negId = `top_-_${r}`;
        return (
          <g key={`top_rails_${r}`}>
            {/* Top Positive Hole */}
            <circle
              cx={hx}
              cy={25}
              r={3.2}
              fill={hoveredPin === posId ? '#ef4444' : '#1e293b'}
              stroke="#64748b"
              strokeWidth={0.8}
              style={{ cursor: 'pointer' }}
              onMouseEnter={() => setHoveredPin(posId)}
              onMouseLeave={() => setHoveredPin(null)}
              onClick={(e) => {
                e.stopPropagation();
                onPinClick(part.id, 'top_+', e.clientX, e.clientY);
              }}
            />
            {/* Top Negative Hole */}
            <circle
              cx={hx}
              cy={42}
              r={3.2}
              fill={hoveredPin === negId ? '#3b82f6' : '#1e293b'}
              stroke="#64748b"
              strokeWidth={0.8}
              style={{ cursor: 'pointer' }}
              onMouseEnter={() => setHoveredPin(negId)}
              onMouseLeave={() => setHoveredPin(null)}
              onClick={(e) => {
                e.stopPropagation();
                onPinClick(part.id, 'top_-', e.clientX, e.clientY);
              }}
            />
          </g>
        );
      })}

      {/* Bottom Power Rail Holes */}
      {rowNumbers.map((r) => {
        const hx = 45 + (r - 1) * colSpacing;
        const posId = `bot_+_${r}`;
        const negId = `bot_-_${r}`;
        return (
          <g key={`bot_rails_${r}`}>
            {/* Bottom Positive Hole */}
            <circle
              cx={hx}
              cy={188}
              r={3.2}
              fill={hoveredPin === posId ? '#ef4444' : '#1e293b'}
              stroke="#64748b"
              strokeWidth={0.8}
              style={{ cursor: 'pointer' }}
              onMouseEnter={() => setHoveredPin(posId)}
              onMouseLeave={() => setHoveredPin(null)}
              onClick={(e) => {
                e.stopPropagation();
                onPinClick(part.id, 'bot_+', e.clientX, e.clientY);
              }}
            />
            {/* Bottom Negative Hole */}
            <circle
              cx={hx}
              cy={205}
              r={3.2}
              fill={hoveredPin === negId ? '#3b82f6' : '#1e293b'}
              stroke="#64748b"
              strokeWidth={0.8}
              style={{ cursor: 'pointer' }}
              onMouseEnter={() => setHoveredPin(negId)}
              onMouseLeave={() => setHoveredPin(null)}
              onClick={(e) => {
                e.stopPropagation();
                onPinClick(part.id, 'bot_-', e.clientX, e.clientY);
              }}
            />
          </g>
        );
      })}

      {/* Terminal Strip Rows: 1 to numRows */}
      {rowNumbers.map((r) => {
        const hx = 45 + (r - 1) * colSpacing;
        return (
          <g key={`row_strip_${r}`}>
            {/* Columns a-e (top side of center trench) */}
            {leftCols.map((col, cIdx) => {
              const hy = 65 + cIdx * 9.5;
              const holeId = `${r}${col}`;
              const isHov = hoveredPin === holeId;
              return (
                <circle
                  key={`hole_${holeId}`}
                  cx={hx}
                  cy={hy}
                  r={3.2}
                  fill={isHov ? '#10b981' : '#0f172a'}
                  stroke="#64748b"
                  strokeWidth={0.8}
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={() => setHoveredPin(holeId)}
                  onMouseLeave={() => setHoveredPin(null)}
                  onClick={(e) => {
                    e.stopPropagation();
                    onPinClick(part.id, holeId, e.clientX, e.clientY);
                  }}
                />
              );
            })}

            {/* Columns f-j (bottom side of center trench) */}
            {rightCols.map((col, cIdx) => {
              const hy = 125 + cIdx * 9.5;
              const holeId = `${r}${col}`;
              const isHov = hoveredPin === holeId;
              return (
                <circle
                  key={`hole_${holeId}`}
                  cx={hx}
                  cy={hy}
                  r={3.2}
                  fill={isHov ? '#10b981' : '#0f172a'}
                  stroke="#64748b"
                  strokeWidth={0.8}
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={() => setHoveredPin(holeId)}
                  onMouseLeave={() => setHoveredPin(null)}
                  onClick={(e) => {
                    e.stopPropagation();
                    onPinClick(part.id, holeId, e.clientX, e.clientY);
                  }}
                />
              );
            })}
          </g>
        );
      })}

      {/* Hover tooltip */}
      {hoveredPin && (
        <text x={width - 50} y={15} fill="#475569" fontSize="9" fontFamily="monospace">
          PIN: {hoveredPin}
        </text>
      )}
    </g>
  );
};

