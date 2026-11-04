import schemas from '../../payload_schema.json';
export function validatePayload<T extends Record<string, unknown>>(template: keyof typeof schemas, props: T): T {
  const schema = schemas[template];
  for (const key of schema.strings) if (typeof props[key] !== 'string') throw new Error(`Missing string payload field: ${key}`);
  for (const key of schema.numbers) if (typeof props[key] !== 'number' || !Number.isFinite(props[key])) throw new Error(`Missing finite numeric payload field: ${key}`);
  for (const key of schema.arrays) if (!Array.isArray(props[key])) throw new Error(`Missing array payload field: ${key}`);
  if ('map' in schema) {
    if (props.tileSource !== undefined && typeof props.tileSource !== 'string') throw new Error('tileSource must be a string');
    const pan = props.cameraPan as Record<string, number> | undefined;
    if (pan !== undefined && (!pan || ['deltaLat','deltaLon','zoomDelta'].some((key) => typeof pan[key] !== 'number' || !Number.isFinite(pan[key])))) throw new Error('cameraPan requires finite deltaLat, deltaLon and zoomDelta');
    const center = props.center as number[];
    if (!Array.isArray(center) || center.length !== 2 || center.some((v) => !Number.isFinite(v)) || Math.abs(center[0]) > 85.05112878 || Math.abs(center[1]) > 180) throw new Error('center must be valid [latitude, longitude]');
    if (typeof props.zoom !== 'number' || !Number.isFinite(props.zoom) || props.zoom < 0 || props.zoom > 22) throw new Error('zoom must be between 0 and 22');
  }
  if (template === 'TelemetryCurve') {
    const data = props.dataPoints as number[];
    if (data.length < 2 || data.some((value) => typeof value !== 'number' || !Number.isFinite(value))) throw new Error('dataPoints requires at least two finite numbers');
    const range = props.yRange as number[] | undefined;
    if (range && (!Array.isArray(range) || range.length !== 2 || range.some((v) => !Number.isFinite(v)) || range[1] <= range[0])) throw new Error('yRange must be [min, max] with max > min');
  }
  for (const key of ['metrics', 'summaryMetrics']) {
    const items = props[key] as {label: string; value: unknown}[] | undefined;
    if (items && items.some((item) => !item || typeof item.label !== 'string' || (!['string','number'].includes(typeof item.value) || (typeof item.value === 'number' && !Number.isFinite(item.value))))) throw new Error(`${key} items require label and value`);
  }
  return props;
}
