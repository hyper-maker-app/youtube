import React from 'react';
import { interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { Zap, Activity, ShieldAlert, Radio } from 'lucide-react';
import { MetricItem } from '../../types';

interface TelemetryHUDProps {
  eventCount: number;
  eventCountLabel: string;
  systemStatus: string;
  statusLevel?: 'NOMINAL' | 'WARNING' | 'CRITICAL' | 'DANGER';
  metrics?: MetricItem[];
  accentColor?: string;
  glassmorphism?: boolean;
}

export const TelemetryHUD: React.FC<TelemetryHUDProps> = ({
  eventCount,
  eventCountLabel,
  systemStatus,
  statusLevel = 'WARNING',
  metrics = [],
  accentColor = '#00f0ff',
  glassmorphism = true,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // Accelerating number counter interpolation from 0 to eventCount
  // Curve eases into the final number across the first 70% of frames
  const countProgress = interpolate(
    frame,
    [0, Math.max(1, Math.floor(durationInFrames * 0.7))],
    [0, eventCount],
    {
      extrapolateRight: 'clamp',
    }
  );
  const currentCount = Math.floor(countProgress);

  // Status color map
  const statusColors: Record<string, string> = {
    NOMINAL: '#10b981',
    WARNING: '#f59e0b',
    CRITICAL: '#ef4444',
    DANGER: '#ff0055',
  };
  const badgeColor = statusColors[statusLevel] || '#f59e0b';

  // Subtle glass glow pulse
  const glowAlpha = interpolate(frame % 60, [0, 30, 60], [0.3, 0.6, 0.3]);

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 48,
        left: 48,
        minWidth: 420,
        backgroundColor: glassmorphism ? 'rgba(7, 13, 24, 0.78)' : 'rgba(10, 15, 25, 0.95)',
        backdropFilter: glassmorphism ? 'blur(16px)' : 'none',
        WebkitBackdropFilter: glassmorphism ? 'blur(16px)' : 'none',
        borderRadius: 14,
        border: `1px solid rgba(0, 240, 255, ${glowAlpha})`,
        boxShadow: `0 8px 32px 0 rgba(0, 0, 0, 0.6), inset 0 0 16px rgba(0, 240, 255, 0.1)`,
        padding: '24px 28px',
        color: '#f0f6fc',
        fontFamily: 'ui-monospace, SFMono-Regular, "Roboto Mono", Menlo, monospace',
        display: 'flex',
        flexDirection: 'column',
        gap: 18,
        zIndex: 50,
      }}
    >
      {/* Header status bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid rgba(255, 255, 255, 0.12)',
          paddingBottom: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Radio size={18} color={accentColor} style={{ animation: 'spin 4s linear infinite' }} />
          <span
            style={{
              fontSize: 13,
              letterSpacing: 2,
              fontWeight: 700,
              color: 'rgba(255, 255, 255, 0.7)',
              textTransform: 'uppercase',
            }}
          >
            TELEMETRY FEED
          </span>
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '4px 10px',
            borderRadius: 6,
            backgroundColor: `${badgeColor}22`,
            border: `1px solid ${badgeColor}`,
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: badgeColor,
              boxShadow: `0 0 8px ${badgeColor}`,
            }}
          />
          <span
            style={{
              fontSize: 11,
              fontWeight: 800,
              letterSpacing: 1.5,
              color: badgeColor,
            }}
          >
            {systemStatus}
          </span>
        </div>
      </div>

      {/* Main Counter Display */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
        <div
          style={{
            width: 58,
            height: 58,
            borderRadius: 12,
            backgroundColor: 'rgba(0, 240, 255, 0.12)',
            border: `1px solid ${accentColor}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: `0 0 20px ${accentColor}44`,
          }}
        >
          <Zap size={32} color={accentColor} />
        </div>

        <div>
          <div
            style={{
              fontSize: 11,
              letterSpacing: 1.5,
              color: 'rgba(255, 255, 255, 0.6)',
              textTransform: 'uppercase',
              marginBottom: 4,
            }}
          >
            {eventCountLabel}
          </div>
          <div
            style={{
              fontSize: 44,
              fontWeight: 900,
              letterSpacing: 1,
              lineHeight: 1,
              color: '#ffffff',
              textShadow: `0 0 20px ${accentColor}`,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {currentCount.toLocaleString()}
          </div>
        </div>
      </div>

      {/* Additional telemetry parameters */}
      {metrics.length > 0 && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: 12,
            paddingTop: 12,
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
          }}
        >
          {metrics.map((metric, idx) => (
            <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span
                style={{
                  fontSize: 10,
                  letterSpacing: 1,
                  color: 'rgba(255, 255, 255, 0.5)',
                  textTransform: 'uppercase',
                }}
              >
                {metric.label}
              </span>
              <span
                style={{
                  fontSize: 15,
                  fontWeight: 700,
                  color: '#e2e8f0',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {metric.value} {metric.unit ? metric.unit : ''}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
