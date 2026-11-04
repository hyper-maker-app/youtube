import React from 'react';
import { interpolate, useCurrentFrame } from 'remotion';
import { AlertTriangle, AlertOctagon } from 'lucide-react';

interface ThresholdBadgeProps {
  yPosition: number; // Y pixel position on canvas/chart
  thresholdValue: number;
  thresholdLabel: string;
  unit: string;
  alarmActive?: boolean;
  alarmColor?: string;
  chartLeft: number;
  chartRight: number;
}

export const ThresholdBadge: React.FC<ThresholdBadgeProps> = ({
  yPosition,
  thresholdValue,
  thresholdLabel,
  unit,
  alarmActive = true,
  alarmColor = '#ff3366',
  chartLeft,
  chartRight,
}) => {
  const frame = useCurrentFrame();

  // Flashing pulse animation if alarm is active
  const pulseAlpha = alarmActive
    ? interpolate(frame % 30, [0, 15, 30], [0.6, 1.0, 0.6])
    : 0.7;

  return (
    <div
      style={{
        position: 'absolute',
        top: yPosition,
        left: chartLeft,
        right: 1920 - chartRight,
        pointerEvents: 'none',
        zIndex: 40,
        transform: 'translateY(-50%)',
        fontFamily: 'ui-monospace, SFMono-Regular, "Roboto Mono", Menlo, monospace',
      }}
    >
      {/* Dashed threshold guide line */}
      <svg
        width="100%"
        height="20"
        style={{ position: 'absolute', top: 0, left: 0, overflow: 'visible' }}
      >
        <line
          x1="0"
          y1="10"
          x2="100%"
          y2="10"
          stroke={alarmColor}
          strokeWidth="2"
          strokeDasharray="6 6"
          strokeOpacity={pulseAlpha}
          style={{
            filter: `drop-shadow(0 0 8px ${alarmColor})`,
          }}
        />
      </svg>

      {/* Warning Badge Tag */}
      <div
        style={{
          position: 'absolute',
          right: 0,
          top: -16,
          backgroundColor: 'rgba(20, 10, 20, 0.9)',
          border: `1.5px solid ${alarmColor}`,
          borderRadius: 8,
          padding: '6px 14px',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          boxShadow: `0 0 20px ${alarmColor}66`,
          color: '#ffffff',
        }}
      >
        <AlertTriangle size={16} color={alarmColor} />
        <span
          style={{
            fontSize: 12,
            fontWeight: 800,
            letterSpacing: 1.5,
            color: alarmColor,
            textTransform: 'uppercase',
          }}
        >
          {thresholdLabel}
        </span>
        <span
          style={{
            fontSize: 12,
            fontWeight: 700,
            color: '#ffffff',
            paddingLeft: 4,
            borderLeft: '1px solid rgba(255, 255, 255, 0.2)',
          }}
        >
          {thresholdValue} {unit}
        </span>
      </div>
    </div>
  );
};
