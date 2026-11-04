import React, { useMemo } from 'react';
import { interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import {resolveYRange} from '../../utils/telemetry';

interface LineChartProps {
  dataPoints: number[];
  timeLabels?: string[];
  metricName: string;
  unit: string;
  color?: string;
  fillArea?: boolean;
  showGrid?: boolean;
  yRange?: [number, number];
  chartLeft?: number;
  chartTop?: number;
  chartWidth?: number;
  chartHeight?: number;
}

export const LineChart: React.FC<LineChartProps> = ({
  dataPoints,
  timeLabels = [],
  metricName,
  unit,
  color = '#00f0ff',
  fillArea = true,
  showGrid = true,
  yRange,
  chartLeft = 140,
  chartTop = 220,
  chartWidth = 1640,
  chartHeight = 620,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // Compute min/max range
  const [minY, maxY] = useMemo(() => resolveYRange(dataPoints, yRange), [dataPoints, yRange]);

  // Interpolate draw progress across duration
  const progress = interpolate(frame, [0, Math.max(1, Math.floor(durationInFrames * 0.85))], [0, 1], {
    extrapolateRight: 'clamp',
  });

  // Calculate coordinates of data points
  const points = useMemo(() => {
    if (dataPoints.length === 0) return [];
    const stepX = chartWidth / (dataPoints.length - 1);
    return dataPoints.map((val, idx) => {
      const x = chartLeft + idx * stepX;
      const normalizedY = (val - minY) / (maxY - minY || 1);
      const y = chartTop + chartHeight - normalizedY * chartHeight;
      return { x, y, val };
    });
  }, [dataPoints, minY, maxY, chartLeft, chartTop, chartWidth, chartHeight]);

  // Construct smooth SVG Bezier curve path
  const { linePath, areaPath, activePoint } = useMemo(() => {
    if (points.length < 2) return { linePath: '', areaPath: '', activePoint: points[0] };

    // Visible slice based on progress
    const totalPoints = points.length;
    const currentProgressIndex = progress * (totalPoints - 1);
    const baseIdx = Math.floor(currentProgressIndex);
    const fraction = currentProgressIndex - baseIdx;

    const visiblePoints = points.slice(0, baseIdx + 1);
    let interpolatedPoint = points[baseIdx];

    if (fraction > 0 && baseIdx + 1 < points.length) {
      const p1 = points[baseIdx];
      const p2 = points[baseIdx + 1];
      interpolatedPoint = {
        x: p1.x + (p2.x - p1.x) * fraction,
        y: p1.y + (p2.y - p1.y) * fraction,
        val: p1.val + (p2.val - p1.val) * fraction,
      };
      visiblePoints.push(interpolatedPoint);
    }

    if (visiblePoints.length === 0) return { linePath: '', areaPath: '', activePoint: points[0] };

    let d = `M ${visiblePoints[0].x} ${visiblePoints[0].y}`;
    for (let i = 0; i < visiblePoints.length - 1; i++) {
      const p0 = visiblePoints[i];
      const p1 = visiblePoints[i + 1];
      const cx = (p0.x + p1.x) / 2;
      d += ` C ${cx} ${p0.y}, ${cx} ${p1.y}, ${p1.x} ${p1.y}`;
    }

    const last = visiblePoints[visiblePoints.length - 1];
    const area = `${d} L ${last.x} ${chartTop + chartHeight} L ${visiblePoints[0].x} ${
      chartTop + chartHeight
    } Z`;

    return {
      linePath: d,
      areaPath: area,
      activePoint: last,
    };
  }, [points, progress, chartTop, chartHeight]);

  // Grid steps
  const gridRows = 5;
  const gridCols = timeLabels.length > 1 ? timeLabels.length - 1 : Math.min(8, dataPoints.length - 1);

  return (
    <div
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        fontFamily: 'ui-monospace, SFMono-Regular, "Roboto Mono", Menlo, monospace',
      }}
    >
      <svg
        width="1920"
        height="1080"
        style={{ position: 'absolute', top: 0, left: 0, overflow: 'visible' }}
      >
        <defs>
          {/* Neon gradient fill */}
          <linearGradient id="neonGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.35" />
            <stop offset="60%" stopColor={color} stopOpacity="0.08" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>

          {/* Glow filter */}
          <filter id="neonGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="6" result="blur1" />
            <feGaussianBlur stdDeviation="14" result="blur2" />
            <feMerge>
              <feMergeNode in="blur2" />
              <feMergeNode in="blur1" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* 1. Tactical Grid */}
        {showGrid && (
          <g opacity="0.18">
            {/* Horizontal rows */}
            {Array.from({ length: gridRows + 1 }).map((_, r) => {
              const y = chartTop + (r * chartHeight) / gridRows;
              const val = maxY - (r * (maxY - minY)) / gridRows;
              return (
                <g key={`r-${r}`}>
                  <line
                    x1={chartLeft}
                    y1={y}
                    x2={chartLeft + chartWidth}
                    y2={y}
                    stroke="#ffffff"
                    strokeWidth="1"
                    strokeDasharray="4 6"
                  />
                  <text
                    x={chartLeft - 16}
                    y={y + 4}
                    fill="rgba(255, 255, 255, 0.7)"
                    fontSize="12"
                    textAnchor="end"
                    fontWeight="700"
                  >
                    {Math.round(val)} {unit}
                  </text>
                </g>
              );
            })}

            {/* Vertical cols */}
            {Array.from({ length: gridCols + 1 }).map((_, c) => {
              const x = chartLeft + (c * chartWidth) / gridCols;
              const label =
                timeLabels[c] || `#${Number((c * (dataPoints.length - 1) / gridCols).toFixed(2))}`;
              return (
                <g key={`c-${c}`}>
                  <line
                    x1={x}
                    y1={chartTop}
                    x2={x}
                    y2={chartTop + chartHeight}
                    stroke="#ffffff"
                    strokeWidth="1"
                    strokeDasharray="4 6"
                  />
                  <text
                    x={x}
                    y={chartTop + chartHeight + 24}
                    fill="rgba(255, 255, 255, 0.6)"
                    fontSize="11"
                    textAnchor="middle"
                  >
                    {label}
                  </text>
                </g>
              );
            })}
          </g>
        )}

        {/* 2. Gradient Area Fill */}
        {fillArea && areaPath && <path d={areaPath} fill="url(#neonGradient)" />}

        {/* 3. Glowing Bezier Stroke */}
        {linePath && (
          <path
            d={linePath}
            fill="none"
            stroke={color}
            strokeWidth="3.5"
            strokeLinecap="round"
            filter="url(#neonGlow)"
          />
        )}

        {/* 4. Active Scanline Cursor and Current Value Indicator */}
        {activePoint && (
          <g>
            {/* Vertical scanning laser line */}
            <line
              x1={activePoint.x}
              y1={chartTop}
              x2={activePoint.x}
              y2={chartTop + chartHeight}
              stroke="rgba(255, 255, 255, 0.3)"
              strokeWidth="1.5"
              strokeDasharray="2 4"
            />

            {/* Glowing tracer dot */}
            <circle
              cx={activePoint.x}
              cy={activePoint.y}
              r="7"
              fill="#ffffff"
              stroke={color}
              strokeWidth="3"
              style={{
                filter: `drop-shadow(0 0 12px ${color})`,
              }}
            />

            {/* Ripple ring around current point */}
            <circle
              cx={activePoint.x}
              cy={activePoint.y}
              r="16"
              fill="none"
              stroke={color}
              strokeWidth="1.5"
              opacity="0.7"
            />
          </g>
        )}
      </svg>

      {/* Real-time Current Point HUD readout floating beside tracer */}
      {activePoint && (
        <div
          style={{
            position: 'absolute',
            left: Math.min(activePoint.x + 20, chartLeft + chartWidth - 140),
            top: Math.max(activePoint.y - 45, chartTop),
            backgroundColor: 'rgba(5, 12, 22, 0.85)',
            backdropFilter: 'blur(12px)',
            border: `1px solid ${color}`,
            borderRadius: 8,
            padding: '6px 12px',
            boxShadow: `0 0 16px ${color}44`,
            color: '#ffffff',
            pointerEvents: 'none',
          }}
        >
          <div style={{ fontSize: 10, color: 'rgba(255, 255, 255, 0.6)', letterSpacing: 1 }}>
            LIVE READOUT
          </div>
          <div style={{ fontSize: 16, fontWeight: 800, color, fontVariantNumeric: 'tabular-nums' }}>
            {activePoint.val.toFixed(1)} {unit}
          </div>
        </div>
      )}
    </div>
  );
};
