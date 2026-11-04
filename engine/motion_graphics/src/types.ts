/**
 * Type definitions for Remotion Motion Graphics Engine.
 * SIFIR HARDCODE: All labels, numbers, and parameters are defined via props.
 */

export interface MetricItem {
  label: string;
  value: string | number;
  unit?: string;
}

export interface CameraPanConfig {
  deltaLat: number;
  deltaLon: number;
  zoomDelta: number;
}

export type TileSourceType = 'esri_world_imagery' | 'carto_dark' | 'carto_positron' | string;

export type GeospatialStormMapProps = {
  center: [number, number]; // [lat, lon]
  zoom: number;
  tileSource?: TileSourceType;
  tileCache?: Record<string, string>;
  title: string;
  subtitle: string;
  coordinatesLabel: string;
  classification: string;
  timestampLabel: string;
  eventCount: number;
  eventCountLabel: string;
  systemStatus: string;
  statusLevel?: 'NOMINAL' | 'WARNING' | 'CRITICAL' | 'DANGER';
  radarPulsing?: boolean;
  strikeCount?: number;
  lightningIntensity?: number;
  accentColor?: string;
  metrics: MetricItem[];
  scanlines?: boolean;
  gridOverlay?: boolean;
  cameraPan?: CameraPanConfig;
  [key: string]: unknown;
};

export type TelemetryCurveProps = {
  metricName: string;
  unit: string;
  classification: string;
  timestampLabel: string;
  dataPoints: number[];
  timeLabels?: string[];
  color?: string;
  fillArea?: boolean;
  showGrid?: boolean;
  yRange?: [number, number];
  thresholdValue: number;
  thresholdLabel: string;
  alarmActive?: boolean;
  alarmColor?: string;
  currentStatus: string;
  summaryMetrics: MetricItem[];
  [key: string]: unknown;
};

export type VolcanoSeismicMapProps = {
  center: [number, number];
  zoom: number;
  tileSource?: TileSourceType;
  tileCache?: Record<string, string>;
  volcanoName: string;
  classification: string;
  coordinatesLabel: string;
  magnitude: number;
  depthKm: number;
  alertLevel: string;
  alertColor?: string;
  seismicFrequencyHz: number;
  pWaveVelocity: number; // km/s
  sWaveVelocity: number; // km/s
  cameraPan?: CameraPanConfig;
  metrics: MetricItem[];
  scanlines?: boolean;
  gridOverlay?: boolean;
  [key: string]: unknown;
};
