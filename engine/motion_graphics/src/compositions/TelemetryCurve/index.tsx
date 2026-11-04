import React from 'react';
import { AbsoluteFill } from 'remotion';
import { Activity, ShieldAlert, Cpu } from 'lucide-react';
import { TelemetryCurveProps } from '../../types';
import { LineChart } from './LineChart';
import { ThresholdBadge } from './ThresholdBadge';
import {resolveYRange} from '../../utils/telemetry';

export const TelemetryCurve: React.FC<TelemetryCurveProps> = ({
  metricName,
  unit,
  classification,
  timestampLabel,
  dataPoints,
  timeLabels,
  color = '#00f0ff',
  fillArea = true,
  showGrid = true,
  yRange,
  thresholdValue,
  thresholdLabel,
  alarmActive = true,
  alarmColor = '#ff3366',
  currentStatus,
  summaryMetrics = [],
}) => {
  const chartLeft = 140;
  const chartTop = 220;
  const chartWidth = 1640;
  const chartHeight = 580;

  // Compute Y pixel coordinate for threshold
  const resolvedRange = resolveYRange(dataPoints, yRange);
  const [minY, maxY] = resolvedRange;
  const normalizedThreshold = (thresholdValue - minY) / (maxY - minY || 1);
  const thresholdYPosition = chartTop + chartHeight - normalizedThreshold * chartHeight;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: '#030712',
        overflow: 'hidden',
        fontFamily: 'ui-monospace, SFMono-Regular, "Roboto Mono", Menlo, monospace',
      }}
    >
      {/* Background ambient radial glow */}
      <div
        style={{
          position: 'absolute',
          top: '20%',
          left: '30%',
          width: '40%',
          height: '40%',
          borderRadius: '50%',
          background: `radial-gradient(circle, ${color}15 0%, rgba(3, 7, 18, 0) 70%)`,
          filter: 'blur(60px)',
          pointerEvents: 'none',
        }}
      />

      {/* Top Header & Classification Bar */}
      <div
        style={{
          position: 'absolute',
          top: 48,
          left: 64,
          right: 64,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          backgroundColor: 'rgba(7, 13, 24, 0.75)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.12)',
          borderRadius: 14,
          padding: '16px 28px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.6)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div
            style={{
              padding: '8px',
              borderRadius: 10,
              backgroundColor: `${color}20`,
              border: `1px solid ${color}`,
            }}
          >
            <Activity size={24} color={color} />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span
                style={{
                  fontSize: 10,
                  letterSpacing: 2,
                  fontWeight: 800,
                  color,
                  backgroundColor: `${color}18`,
                  padding: '2px 8px',
                  borderRadius: 4,
                }}
              >
                {classification}
              </span>
              <span style={{ fontSize: 11, color: 'rgba(255, 255, 255, 0.5)' }}>
                {timestampLabel}
              </span>
            </div>
            <h1
              style={{
                margin: '4px 0 0 0',
                fontSize: 24,
                fontWeight: 900,
                letterSpacing: 1,
                color: '#ffffff',
                textTransform: 'uppercase',
              }}
            >
              {metricName} ANALYSIS
            </h1>
          </div>
        </div>

        {/* Status Chip */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            backgroundColor: alarmActive ? `${alarmColor}22` : 'rgba(16, 185, 129, 0.15)',
            border: `1.5px solid ${alarmActive ? alarmColor : '#10b981'}`,
            borderRadius: 8,
            padding: '6px 14px',
          }}
        >
          <span
            style={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              backgroundColor: alarmActive ? alarmColor : '#10b981',
              boxShadow: `0 0 10px ${alarmActive ? alarmColor : '#10b981'}`,
            }}
          />
          <span
            style={{
              fontSize: 12,
              fontWeight: 800,
              letterSpacing: 1.5,
              color: alarmActive ? alarmColor : '#10b981',
            }}
          >
            {currentStatus}
          </span>
        </div>
      </div>

      {/* Main Curve Chart */}
      <LineChart
        dataPoints={dataPoints}
        timeLabels={timeLabels}
        metricName={metricName}
        unit={unit}
        color={color}
        fillArea={fillArea}
        showGrid={showGrid}
        yRange={resolvedRange}
        chartLeft={chartLeft}
        chartTop={chartTop}
        chartWidth={chartWidth}
        chartHeight={chartHeight}
      />

      {/* Threshold Guide & Dynamic Badge */}
      <ThresholdBadge
        yPosition={thresholdYPosition}
        thresholdValue={thresholdValue}
        thresholdLabel={thresholdLabel}
        unit={unit}
        alarmActive={alarmActive}
        alarmColor={alarmColor}
        chartLeft={chartLeft}
        chartRight={chartLeft + chartWidth}
      />

      {/* Bottom Summary Telemetry Cards */}
      {summaryMetrics.length > 0 && (
        <div
          style={{
            position: 'absolute',
            bottom: 40,
            left: 64,
            right: 64,
            display: 'grid',
            gridTemplateColumns: `repeat(${summaryMetrics.length}, 1fr)`,
            gap: 20,
          }}
        >
          {summaryMetrics.map((item, idx) => (
            <div
              key={idx}
              style={{
                backgroundColor: 'rgba(7, 13, 24, 0.8)',
                backdropFilter: 'blur(16px)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: 12,
                padding: '14px 20px',
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
              }}
            >
              <span
                style={{
                  fontSize: 10,
                  letterSpacing: 1.5,
                  color: 'rgba(255, 255, 255, 0.5)',
                  textTransform: 'uppercase',
                }}
              >
                {item.label}
              </span>
              <span
                style={{
                  fontSize: 20,
                  fontWeight: 800,
                  color: '#ffffff',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                {item.value} {item.unit || ''}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Scanline CRT overlay */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          backgroundImage:
            'repeating-linear-gradient(0deg, rgba(0,0,0,0.1) 0px, rgba(0,0,0,0.1) 1px, transparent 1px, transparent 3px)',
          pointerEvents: 'none',
        }}
      />
    </AbsoluteFill>
  );
};
