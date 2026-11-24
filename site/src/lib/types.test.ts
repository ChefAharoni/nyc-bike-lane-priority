import { existsSync, readFileSync } from 'node:fs';
import { dirname, isAbsolute, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gunzipSync } from 'node:zlib';
import { describe, expect, it } from 'vitest';
import type {
  Area, AreaTotals, Areas, Block, Meta, SnapshotIndex, Stretch, Street,
} from './types';

// CONTRACT_DIR points the same checks at another directory (for example the real pipeline output).
const HERE = dirname(fileURLToPath(import.meta.url));
const DATA = process.env.CONTRACT_DIR
  ? (isAbsolute(process.env.CONTRACT_DIR) ? process.env.CONTRACT_DIR : resolve(process.cwd(), process.env.CONTRACT_DIR))
  : join(HERE, '../../fixtures/data');
// CONTRACT_SNAPSHOTS_DIR: where snapshots/ lives when it is not inside CONTRACT_DIR (the nightly job
// downloads data-in/latest and data-in/snapshots side by side).
const SNAPS = process.env.CONTRACT_SNAPSHOTS_DIR
  ? (isAbsolute(process.env.CONTRACT_SNAPSHOTS_DIR) ? process.env.CONTRACT_SNAPSHOTS_DIR : resolve(process.cwd(), process.env.CONTRACT_SNAPSHOTS_DIR))
  : join(DATA, 'snapshots');
// Snapshot files are stored gzipped (`.json.gz`); everything else is plain JSON.
const read = (rel: string) => {
  const buf = readFileSync(rel.startsWith('snapshots/') ? join(SNAPS, rel.slice('snapshots/'.length)) : join(DATA, rel));
  return JSON.parse((rel.endsWith('.gz') ? gunzipSync(buf) : buf).toString('utf8'));
};

// A tiny schema language: a check is a typeof name, 'nullable:<check>', 'array:<check>', an
// enum written as 'enum:<json array>' (strict, so 1 is not "1"), a fixed-length tuple 'tuple:n', or a nested schema object.
type Check = string | Schema;
type Schema = { [key: string]: Check };
type Shape<T> = { [K in keyof T]-?: Check };

function matches(value: unknown, check: Check, path: string, errors: string[]): void {
  if (typeof check === 'object') {
    if (typeof value !== 'object' || value === null || Array.isArray(value)) {
      errors.push(`${path}: expected object`);
      return;
    }
    const rec = value as Record<string, unknown>;
    for (const key of Object.keys(check)) {
      if (!(key in rec)) errors.push(`${path}.${key}: missing`);
      else matches(rec[key], check[key], `${path}.${key}`, errors);
    }
    for (const key of Object.keys(rec)) {
      if (!(key in check)) errors.push(`${path}.${key}: unexpected key`);
    }
    return;
  }
  if (check.startsWith('nullable:')) {
    if (value !== null) matches(value, check.slice(9), path, errors);
  } else if (check.startsWith('array:')) {
    if (!Array.isArray(value)) errors.push(`${path}: expected array`);
    else value.forEach((v, i) => matches(v, check.slice(6), `${path}[${i}]`, errors));
  } else if (check.startsWith('enum:')) {
    const allowed = JSON.parse(check.slice(5)) as unknown[];
    if (!allowed.includes(value)) errors.push(`${path}: bad enum ${JSON.stringify(value)}`);
  } else if (check.startsWith('tuple:')) {
    const n = Number(check.slice(6));
    if (!Array.isArray(value) || value.length !== n || value.some((v) => typeof v !== 'number')) {
      errors.push(`${path}: expected ${n} numbers`);
    }
  } else if (check === 'record:number') {
    if (typeof value !== 'object' || value === null || Array.isArray(value)) errors.push(`${path}: expected record`);
    else for (const [k, v] of Object.entries(value)) matches(v, 'number', `${path}.${k}`, errors);
  } else if (check === 'record:string') {
    if (typeof value !== 'object' || value === null || Array.isArray(value)) errors.push(`${path}: expected record`);
    else for (const [k, v] of Object.entries(value)) matches(v, 'string', `${path}.${k}`, errors);
  } else if (typeof value !== check) {
    errors.push(`${path}: expected ${check}, got ${typeof value}`);
  }
}

function validate(value: unknown, schema: Schema, path: string): string[] {
  const errors: string[] = [];
  matches(value, schema, path, errors);
  return errors;
}

