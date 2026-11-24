import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { blocksForArea, isShared, otherAreas, streetsForArea, stretchesForArea } from './rank';
import type { Block, Stretch, Street } from './types';

const D = join(dirname(fileURLToPath(import.meta.url)), '../../fixtures/data');
const j = <T>(f: string): T => JSON.parse(readFileSync(join(D, f), 'utf8'));
const stretches = j<Stretch[]>('stretches.json');
const blocks = j<Block[]>('blocks.json');
const streets = j<Street[]>('streets.json');

describe('stretchesForArea', () => {
  it('restarts areaRank at 1 for the area', () => {
    const r = stretchesForArea(stretches, 'cd', '40', { sharedOnly: false });
    expect(r.map((x) => x.item.stretch_id)).toEqual(['S0100001', 'S0300001']);
    expect(r.map((x) => x.areaRank)).toEqual([1, 2]);
    const r317 = stretchesForArea(stretches, 'cb', '317', { sharedOnly: false });
    expect(r317[0].areaRank).toBe(1);
  });
  it('keeps Tier 1 before Tier 2 and citywide order', () => {
    const r = stretchesForArea(stretches, 'cb', '309', { sharedOnly: false });
    expect(r.map((x) => x.item.tier)).toEqual([1, 1, 1, 2]);
    expect(r.map((x) => x.item.rank)).toEqual([1, 2, 3, 4]);
  });
  it('sharedOnly keeps multi-area stretches and renumbers', () => {
    const r = stretchesForArea(stretches, 'cb', '309', { sharedOnly: true });
    expect(r.map((x) => x.item.stretch_id)).toEqual(['S0100001']);
    expect(r.map((x) => x.areaRank)).toEqual([1]);
    const s2 = stretchesForArea(stretches, 'cd', '40', { sharedOnly: true });
    expect(s2.map((x) => x.areaRank)).toEqual([1]);
  });
  it('citywide returns everything', () => {
    expect(stretchesForArea(stretches, 'citywide', null, { sharedOnly: false })).toHaveLength(stretches.length);
  });
  it('unknown area is empty', () => {
    expect(stretchesForArea(stretches, 'cb', '999', { sharedOnly: false })).toEqual([]);
    expect(blocksForArea(blocks, 'cb', '999')).toEqual([]);
    expect(streetsForArea(streets, 'cb', '999')).toEqual([]);
  });
});

describe('blocks and streets', () => {
  it('blocks are ranked only, tier ordered, renumbered', () => {
    const r = blocksForArea(blocks, 'cb', '309');
    expect(r.length).toBeGreaterThan(0);
    expect(r.every((x) => x.item.tier !== null && x.item.cb === '309')).toBe(true);
    expect(r.map((x) => x.areaRank)).toEqual(r.map((_, i) => i + 1));
    const tiers = r.map((x) => x.item.tier);
    expect(tiers).toEqual([...tiers].sort());
  });
  it('blocks drop unranked rows even with a stale tier', () => {
    const stale = { ...blocks.find((b) => b.rank !== null)!, rank: null, rank_in_tier: null, tier: 1 as const };
    const r = blocksForArea([...blocks, stale], 'citywide', null);
    expect(r.length).toBe(blocks.filter((b) => b.rank !== null).length);
  });
  it('streets filter by area', () => {
    const r = streetsForArea(streets, 'cd', '40');
    expect(r.every((x) => x.item.cds.includes('40'))).toBe(true);
    expect(r[0].areaRank).toBe(1);
  });
});

describe('sharing', () => {
  const empire = stretches.find((s) => s.stretch_id === 'S0100001')!;
  it('isShared', () => {
    expect(isShared(empire, 'cb')).toBe(true);
    expect(isShared(stretches.find((s) => s.stretch_id === 'S0200001')!, 'cb')).toBe(false);
  });
  it('otherAreas', () => expect(otherAreas(empire, 'cb', '309')).toEqual(['308', '317']));
});
