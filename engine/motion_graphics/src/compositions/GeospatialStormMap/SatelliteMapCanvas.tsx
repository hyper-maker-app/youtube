import React, { useEffect, useRef, useMemo } from 'react';
import { cancelRender, continueRender, delayRender, interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { getVisibleTiles } from '../../utils/geo';
import { loadTileImage, getCachedTileImage, resolveTileUrl } from '../../utils/tile_cache';
import { drawCornerBrackets, drawHudGrid } from '../../utils/canvas';
import { CameraPanConfig } from '../../types';

interface SatelliteMapCanvasProps {
  center: [number, number];
  zoom: number;
  tileSource?: string;
  tileCache?: Record<string, string>;
  cameraPan?: CameraPanConfig;
  scanlines?: boolean;
  gridOverlay?: boolean;
  accentColor?: string;
}

export const SatelliteMapCanvas: React.FC<SatelliteMapCanvasProps> = ({
  center,
  zoom,
  tileSource = 'esri_world_imagery',
  tileCache,
  cameraPan,
  scanlines = true,
  gridOverlay = true,
  accentColor = 'rgba(0, 220, 255, 0.6)',
}) => {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Compute camera pan and zoom interpolation across duration
  const panLat = cameraPan
    ? interpolate(frame, [0, durationInFrames], [0, cameraPan.deltaLat])
    : 0;
  const panLon = cameraPan
    ? interpolate(frame, [0, durationInFrames], [0, cameraPan.deltaLon])
    : 0;
  const zoomDrift = cameraPan
    ? interpolate(frame, [0, durationInFrames], [0, cameraPan.zoomDelta])
    : 0;

  const currentLat = center[0] + panLat;
  const currentLon = center[1] + panLon;
  const currentZoom = zoom + zoomDrift;

  // Calculate visible tiles for this frame
  const {tiles} = useMemo(
    () => getVisibleTiles(currentLat, currentLon, currentZoom, width, height),
    [currentLat, currentLon, currentZoom, width, height]
  );

  // Each frame owns a render handle until its tiles are loaded AND drawn.
  useEffect(() => {
    const handle = delayRender('Loading and drawing map tiles');
    let cancelled = false;
    const draw = async () => {
      const urls = tiles.map((t) => resolveTileUrl(tileSource, currentZoom, t.tileX, t.tileY)).map((url) => tileCache?.[url] ?? url);
      const images = await Promise.all(urls.map(loadTileImage));
      if (cancelled) return;
      if (images.some((image) => !image)) throw new Error('Unable to load required map tiles');
      const canvas = canvasRef.current;
      const ctx = canvas?.getContext('2d');
      if (!ctx) throw new Error('Map canvas is unavailable');
      ctx.fillStyle = '#060a10';
      ctx.fillRect(0, 0, width, height);
      tiles.forEach((tile, index) => {
        const image = getCachedTileImage(urls[index]);
        if (!image) throw new Error('Loaded map tile is missing from cache');
        ctx.drawImage(image, tile.drawX, tile.drawY, tile.size, tile.size);
      });
    // Grid overlay
    if (gridOverlay) {
      drawHudGrid(ctx, width, height, 160, 'rgba(0, 220, 255, 0.07)');
    }

    // Tactical center reticle
    const cx = width / 2;
    const cy = height / 2;
    drawCornerBrackets(ctx, cx - 60, cy - 60, 120, 120, 18, accentColor);

    // Center crosshair
    ctx.save();
    ctx.strokeStyle = accentColor;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(cx - 15, cy);
    ctx.lineTo(cx + 15, cy);
    ctx.moveTo(cx, cy - 15);
    ctx.lineTo(cx, cy + 15);
    ctx.stroke();

    // Center pulse circle
    const pulseRadius = interpolate(frame % 90, [0, 90], [20, 90]);
    const pulseAlpha = interpolate(frame % 90, [0, 90], [0.5, 0]);
    ctx.strokeStyle = `rgba(0, 240, 255, ${pulseAlpha})`;
    ctx.beginPath();
    ctx.arc(cx, cy, pulseRadius, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();

    // Vignette / atmospheric edge darkening
    const vignetteGradient = ctx.createRadialGradient(
      cx,
      cy,
      Math.min(width, height) * 0.35,
      cx,
      cy,
      Math.max(width, height) * 0.75
    );
    vignetteGradient.addColorStop(0, 'rgba(0, 0, 0, 0)');
    vignetteGradient.addColorStop(0.7, 'rgba(3, 7, 18, 0.55)');
    vignetteGradient.addColorStop(1, 'rgba(2, 4, 10, 0.95)');
    ctx.fillStyle = vignetteGradient;
    ctx.fillRect(0, 0, width, height);

    // Scanlines
    if (scanlines) {
      ctx.fillStyle = 'rgba(0, 0, 0, 0.12)';
      for (let y = 0; y < height; y += 4) {
        ctx.fillRect(0, y, width, 1.5);
      }
    }
      continueRender(handle);
    };
    draw().catch((error) => {
      if (!cancelled) cancelRender(error);
    });
    return () => {
      cancelled = true;
      continueRender(handle);
    };
  }, [tiles, tileSource, tileCache, currentZoom, width, height, frame, gridOverlay, scanlines, accentColor]);

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
        backgroundColor: '#05080f',
      }}
    />
  );
};
