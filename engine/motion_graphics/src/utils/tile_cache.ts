/**
 * Map tile caching and resolution utility.
 * Supports ESRI World Imagery, CartoDB Dark, CartoDB Positron, and custom raster templates.
 * Caches image objects in-memory for 60 FPS Remotion rendering and prevents redundant network fetches.
 */

import providers from '../../tile_providers.json';
export const TILE_PROVIDERS: Record<string, string> = providers;

// Global in-memory cache of HTMLImageElements
const imageMemoryCache = new Map<string, HTMLImageElement>();
const loadingPromises = new Map<string, Promise<HTMLImageElement | null>>();

/**
 * Resolves a tile URL given provider template, zoom, and tile coordinates.
 */
export function resolveTileUrl(
  templateOrKey: string,
  z: number,
  x: number,
  y: number
): string {
  const template = TILE_PROVIDERS[templateOrKey] || templateOrKey;
  return template
    .replace('{z}', String(Math.floor(z)))
    .replace('{x}', String(Math.floor(x)))
    .replace('{y}', String(Math.floor(y)));
}

/**
 * Creates a fallback procedural dark tile when network tile is unavailable.
 */
export function createFallbackTile(size = 256): HTMLCanvasElement {
  if (typeof document === 'undefined') {
    return null as unknown as HTMLCanvasElement;
  }
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  if (ctx) {
    ctx.fillStyle = '#0a0e14';
    ctx.fillRect(0, 0, size, size);
    ctx.strokeStyle = '#1a2332';
    ctx.lineWidth = 1;
    ctx.strokeRect(0, 0, size, size);
  }
  return canvas;
}

/**
 * Loads and caches an image tile in the browser/Chromium context.
 */
export function loadTileImage(url: string): Promise<HTMLImageElement | null> {
  if (typeof window === 'undefined') {
    return Promise.resolve(null);
  }

  // Already cached in memory
  if (imageMemoryCache.has(url)) {
    return Promise.resolve(imageMemoryCache.get(url)!);
  }

  // Already in-flight
  if (loadingPromises.has(url)) {
    return loadingPromises.get(url)!;
  }

  const promise = new Promise<HTMLImageElement | null>((resolve) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';

    img.onload = () => {
      imageMemoryCache.set(url, img);
      loadingPromises.delete(url);
      resolve(img);
    };

    img.onerror = () => {
      loadingPromises.delete(url);
      resolve(null);
    };

    img.src = url;
  });

  loadingPromises.set(url, promise);
  return promise;
}

/**
 * Synchronously retrieves a cached image if already loaded, or returns null.
 */
export function getCachedTileImage(url: string): HTMLImageElement | null {
  return imageMemoryCache.get(url) || null;
}
