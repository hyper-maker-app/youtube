/**
 * Canvas 2D and HUD rendering utilities for tactical overlays.
 */

export interface ReticleConfig {
  x: number;
  y: number;
  radius: number;
  color?: string;
  label?: string;
}

/**
 * Draws tactical HUD grid lines across a canvas.
 */
export function drawHudGrid(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  step = 120,
  strokeColor = 'rgba(0, 220, 255, 0.08)'
): void {
  ctx.save();
  ctx.strokeStyle = strokeColor;
  ctx.lineWidth = 1;

  // Vertical lines
  for (let x = 0; x <= width; x += step) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }

  // Horizontal lines
  for (let y = 0; y <= height; y += step) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }

  ctx.restore();
}

/**
 * Draws tactical corner brackets for viewfinders / target locks.
 */
export function drawCornerBrackets(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  len = 24,
  color = 'rgba(0, 255, 200, 0.6)'
): void {
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;

  // Top Left
  ctx.beginPath();
  ctx.moveTo(x, y + len);
  ctx.lineTo(x, y);
  ctx.lineTo(x + len, y);
  ctx.stroke();

  // Top Right
  ctx.beginPath();
  ctx.moveTo(x + w - len, y);
  ctx.lineTo(x + w, y);
  ctx.lineTo(x + w, y + len);
  ctx.stroke();

  // Bottom Left
  ctx.beginPath();
  ctx.moveTo(x, y + h - len);
  ctx.lineTo(x, y + h);
  ctx.lineTo(x + len, y + h);
  ctx.stroke();

  // Bottom Right
  ctx.beginPath();
  ctx.moveTo(x + w - len, y + h);
  ctx.lineTo(x + w, y + h);
  ctx.lineTo(x + w, y + h - len);
  ctx.stroke();

  ctx.restore();
}

/**
 * Generates an organic fractal lightning bolt path between two points.
 */
export interface Point {
  x: number;
  y: number;
}

export function generateLightningBolt(
  start: Point,
  end: Point,
  displace = 80,
  minDisplace = 4
): Point[] {
  let points: Point[] = [start, end];

  let currentDisplace = displace;
  while (currentDisplace > minDisplace) {
    const nextPoints: Point[] = [];
    for (let i = 0; i < points.length - 1; i++) {
      const p1 = points[i];
      const p2 = points[i + 1];

      const midX = (p1.x + p2.x) / 2;
      const midY = (p1.y + p2.y) / 2;

      // Normal vector
      const dx = p2.x - p1.x;
      const dy = p2.y - p1.y;
      const len = Math.sqrt(dx * dx + dy * dy);
      const nx = -dy / (len || 1);
      const ny = dx / (len || 1);

      const offset = (Math.random() - 0.5) * currentDisplace;

      nextPoints.push(p1);
      nextPoints.push({
        x: midX + nx * offset,
        y: midY + ny * offset,
      });
    }
    nextPoints.push(points[points.length - 1]);
    points = nextPoints;
    currentDisplace /= 2;
  }

  return points;
}