const tier = 'enum:[1,2]';
const bbox = 'tuple:4';
const totals: Shape<AreaTotals> = {
  crashes_5y: 'number', injured_5y: 'number', killed_5y: 'number',
  lane_at_crash_5y: {
    none: 'number', paint: 'number', sharrow: 'number', protected: 'number', unknown: 'number',
  },
  ranked_blocks: 'number', tier1_blocks: 'number', tier2_blocks: 'number',
  stretches: 'number', shared_stretches: 'number',
};
const metaShape: Shape<Meta> = {
  data_date: 'string', built_at: 'string', window_start: 'string', recent_start: 'string',
  sources: 'record:string', counts: 'record:number', citywide: totals, unassigned: totals,
};
const areaShape: Shape<Area> = {
  kind: 'enum:["cb","cd"]', id: 'string', name: 'string', borough: 'nullable:string', bbox, totals,
};
const blockShape: Shape<Block> = {
  segmentid: 'string', street: 'string', borough: 'nullable:string',
  current_facility: 'enum:["none","paint","sharrow","protected"]', tier: `nullable:${tier}`,
  rank: 'nullable:number', rank_in_tier: 'nullable:number', score: 'number', crashes_5y: 'number',
  injured_5y: 'number', killed_5y: 'number', crashes_no_lane_5y: 'number',
  crashes_all_years: 'number', last_crash_date: 'nullable:string', posted_speed: 'nullable:number',
  travel_lanes: 'nullable:number', cb: 'nullable:string', cd: 'nullable:string',
  area_by_nearest: 'boolean', stretch_id: 'nullable:string', mid: 'tuple:2',
};
const stretchShape: Shape<Stretch> = {
  stretch_id: 'string', street: 'string', borough: 'string', tier, rank: 'number',
  from_street: 'nullable:string', to_street: 'nullable:string', blocks: 'number',
  segmentids: 'array:string', gap_segmentids: 'array:string', score: 'number',
  crashes_5y: 'number', injured_5y: 'number', killed_5y: 'number', crashes_no_lane_5y: 'number',
  last_crash_date: 'nullable:string', cbs: 'array:string', cds: 'array:string', bbox,
};
const streetShape: Shape<Street> = {
  street_key: 'string', street: 'string', borough: 'string', tier, rank: 'number', score: 'number',
  blocks: 'number', crashes_5y: 'number', injured_5y: 'number', killed_5y: 'number',
  stretch_ids: 'array:string', cbs: 'array:string', cds: 'array:string',
};
const indexShape: Shape<SnapshotIndex> = { latest: 'string', dates: 'array:string' };

const REQUIRED_COUNTS = [
  'candidate_crashes', 'bike_riders', 'riders_killed', 'bike_crashes', 'match_high', 'match_medium',
  'match_low', 'unmatched_no_coords', 'unmatched_too_far', 'lane_none', 'lane_paint', 'lane_sharrow',
  'lane_protected', 'lane_unknown', 'blocks', 'ranked_blocks', 'tier1_blocks', 'tier2_blocks',
  'stretches', 'rows_crashes', 'rows_persons', 'rows_vehicles', 'rows_routes', 'rows_council',
  'rows_community', 'rows_lion',
];

/** One CSV line, honouring double-quoted fields (street names may contain commas). */
function parseCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = '';
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; } else if (ch === '"') quoted = false; else cur += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ',') { out.push(cur); cur = ''; } else cur += ch;
  }
  out.push(cur);
  return out;
}

/** All [lon, lat] points of a Polygon or MultiPolygon coordinate array. */
function points(coords: unknown): number[][] {
  if (Array.isArray(coords) && typeof coords[0] === 'number') return [coords as number[]];
  return (coords as unknown[]).flatMap(points);
}

