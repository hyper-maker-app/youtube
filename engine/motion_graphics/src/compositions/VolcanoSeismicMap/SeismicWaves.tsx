import React, { useEffect, useRef } from 'react';
import { interpolate, useCurrentFrame, useVideoConfig } from 'remotion';

interface SeismicWavesProps {
  epicenter?: [number, number];
  magnitude: number;
  pWaveVelocity?: number; // km/s
  sWaveVelocity?: number; // km/s
  alertColor?: string;
}

export const SeismicWaves: React.FC<SeismicWavesProps> = ({
  epicenter,
  magnitude,
  pWaveVelocity = 6.2,
  sWaveVelocity = 3.5,
  alertColor = '#ff4400',
}) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const cx = epicenter ? epicenter[0] : width / 2;
  const cy = epicenter ? epicenter[1] : height / 2;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, width, height);

    // Period of seismic pulse propagation
    const cycleFrames = 90;

    // 1. Primary Waves (P-Waves - Fast compression wave)
    const pCycles = 3;
    for (let i = 0; i < pCycles; i++) {
      const cycleProgress = ((frame + i * 30) % cycleFrames) / cycleFrames;
      const radius = cycleProgress * 520;
      const alpha = interpolate(cycleProgress, [0, 0.2, 1], [0.8, 0.4, 0]);

      ctx.save();
      ctx.lineWidth = 2;
      ctx.strokeStyle = `rgba(255, 200, 0, ${alpha})`;
      ctx.shadowColor = 'rgba(255, 200, 0, 0.8)';
      ctx.shadowBlur = 12;
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.stroke();

      // Distance tag on the wave
      if (radius > 120 && radius < 460) {
        ctx.fillStyle = `rgba(255, 200, 0, ${alpha * 0.9})`;
        ctx.font = '10px ui-monospace, monospace';
        const distKm = Math.round((radius / 520) * 80);
        ctx.fillText(`P-WAVE ${distKm}km`, cx + radius * 0.707 + 6, cy - radius * 0.707);
      }
      ctx.restore();
    }

    // 2. Secondary Shear Waves (S-Waves - Slower, high amplitude destructive wave)
    const sCycles = 2;
    for (let i = 0; i < sCycles; i++) {
      const cycleProgress = ((frame + i * 45) % cycleFrames) / cycleFrames;
      // S-wave is slower (~60% speed of P-wave)
      const radius = cycleProgress * 340;
      const alpha = interpolate(cycleProgress, [0, 0.2, 1], [0.95, 0.6, 0]);

      ctx.save();
      ctx.lineWidth = 3.5;
      ctx.strokeStyle = `${alertColor}${Math.floor(alpha * 255)
        .toString(16)
        .padStart(2, '0')}`;
      ctx.shadowColor = alertColor;
      ctx.shadowBlur = 18;
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.stroke();

      // Concentric dashed resonance
      ctx.setLineDash([8, 8]);
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = `rgba(255, 80, 80, ${alpha * 0.6})`;
      ctx.beginPath();
      ctx.arc(cx, cy, radius * 0.85, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }

    // 3. Epicenter Core Indicator
    const corePulse = interpolate(frame % 40, [0, 20, 40], [12, 18, 12]);
    ctx.save();
    ctx.fillStyle = alertColor;
    ctx.shadowColor = alertColor;
    ctx.shadowBlur = 24;
    ctx.beginPath();
    ctx.arc(cx, cy, corePulse, 0, Math.PI * 2);
    ctx.fill();

    // Epicenter Crosshair
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(cx - 24, cy);
    ctx.lineTo(cx + 24, cy);
    ctx.moveTo(cx, cy - 24);
    ctx.lineTo(cx, cy + 24);
    ctx.stroke();
    ctx.restore();
  }, [frame, width, height, cx, cy, magnitude, pWaveVelocity, sWaveVelocity, alertColor]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
      }}
    />
  );
};
