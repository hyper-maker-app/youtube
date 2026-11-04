import React from 'react';
import { Compass, ShieldCheck } from 'lucide-react';

interface TitleBarProps {
  title: string;
  subtitle: string;
  coordinatesLabel: string;
  classification?: string;
  timestampLabel?: string;
  accentColor?: string;
}

export const TitleBar: React.FC<TitleBarProps> = ({
  title,
  subtitle,
  coordinatesLabel,
  classification = 'RESTRICTED // ORBITAL RECON',
  timestampLabel,
  accentColor = '#00f0ff',
}) => {
  return (
    <div
      style={{
        position: 'absolute',
        top: 48,
        left: 48,
        right: 48,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        zIndex: 50,
        fontFamily: 'ui-monospace, SFMono-Regular, "Roboto Mono", Menlo, monospace',
      }}
    >
      {/* Left Title & Subtitle block */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
          backgroundColor: 'rgba(7, 13, 24, 0.78)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          padding: '16px 24px',
          borderRadius: 12,
          border: '1px solid rgba(0, 240, 255, 0.25)',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span
            style={{
              padding: '2px 8px',
              backgroundColor: `${accentColor}22`,
              border: `1px solid ${accentColor}`,
              borderRadius: 4,
              fontSize: 10,
              fontWeight: 800,
              letterSpacing: 2,
              color: accentColor,
            }}
          >
            {classification}
          </span>
          {timestampLabel && (
            <span
              style={{
                fontSize: 11,
                color: 'rgba(255, 255, 255, 0.5)',
                letterSpacing: 1,
              }}
            >
              {timestampLabel}
            </span>
          )}
        </div>

        <h1
          style={{
            margin: 0,
            fontSize: 26,
            fontWeight: 900,
            letterSpacing: 1.5,
            color: '#ffffff',
            textTransform: 'uppercase',
            textShadow: '0 2px 10px rgba(0, 0, 0, 0.8)',
          }}
        >
          {title}
        </h1>

        <div
          style={{
            fontSize: 12,
            letterSpacing: 1,
            color: 'rgba(255, 255, 255, 0.7)',
            textTransform: 'uppercase',
          }}
        >
          {subtitle}
        </div>
      </div>

      {/* Right Coordinates & Grid Tag */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          backgroundColor: 'rgba(7, 13, 24, 0.78)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          padding: '14px 20px',
          borderRadius: 12,
          border: '1px solid rgba(255, 255, 255, 0.15)',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
          color: '#ffffff',
        }}
      >
        <Compass size={20} color={accentColor} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span
            style={{
              fontSize: 9,
              letterSpacing: 1.5,
              color: 'rgba(255, 255, 255, 0.5)',
              textTransform: 'uppercase',
            }}
          >
            GRID COORDINATES
          </span>
          <span
            style={{
              fontSize: 14,
              fontWeight: 800,
              letterSpacing: 1,
              color: '#ffffff',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {coordinatesLabel}
          </span>
        </div>
      </div>
    </div>
  );
};
