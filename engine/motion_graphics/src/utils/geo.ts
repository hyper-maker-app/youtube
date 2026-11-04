/**
 * Geospatial Web Mercator projection utilities for Slippy Map tiles.
 * Supports standard tile coordinates, world pixel mapping, and bounding boxes.
 */

export const TILE_SIZE = 256;

/**
 * Clamps latitude to valid Mercator range [-85.05112878, 85.05112878]
 */
export function clampLat(lat: number): number {
  return Math.max(-85.05112878, Math.min(85.05112878, lat));
}

/**
 * Converts Latitude and Longitude to World Pixel coordinates at a given zoom level.
 */
export function latLonToWorldPixels(
  lat: number,
  lon: number,
  zoom: number
): { x: number; y: number } {
  const clampedLat = clampLat(lat);
  const scale = TILE_SIZE * Math.pow(2, zoom);

  const x = ((lon + 180) / 360) * scale;
  const sinLat = Math.sin((clampedLat * Math.PI) / 180);
  const y = (0.5 - Math.log((1 + sinLat) / (1 - sinLat)) / (4 * Math.PI)) * scale;

  return { x, y };
}

/**
 * Converts World Pixel coordinates back to Latitude and Longitude.
 */
export function worldPixelsToLatLon(
  x: number,
  y: number,
  zoom: number
): { lat: number; lon: number } {
  const scale = TILE_SIZE * Math.pow(2, zoom);
  const lon = (x / scale) * 360 - 180;

  const n = Math.PI - (2 * Math.PI * y) / scale;
  const lat = (180 / Math.PI) * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));

  return { lat, lon };
}

/**
 * Computes visible tile bounding box and offset for drawing on canvas.
 */
export interface VisibleTileInfo {
  tileX: number;
  tileY: number;
  drawX: number;
  drawY: number;
  size: number;
}

export function getVisibleTiles(
  centerLat: number,
  centerLon: number,
  zoom: number,
  canvasWidth: number,
  canvasHeight: number
): {
  tiles: VisibleTileInfo[];
  centerPixel: { x: number; y: number };
} {
  const tileZoom = Math.floor(zoom);
  const tileScale = Math.pow(2, zoom - tileZoom);
  const tileSize = TILE_SIZE * tileScale;
  const centerPixel = latLonToWorldPixels(centerLat, centerLon, zoom);
  const topLeftX = centerPixel.x - canvasWidth / 2;
  const topLeftY = centerPixel.y - canvasHeight / 2;

  const maxTiles = Math.pow(2, tileZoom);
  const minTileX = Math.floor(topLeftX / tileSize);
  const maxTileX = Math.floor((topLeftX + canvasWidth) / tileSize);
  const minTileY = Math.max(0, Math.floor(topLeftY / tileSize));
  const maxTileY = Math.min(maxTiles - 1, Math.floor((topLeftY + canvasHeight) / tileSize));

  const tiles: VisibleTileInfo[] = [];

  for (let tx = minTileX; tx <= maxTileX; tx++) {
    for (let ty = minTileY; ty <= maxTileY; ty++) {
      // Wrap X around antimeridian
      const wrappedTileX = ((tx % maxTiles) + maxTiles) % maxTiles;

      const drawX = tx * tileSize - topLeftX;
      const drawY = ty * tileSize - topLeftY;

      tiles.push({
        tileX: wrappedTileX,
        tileY: ty,
        drawX,
        drawY,
        size: tileSize,
      });
    }
  }

  return { tiles, centerPixel };
}
