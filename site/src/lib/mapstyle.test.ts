import { describe, expect, it } from 'vitest';
import { areaLabelPoints, layerIds, priorityState } from './mapstyle';
import type { Block, Stretch } from './types';

describe('areaLabelPoints', () => {
  const square = (x0: number, y0: number, s: number): [number, number][] =>
    [[x0, y0], [x0 + s, y0], [x0 + s, y0 + s], [x0, y0 + s], [x0, y0]];
  it('puts one point per area at the centroid, using the largest polygon of a multipolygon', () => {
    const fc = { features: [
      { properties: { kind: 'cb', id: '309', name: 'Brooklyn CB 9' },
        geometry: { type: 'Polygon' as const, coordinates: [square(0, 0, 2)] } },
      { properties: { kind: 'cd', id: '40', name: 'Council District 40' },
        geometry: { type: 'MultiPolygon' as const, coordinates: [[square(10, 10, 1)], [square(20, 20, 4)]] } },
    ] };
    const out = areaLabelPoints(fc);
    expect(out.features).toHaveLength(2);
    expect(out.features[0].geometry.coordinates).toEqual([1, 1]);
    expect(out.features[0].properties.name).toBe('Brooklyn CB 9');
    expect(out.features[1].geometry.coordinates).toEqual([22, 22]);
  });
});

const blk = (id: string, o: Partial<Block> = {}): Block => ({
  segmentid: id, street: 'MAIN ST', borough: 'Manhattan', current_facility: 'none', tier: null, rank: null,
  rank_in_tier: null, score: 0, crashes_5y: 0, injured_5y: 0, killed_5y: 0, crashes_no_lane_5y: 0,
  crashes_all_years: 0, last_crash_date: null, posted_speed: null, travel_lanes: null, cb: '309', cd: '7',
  area_by_nearest: false, stretch_id: null, mid: [0, 0], ...o,
});
const str = (id: string, tier: 1 | 2, segs: string[], gaps: string[] = []): Stretch => ({
  stretch_id: id, street: 'MAIN ST', borough: 'Manhattan', tier, rank: 1, from_street: null, to_street: null,
  blocks: segs.length, segmentids: segs, gap_segmentids: gaps, score: 1, crashes_5y: 1, injured_5y: 0,
  killed_5y: 0, crashes_no_lane_5y: 1, last_crash_date: null, cbs: ['309'], cds: ['7'], bbox: [0, 0, 1, 1],
});
const blocks = [
  blk('a', { tier: 1, rank: 1, stretch_id: 's1' }), blk('b', { tier: 1, rank: 2, stretch_id: 's1' }),
  blk('gap', { tier: null, cb: '310' }), blk('c', { tier: 2, rank: 3, stretch_id: 's2', cb: '310' }),
  blk('quiet', { tier: null }),
];
const stretches = [str('s1', 1, ['a', 'b'], ['gap']), str('s2', 2, ['c'])];

describe('priorityState', () => {
  it('streets view gives gap blocks the stretch tier', () => {
    const m = priorityState(blocks, stretches, 'streets', 'cb', '309');
    expect(m.get('gap')?.tier).toBe(1);
    expect(m.get('a')?.tier).toBe(1);
    expect(m.get('c')?.tier).toBe(2);
    expect(m.has('quiet')).toBe(false);
  });
  it('blocks view marks only ranked blocks', () => {
    const m = priorityState(blocks, stretches, 'blocks', 'cb', '309');
    expect([...m.keys()].sort()).toEqual(['a', 'b', 'c']);
  });
  it('blocks view skips an unranked block even if it carries a tier', () => {
    const m = priorityState([...blocks, blk('stale', { tier: 1, rank: null })], stretches, 'blocks', 'cb', '309');
    expect(m.has('stale')).toBe(false);
  });
  it('highlights every stretch of a whole street, in streets view only', () => {
    const m = priorityState(blocks, stretches, 'streets', 'cb', '309', null, ['s1']);
    expect(['a', 'b', 'gap'].every((id) => m.get(id)?.selected)).toBe(true);
    expect(m.get('c')?.selected).toBe(false);
    const none = priorityState(blocks, stretches, 'streets', 'cb', '309', null, []);
    expect([...none.values()].some((v) => v.selected)).toBe(false);
    const both = priorityState(blocks, stretches, 'streets', 'cb', '309', { type: 'stretch', id: 's2' }, ['s1']);
    expect(both.get('c')?.selected && both.get('a')?.selected).toBe(true);
    const bv = priorityState(blocks, stretches, 'blocks', 'cb', '309', null, ['s1']);
    expect([...bv.values()].some((v) => v.selected)).toBe(false);
  });
  it('inArea is true only for blocks of the area in cb mode', () => {
    const m = priorityState(blocks, stretches, 'streets', 'cb', '309');
    expect(m.get('a')?.inArea).toBe(true);
    expect(m.get('gap')?.inArea).toBe(false);
    expect(m.get('c')?.inArea).toBe(false);
    const cd = priorityState(blocks, stretches, 'blocks', 'cd', '7');
    expect(cd.get('c')?.inArea).toBe(true);
  });
  it('citywide (no area) puts everything in area', () => {
    const m = priorityState(blocks, stretches, 'streets', 'cb', null);
    expect([...m.values()].every((v) => v.inArea)).toBe(true);
  });
  it('selection flags only the selected stretch blocks, or the selected block', () => {
    const m = priorityState(blocks, stretches, 'streets', 'cb', '309', { type: 'stretch', id: 's1' });
    expect(['a', 'b', 'gap'].every((k) => m.get(k)?.selected)).toBe(true);
    expect(m.get('c')?.selected).toBe(false);
    const b = priorityState(blocks, stretches, 'blocks', 'cb', '309', { type: 'block', id: 'b' });
    expect(b.get('b')?.selected).toBe(true);
    expect(b.get('a')?.selected).toBe(false);
  });
  it('blocks view with a selected stretch highlights its ranked blocks', () => {
    const m = priorityState(blocks, stretches, 'blocks', 'cb', null, { type: 'stretch', id: 's1' });
    expect(m.get('a')?.selected && m.get('b')?.selected).toBe(true);
    expect(m.get('c')?.selected).toBe(false);
  });
  it('exposes layer ids', () => {
    expect(layerIds.priority).toBeTruthy();
    expect(new Set(Object.values(layerIds)).size).toBe(Object.keys(layerIds).length);
  });
});