/** Validate one snapshot-shaped directory (the live data and every snapshot share the shapes). */
function checkSet(dir: string, ext = ''): void {
  const meta = read(`${dir}meta.json${ext}`);
  expect(validate(meta, metaShape, 'meta')).toEqual([]);
  for (const key of REQUIRED_COUNTS) expect(meta.counts, `counts.${key}`).toHaveProperty(key);

  const areas = read(`${dir}areas.json${ext}`) as Areas;
  expect(Object.keys(areas).sort()).toEqual(['cb', 'cd']);
  for (const kind of ['cb', 'cd'] as const) {
    expect(areas[kind].length).toBeGreaterThan(0);
    areas[kind].forEach((a, i) => expect(validate(a, areaShape, `areas.${kind}[${i}]`)).toEqual([]));
  }

  const blocks = read(`${dir}blocks.json${ext}`) as Block[];
  const stretches = read(`${dir}stretches.json${ext}`) as Stretch[];
  const streets = read(`${dir}streets.json${ext}`) as Street[];
  expect(blocks.length).toBeGreaterThan(0);
  blocks.forEach((b, i) => expect(validate(b, blockShape, `blocks[${i}]`)).toEqual([]));
  stretches.forEach((s, i) => expect(validate(s, stretchShape, `stretches[${i}]`)).toEqual([]));
  streets.forEach((s, i) => expect(validate(s, streetShape, `streets[${i}]`)).toEqual([]));
  // street_key is borough|normalized name (no spaces)|tier
  for (const s of streets) expect(s.street_key, s.street_key).toMatch(/^[^|]+\|[^| ]+\|[12]$/);

  // Scores and scored counts recompute from the crash export (the 2026-11-23 snapshot uses the
  // same rows up to its own data date).
  const rows = readFileSync(join(DATA, 'crashes/citywide.csv'), 'utf8').trim().split('\n').slice(1)
    .map(parseCsvLine)
    .map((c) => ({ date: c[1], seg: c[8], conf: c[9], lane: c[10], inj: Number(c[11]), killed: Number(c[12]) }))
    .filter((r) => r.date >= meta.window_start && r.date <= meta.data_date)
    .filter((r) => ['high', 'medium'].includes(r.conf) && ['none', 'paint', 'sharrow'].includes(r.lane));
  const rowsBySeg = new Map<string, typeof rows>();
  for (const r of rows) rowsBySeg.set(r.seg, [...(rowsBySeg.get(r.seg) ?? []), r]);
  for (const b of blocks) {
    const rs = rowsBySeg.get(b.segmentid) ?? [];
    const score = rs.reduce((t, r) => t + (r.killed * 10 + r.inj) * (r.date >= meta.recent_start ? 1 : 0.5), 0);
    expect(Math.abs(b.score - score), `${b.segmentid} score ${b.score} vs ${score}`).toBeLessThan(1e-9);
    expect(b.crashes_5y, `${b.segmentid} crashes_5y`).toBe(rs.length);
    expect(b.injured_5y, `${b.segmentid} injured_5y`).toBe(rs.reduce((t, r) => t + r.inj, 0));
    expect(b.killed_5y, `${b.segmentid} killed_5y`).toBe(rs.reduce((t, r) => t + r.killed, 0));
    expect(b.crashes_no_lane_5y, `${b.segmentid} no_lane`).toBe(rs.filter((r) => r.lane === 'none').length);
  }

  // tier and rank_in_tier are null exactly when the block is not ranked.
  for (const b of blocks) {
    expect(b.tier === null, `${b.segmentid} tier null iff unranked`).toBe(b.rank === null);
    expect(b.rank_in_tier === null, `${b.segmentid} rank_in_tier null iff unranked`).toBe(b.rank === null);
  }

  // Sort orders promised by the contract: ranked first by rank, unranked last.
  const ranks = blocks.map((b) => b.rank);
  const ranked = ranks.filter((r): r is number => r !== null);
  expect(ranks.slice(0, ranked.length)).toEqual(ranked);
  expect(ranked).toEqual([...ranked].sort((a, b) => a - b));
  expect(stretches.map((s) => s.rank)).toEqual(stretches.map((s) => s.rank).sort((a, b) => a - b));
  expect(streets.map((s) => s.rank)).toEqual(streets.map((s) => s.rank).sort((a, b) => a - b));

  // Cross references: stretches point at real blocks, streets at real stretches.
  const bySeg = new Map(blocks.map((b) => [b.segmentid, b]));
  for (const s of stretches) {
    for (const id of s.segmentids) expect(bySeg.get(id)?.stretch_id, id).toBe(s.stretch_id);
    for (const id of [...s.segmentids, ...s.gap_segmentids]) expect(bySeg.has(id), `${id} in blocks.json`).toBe(true);
    for (const id of s.gap_segmentids) expect(s.segmentids).toContain(id);
  }
  const stretchIds = new Set(stretches.map((s) => s.stretch_id));
  for (const st of streets) for (const id of st.stretch_ids) expect(stretchIds.has(id)).toBe(true);
}

describe('fixtures match contract', () => {
  it('live data set', () => checkSet(''));

  // Snapshots are written by a later pipeline step; a custom CONTRACT_DIR may not have them yet.
  it.skipIf(!existsSync(join(SNAPS, 'index.json')))('snapshots', () => {
    const index = read('snapshots/index.json') as SnapshotIndex;
    expect(validate(index, indexShape, 'index')).toEqual([]);
    expect(index.dates[0]).toBe(index.latest);
    expect(index.dates).toEqual([...index.dates].sort().reverse());
    expect(read('meta.json').data_date).toBe(index.latest);
    for (const date of index.dates) {
      checkSet(`snapshots/${date}/`, '.gz');
      expect(read(`snapshots/${date}/meta.json.gz`).data_date).toBe(date);
    }
  });

  it('area geometry and crash export', () => {
    const geo = read('areas.geojson');
    expect(geo.type).toBe('FeatureCollection');
    const areas = read('areas.json') as Areas;
    expect(geo.features.length).toBe(areas.cb.length + areas.cd.length);
    // Area.bbox equals the bounds of the area's polygon.
    for (const f of geo.features) {
      const pts = points(f.geometry.coordinates); // Polygon or MultiPolygon
      const xs = pts.map((p) => p[0]);
      const ys = pts.map((p) => p[1]);
      const area = areas[f.properties.kind as 'cb' | 'cd'].find((a) => a.id === f.properties.id);
      expect(area?.bbox, `${f.properties.kind}-${f.properties.id}`).toEqual([
        Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys),
      ]);
    }
    expect(Object.keys(geo.features[0].properties).sort()).toEqual(['id', 'kind', 'name']);
    const header = readFileSync(join(DATA, 'crashes/cb-309.csv'), 'utf8').split('\n')[0];
    expect(header).toBe(
      'collision_id,crash_date,crash_time,latitude,longitude,on_street_name,cross_street_name,'
      + 'matched_street,segmentid,match_confidence,lane_at_crash,riders_injured,riders_killed,bike_types',
    );
  });
});
