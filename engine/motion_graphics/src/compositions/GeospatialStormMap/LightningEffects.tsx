import React, { useEffect, useRef } from 'react';
import { interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { generateLightningBolt } from '../../utils/canvas';

interface LightningEffectsProps {
  epicenter?: [number, number]; // [x, y] in screen pixels or defaults to center
  strikeFrequency?: number; // frame interval
  strikeIntensity?: number; // 0 to 1
  color?: string;
  radarPulsing?: boolean;
}

export const LightningEffects: React.FC<LightningEffectsProps> = ({
  epicenter,
  strikeFrequency = 45,
  strikeIntensity = 0.8,
  color = 'rgba(190, 230, 255, 0.95)',
  radarPulsing = true,
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

    // 1. Radar Shockwaves / Pulsing Ripples
    if (radarPulsing) {
      const rippleCycles = 3;
      const ripplePeriod = 60; // frames per ring

      for (let i = 0; i < rippleCycles; i++) {
        const offset = (frame + i * (ripplePeriod / rippleCycles)) % ripplePeriod;
        const radius = interpolate(offset, [0, ripplePeriod], [20, 480]);
        const alpha = interpolate(offset, [0, ripplePeriod * 0.2, ripplePeriod], [0, 0.45, 0]);

        ctx.save();
        ctx.lineWidth = 2;
        ctx.strokeStyle = `rgba(0, 230, 255, ${alpha})`;
        ctx.shadowColor = 'rgba(0, 230, 255, 0.8)';
        ctx.shadowBlur = 10;
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.stroke();

        // Secondary inner dashed ripple
        ctx.setLineDash([6, 12]);
        ctx.strokeStyle = `rgba(180, 240, 255, ${alpha * 0.7})`;
        ctx.beginPath();
        ctx.arc(cx, cy, radius * 0.75, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
      }
    }

    // 2. Forked Fractal Lightning Strikes
    // Periodic burst pattern based on frame
    const cycle = frame % strikeFrequency;
    const isStriking = cycle < 8; // Flash lasts ~8 frames

    if (isStriking && strikeIntensity > 0) {
      const strikeAlpha = interpolate(cycle, [0, 2, 7], [0.95, 1.0, 0], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      });

      // Pseudo-random angle seeded by frame cycle index
      const seed = Math.floor(frame / strikeFrequency);
      const angle = (seed * 137.5 * Math.PI) / 180;
      const strikeLength = 220 + (seed % 100);

      const targetX = cx + Math.cos(angle) * strikeLength;
      const targetY = cy + Math.sin(angle) * strikeLength;

      const mainBolt = generateLightningBolt(
        { x: cx, y: cy },
        { x: targetX, y: targetY },
        60,
        6
      );

      // Draw Main Bolt with high neon glow
      ctx.save();
      ctx.strokeStyle = color;
      ctx.lineWidth = 3.5;
      ctx.shadowColor = 'rgba(120, 210, 255, 1)';
      ctx.shadowBlur = 24;

      ctx.beginPath();
      for (let i = 0; i < mainBolt.length; i++) {
        if (i === 0) ctx.moveTo(mainBolt[i].x, mainBolt[i].y);
        else ctx.lineTo(mainBolt[i].x, mainBolt[i].y);
      }
      ctx.stroke();

      // Core white hot channel
      ctx.strokeStyle = `rgba(255, 255, 255, ${strikeAlpha})`;
      ctx.lineWidth = 1.8;
      ctx.stroke();

      // Branch 1
      if (mainBolt.length > 5) {
        const branchPoint = mainBolt[Math.floor(mainBolt.length * 0.45)];
        const branchEnd = {
          x: branchPoint.x + Math.cos(angle + 0.6) * 110,
          y: branchPoint.y + Math.sin(angle + 0.6) * 110,
        };
        const branchBolt = generateLightningBolt(branchPoint, branchEnd, 35, 5);

        ctx.strokeStyle = `rgba(160, 220, 255, ${strikeAlpha * 0.8})`;
        ctx.lineWidth = 2;
        ctx.beginPath();
        for (let i = 0; i < branchBolt.length; i++) {
          if (i === 0) ctx.moveTo(branchBolt[i].x, branchBolt[i].y);
          else ctx.lineTo(branchBolt[i].x, branchBolt[i].y);
        }
        ctx.stroke();
      }

      // Branch 2
      if (mainBolt.length > 7) {
        const branchPoint2 = mainBolt[Math.floor(mainBolt.length * 0.7)];
        const branchEnd2 = {
          x: branchPoint2.x + Math.cos(angle - 0.7) * 90,
          y: branchPoint2.y + Math.sin(angle - 0.7) * 90,
        };
        const branchBolt2 = generateLightningBolt(branchPoint2, branchEnd2, 25, 4);

        ctx.strokeStyle = `rgba(160, 220, 255, ${strikeAlpha * 0.7})`;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        for (let i = 0; i < branchBolt2.length; i++) {
          if (i === 0) ctx.moveTo(branchBolt2[i].x, branchBolt2[i].y);
          else ctx.lineTo(branchBolt2[i].x, branchBolt2[i].y);
        }
        ctx.stroke();
      }

      // Atmospheric flash at epicenter
      const flashGrad = ctx.createRadialGradient(cx, cy, 10, cx, cy, 260);
      flashGrad.addColorStop(0, `rgba(200, 240, 255, ${strikeAlpha * 0.45})`);
      flashGrad.addColorStop(0.5, `rgba(80, 180, 255, ${strikeAlpha * 0.15})`);
      flashGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');
      ctx.fillStyle = flashGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, 260, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();
    }
  }, [frame, width, height, cx, cy, strikeFrequency, strikeIntensity, color, radarPulsing]);

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
