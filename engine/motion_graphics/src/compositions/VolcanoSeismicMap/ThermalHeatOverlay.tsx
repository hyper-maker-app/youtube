import React from 'react';
import { interpolate, useCurrentFrame } from 'remotion';

interface ThermalHeatOverlayProps {
  epicenter?: [number, number];
  intensity?: number;
  radius?: number;
  accentColor?: string;
}

export const ThermalHeatOverlay: React.FC<ThermalHeatOverlayProps> = ({
  epicenter,
  intensity = 0.8,
  radius = 180,
  accentColor = '#ff3300',
}) => {
  const frame = useCurrentFrame();

  const cx = epicenter ? `${(epicenter[0] / 1920) * 100}%` : '50%';
  const cy = epicenter ? `${(epicenter[1] / 1080) * 100}%` : '50%';

  // Breathing thermal shimmer
  const scale = interpolate(frame % 90, [0, 45, 90], [1, 1.12, 1]);
  const opacity = interpolate(frame % 90, [0, 45, 90], [0.65, 0.85, 0.65]) * intensity;

  return (
    <div
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        mixBlendMode: 'screen',
        opacity,
      }}
    >
      <div
        style={{
          position: 'absolute',
          left: cx,
          top: cy,
          width: radius * 2,
          height: radius * 2,
          transform: `translate(-50%, -50%) scale(${scale})`,
          borderRadius: '50%',
          background: `radial-gradient(circle, #ffffff 0%, #ffeb3b 25%, ${accentColor} 55%, rgba(139, 0, 0, 0.4) 75%, transparent 100%)`,
          filter: 'blur(32px)',
        }}
      />
    </div>
  );
};
