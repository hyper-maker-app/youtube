import React from 'react';
import { interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { Flame, Waves, AlertTriangle } from 'lucide-react';
import { MetricItem } from '../../types';

interface VolcanoHUDProps {
  volcanoName: string;
  magnitude: number;
  depthKm: number;
  alertLevel: string;
  alertColor?: string;
  seismicFrequencyHz: number;
  metrics?: MetricItem[];
}

export const VolcanoHUD: React.FC<VolcanoHUDProps> = ({
  volcanoName,
  magnitude,
  depthKm,
  alertLevel,
  alertColor = '#ff3300',
  seismicFrequencyHz,
  metrics = [],
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // Accelerating magnitude counter interpolation
  const magProgress = interpolate(
    frame,
    [0, Math.max(1, Math.floor(durationInFrames * 0.65))],
    [0, magnitude],
    {
      extrapolateRight: 'clamp',
    }
  );

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 48,
        left: 48,
        minWidth: 440,
        backgroundColor: 'rgba(12, 10, 16, 0.82)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        borderRadius: 14,
        border: `1.5px solid ${alertColor}66`,
        boxShadow: `0 8px 32px 0 rgba(0, 0, 0, 0.6), inset 0 0 20px ${alertColor}15`,
        padding: '24px 28px',
        color: '#f0f6fc',
        fontFamily: 'ui-monospace, SFMono-Regular, "Roboto Mono", Menlo, monospace',
        display: 'flex',
        flexDirection: 'column',
        gap: 18,
        zIndex: 50,
      }}
    >
      {/* Top Header */}
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
          <Flame size={20} color={alertColor} />
          <span
            style={{
              fontSize: 13,
              letterSpacing: 2,
              fontWeight: 800,
              color: '#ffffff',
              textTransform: 'uppercase',
            }}
          >
            {volcanoName}
          </span>
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '4px 10px',
            borderRadius: 6,
            backgroundColor: `${alertColor}22`,
            border: `1px solid ${alertColor}`,
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: alertColor,
              boxShadow: `0 0 10px ${alertColor}`,
            }}
          />
          <span
            style={{
              fontSize: 11,
              fontWeight: 800,
              letterSpacing: 1.5,
              color: alertColor,
            }}
          >
            ALERT: {alertLevel}
          </span>
        </div>
      </div>

      {/* Magnitude Counter */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
        <div
          style={{
            width: 64,
            height: 64,
            borderRadius: 12,
            backgroundColor: `${alertColor}22`,
            border: `1px solid ${alertColor}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: `0 0 20px ${alertColor}44`,
          }}
        >
          <Waves size={34} color={alertColor} />
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
            RICHTER MAGNITUDE (ML)
          </div>
          <div
            style={{
              fontSize: 48,
              fontWeight: 900,
              letterSpacing: 1,
              lineHeight: 1,
              color: '#ffffff',
              textShadow: `0 0 24px ${alertColor}`,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {magProgress.toFixed(1)}
          </div>
        </div>
      </div>

      {/* Primary Parameters */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: 12,
          paddingTop: 12,
          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span
            style={{
              fontSize: 10,
              letterSpacing: 1,
              color: 'rgba(255, 255, 255, 0.5)',
              textTransform: 'uppercase',
            }}
          >
            FOCAL DEPTH
          </span>
          <span
            style={{
              fontSize: 16,
              fontWeight: 700,
              color: '#ffffff',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {depthKm.toFixed(1)} KM
          </span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span
            style={{
              fontSize: 10,
              letterSpacing: 1,
              color: 'rgba(255, 255, 255, 0.5)',
              textTransform: 'uppercase',
            }}
          >
            DOMINANT FREQ
          </span>
          <span
            style={{
              fontSize: 16,
              fontWeight: 700,
              color: '#ffffff',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {seismicFrequencyHz.toFixed(2)} HZ
          </span>
        </div>

        {/* Custom Extra Metrics */}
        {metrics.map((m, idx) => (
          <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span
              style={{
                fontSize: 10,
                letterSpacing: 1,
                color: 'rgba(255, 255, 255, 0.5)',
                textTransform: 'uppercase',
              }}
            >
              {m.label}
            </span>
            <span
              style={{
                fontSize: 16,
                fontWeight: 700,
                color: '#ffffff',
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {m.value} {m.unit || ''}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};
