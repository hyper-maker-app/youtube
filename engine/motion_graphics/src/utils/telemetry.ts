export function resolveYRange(data: number[], explicit?: [number, number]): [number, number] {
  if (explicit) return explicit;
  if (data.length < 2 || data.some((value) => !Number.isFinite(value))) throw new Error('Telemetry requires at least two finite data points');
  const min = Math.min(...data);
  const max = Math.max(...data);
  const padding = (max - min) * 0.15 || 10;
  return [Math.floor(min - padding), Math.ceil(max + padding)];
}
