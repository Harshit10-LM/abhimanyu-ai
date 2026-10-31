import React, { useState } from 'react';
import { Cpu, Grid, Zap, Radio, Activity, Search, Plus, ChevronLeft, ChevronRight, Layers } from 'lucide-react';

interface LibraryProps {
  onAddComponent: (type: string, defaultProps?: Record<string, any>) => void;
  disabled?: boolean;
}

interface ComponentItem {
  type: string;
  name: string;
  category: 'mcu' | 'breadboard' | 'basic' | 'actuator' | 'sensor';
  defaultProps?: Record<string, any>;
  icon: any;
}

export const ComponentLibrary: React.FC<LibraryProps> = ({ onAddComponent, disabled = false }) => {
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  const components: ComponentItem[] = [
    // Microcontrollers
    { type: 'arduino_uno', name: 'Arduino Uno', category: 'mcu', icon: Cpu },
    { type: 'esp32_devkit', name: 'ESP32 DevKit', category: 'mcu', icon: Cpu },
    { type: 'stm32_bluepill', name: 'STM32 Blue Pill', category: 'mcu', icon: Cpu },

    // Breadboards
    { type: 'breadboard_half', name: 'Half Breadboard', category: 'breadboard', icon: Grid },
    { type: 'breadboard_full', name: 'Full Breadboard', category: 'breadboard', icon: Grid },

    // Basic Components
    { type: 'led', name: 'LED (5mm)', category: 'basic', defaultProps: { color: 'red', forward_voltage: 2.0 }, icon: Zap },
    { type: 'resistor', name: 'Resistor', category: 'basic', defaultProps: { resistance: 220, unit: 'Ω' }, icon: Activity },
    { type: 'button', name: 'Push Button', category: 'basic', defaultProps: { is_pressed: false }, icon: Radio },
    { type: 'potentiometer', name: 'Potentiometer', category: 'basic', defaultProps: { ratio: 0.5 }, icon: Activity },
    { type: 'buzzer', name: 'Piezo Buzzer', category: 'basic', icon: Zap },

    // Actuators
    { type: 'servo', name: 'Micro Servo', category: 'actuator', icon: Cpu },

    // Sensors
    { type: 'dht11', name: 'DHT11 Temp', category: 'sensor', icon: Activity },
    { type: 'hcsr04', name: 'HC-SR04 Echo', category: 'sensor', icon: Radio },
  ];

  const filtered = components.filter((c) => {
    const matchesSearch = c.name.toLowerCase().includes(search.toLowerCase());
    const matchesCat = selectedCategory === 'all' || c.category === selectedCategory;
    return matchesSearch && matchesCat;
  });

  if (isCollapsed) {
    return (
      <div
        style={{
          width: 36,
          height: '100%',
          backgroundColor: '#fbf8f3',
          borderRight: '1px solid #dfd3c2',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          paddingTop: 8,
          gap: 12,
        }}
      >
        <button
          onClick={() => setIsCollapsed(false)}
          style={{
            background: 'none',
            border: 'none',
            color: '#781d32',
            cursor: 'pointer',
            padding: 4,
          }}
          title="Expand Component Library"
        >
          <ChevronRight size={18} />
        </button>
        <Layers size={16} style={{ color: '#8a7d75' }} />
      </div>
    );
  }

  return (
    <div
      style={{
        width: 155,
        height: '100%',
        backgroundColor: '#fbf8f3',
        borderRight: '1px solid #dfd3c2',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Header */}
      <div style={{ padding: '8px 10px', borderBottom: '1px solid #dfd3c2', backgroundColor: '#f6efe6', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 10, fontWeight: 800, color: '#781d32', letterSpacing: '0.4px', textTransform: 'uppercase' }}>
          PARTS
        </span>
        <button
          onClick={() => setIsCollapsed(true)}
          style={{ background: 'none', border: 'none', color: '#8a7d75', cursor: 'pointer', padding: 2 }}
          title="Collapse"
        >
          <ChevronLeft size={14} />
        </button>
      </div>

      {/* Search */}
      <div style={{ padding: '6px 8px', borderBottom: '1px solid #dfd3c2' }}>
        <input
          type="text"
          placeholder="Filter..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            width: '100%',
            padding: '4px 6px',
            backgroundColor: '#ffffff',
            border: '1px solid #d8c6b0',
            borderRadius: 4,
            color: '#2b2523',
            fontSize: 10,
            outline: 'none',
            boxSizing: 'border-box',
          }}
        />
      </div>

      {/* Component List */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '6px 4px', display: 'flex', flexDirection: 'column', gap: 4 }}>
        {filtered.map((c) => {
          const IconComp = c.icon;
          return (
            <div
              key={c.type}
              onClick={() => {
                if (!disabled) onAddComponent(c.type, c.defaultProps);
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 8px',
                backgroundColor: '#ffffff',
                border: '1px solid #e5dac9',
                borderRadius: 5,
                cursor: disabled ? 'not-allowed' : 'pointer',
                opacity: disabled ? 0.6 : 1,
                fontSize: 10,
                color: '#2b2523',
                fontWeight: 600,
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                if (!disabled) {
                  e.currentTarget.style.borderColor = '#781d32';
                  e.currentTarget.style.backgroundColor = '#fcf8f4';
                }
              }}
              onMouseLeave={(e) => {
                if (!disabled) {
                  e.currentTarget.style.borderColor = '#e5dac9';
                  e.currentTarget.style.backgroundColor = '#ffffff';
                }
              }}
              title={`Add ${c.name} to workspace`}
            >
              <div
                style={{
                  width: 18,
                  height: 18,
                  borderRadius: 3,
                  backgroundColor: 'rgba(120, 29, 50, 0.08)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#781d32',
                  flexShrink: 0,
                }}
              >
                <IconComp size={11} />
              </div>
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                {c.name}
              </span>
              <Plus size={10} style={{ color: '#8a7d75' }} />
            </div>
          );
        })}
      </div>
    </div>
  );
};
