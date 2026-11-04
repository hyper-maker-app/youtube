import React from 'react';
import { AbsoluteFill } from 'remotion';
import { VolcanoSeismicMapProps } from '../../types';
import { SatelliteMapCanvas } from '../GeospatialStormMap/SatelliteMapCanvas';
import { TitleBar } from '../GeospatialStormMap/TitleBar';
import { SeismicWaves } from './SeismicWaves';
import { ThermalHeatOverlay } from './ThermalHeatOverlay';
import { VolcanoHUD } from './VolcanoHUD';

export const VolcanoSeismicMap: React.FC<VolcanoSeismicMapProps> = ({
  center,
  zoom,
  tileSource = 'esri_world_imagery',
  tileCache,
  volcanoName,
  classification,
  coordinatesLabel,
  magnitude,
  depthKm,
  alertLevel,
  alertColor = '#ff3300',
  seismicFrequencyHz,
  pWaveVelocity,
  sWaveVelocity,
  cameraPan,
  metrics = [],
  scanlines = true,
  gridOverlay = true,
}) => {
  return (
    <AbsoluteFill style={{ backgroundColor: '#050308', overflow: 'hidden' }}>
      {/* 1. Underlying Satellite Terrain Map */}
      <SatelliteMapCanvas
        center={center}
        zoom={zoom}
        tileSource={tileSource}
        tileCache={tileCache}
        cameraPan={cameraPan}
        scanlines={scanlines}
        gridOverlay={gridOverlay}
        accentColor={alertColor}
      />

      {/* 2. Thermal Magma Plume Heat Shimmer */}
      <ThermalHeatOverlay
        intensity={0.85}
        radius={220}
        accentColor={alertColor}
      />

      {/* 3. Expanding P-Wave and S-Wave Propagation */}
      <SeismicWaves
        magnitude={magnitude}
        pWaveVelocity={pWaveVelocity}
        sWaveVelocity={sWaveVelocity}
        alertColor={alertColor}
      />

      {/* 4. Top Tactical Title Bar */}
      <TitleBar
        title={volcanoName}
        subtitle={`SEISMIC ACTIVITY // MAGNITUDE M${magnitude.toFixed(1)}`}
        coordinatesLabel={coordinatesLabel}
        classification={classification}
        accentColor={alertColor}
      />

      {/* 5. Volcano Tactical HUD */}
      <VolcanoHUD
        volcanoName={volcanoName}
        magnitude={magnitude}
        depthKm={depthKm}
        alertLevel={alertLevel}
        alertColor={alertColor}
        seismicFrequencyHz={seismicFrequencyHz}
        metrics={metrics}
      />
    </AbsoluteFill>
  );
};
