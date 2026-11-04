import React from 'react';
import { AbsoluteFill, useVideoConfig } from 'remotion';
import { GeospatialStormMapProps } from '../../types';
import { SatelliteMapCanvas } from './SatelliteMapCanvas';
import { LightningEffects } from './LightningEffects';
import { TelemetryHUD } from './TelemetryHUD';
import { TitleBar } from './TitleBar';

export const GeospatialStormMap: React.FC<GeospatialStormMapProps> = ({
  center,
  zoom,
  tileSource = 'esri_world_imagery',
  tileCache,
  title,
  subtitle,
  coordinatesLabel,
  classification,
  timestampLabel,
  eventCount,
  eventCountLabel,
  systemStatus,
  statusLevel = 'WARNING',
  radarPulsing = true,
  strikeCount,
  lightningIntensity = 0.85,
  accentColor = '#00f0ff',
  metrics = [],
  scanlines = true,
  gridOverlay = true,
  cameraPan,
}) => {
  const {durationInFrames} = useVideoConfig();
  return (
    <AbsoluteFill style={{ backgroundColor: '#020408', overflow: 'hidden' }}>
      {/* 1. Underlying Satellite Raster Map Canvas */}
      <SatelliteMapCanvas
        center={center}
        zoom={zoom}
        tileSource={tileSource}
        tileCache={tileCache}
        cameraPan={cameraPan}
        scanlines={scanlines}
        gridOverlay={gridOverlay}
        accentColor={accentColor}
      />

      {/* 2. Procedural Lightning & Radar Shockwaves */}
      <LightningEffects
        strikeFrequency={strikeCount ? Math.max(1, Math.floor(durationInFrames / strikeCount)) : 40}
        strikeIntensity={lightningIntensity}
        color={accentColor}
        radarPulsing={radarPulsing}
      />

      {/* 3. Military / Tactical Title Bar */}
      <TitleBar
        title={title}
        subtitle={subtitle}
        coordinatesLabel={coordinatesLabel}
        classification={classification}
        timestampLabel={timestampLabel}
        accentColor={accentColor}
      />

      {/* 4. Glassmorphism Telemetry HUD Counter */}
      <TelemetryHUD
        eventCount={eventCount}
        eventCountLabel={eventCountLabel}
        systemStatus={systemStatus}
        statusLevel={statusLevel}
        metrics={metrics}
        accentColor={accentColor}
      />
    </AbsoluteFill>
  );
};
