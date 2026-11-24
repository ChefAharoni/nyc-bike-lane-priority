import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import type { DataBundle } from './load';
import { buildReport, endsProse } from './report';
import { stretchesForArea } from './rank';
import { defaultRoute, type Route } from './route';

const D = join(dirname(fileURLToPath(import.meta.url)), '../../fixtures/data');
const j = <T>(f: string): T => JSON.parse(readFileSync(join(D, f), 'utf8'));
const bundle: DataBundle = {
  meta: j('meta.json'), areas: j('areas.json'), blocks: j('blocks.json'), stretches: j('stretches.json'),
  streets: j('streets.json'), index: { latest: '2026-11-24', dates: ['2026-11-24'] }, date: null, notice: null,
};
const cb = (id: string): Route => ({ ...defaultRoute(), kind: 'cb', areaId: id });
const HREF = 'https://example.org/site/#/cb/309';

describe('buildReport', () => {
  it('DOT summary for CB 9 names the shared stretch and the boards it crosses', () => {
    const r = buildReport('dot', bundle, cb('309'), HREF);
    expect(r.kind).toBe('dot');
    expect(r.areaName).toBe('Brooklyn CB 9');
    expect(r.asks.length).toBe(1);
    expect(r.asks[0]).toContain('Protected bike lane on Empire Boulevard, Washington Avenue to Schenectady Avenue');
    expect(r.asks[0]).toContain('crosses CB 8, CB 17');
    expect(r.shared.map((s) => s.stretch.stretch_id)).toEqual(['S0100001']);
    expect(r.shared[0].others).toEqual(['CB 8', 'CB 17']);
    expect(r.topStretches.every((x) => x.item.tier === 1)).toBe(true);
    expect(r.topStreets.every((x) => x.item.tier === 1)).toBe(true);
    expect(r.window).toBe('2021-11-01 to 2026-11-24');
    expect(r.dataDate).toBe('2026-11-24');
  });
  it('Board view lists the whole area list', () => {
    const r = buildReport('board', bundle, cb('309'), HREF);
    expect(r.fullList.length).toBe(stretchesForArea(bundle.stretches, 'cb', '309', { sharedOnly: false }).length);
    expect(r.fullList.some((x) => x.item.tier === 2)).toBe(true);
  });
  it('adds @date to the permalink only when absent', () => {
    expect(buildReport('dot', bundle, cb('309'), HREF).permalink).toBe('https://example.org/site/#/cb/309@2026-11-24');
    expect(buildReport('dot', bundle, cb('309'), 'https://example.org/site/#/cb/309@2026-11-20').permalink)
      .toBe('https://example.org/site/#/cb/309@2026-11-20');
    expect(buildReport('dot', bundle, defaultRoute(), 'https://example.org/site/').permalink)
      .toBe('https://example.org/site/#/citywide@2026-11-24');
  });
  it('methods are plain words with numbers from meta and no em dashes', () => {
    const m = buildReport('dot', bundle, cb('309'), HREF).methods;
    expect(m).toContain('2021-11-01');
    expect(m).toContain('2026-11-24');
    expect(m).toContain('Tier 1');
    expect(m).toContain('Tier 2');
    expect(m).not.toContain('—');
  });
  it('an empty area gives empty lists and does not throw', () => {
    const r = buildReport('board', bundle, cb('999'), HREF);
    expect(r.fullList).toEqual([]);
    expect(r.topStretches).toEqual([]);
    expect(r.asks).toEqual([]);
    expect(r.shared).toEqual([]);
    expect(r.totals.crashes_5y).toBeGreaterThanOrEqual(0);
  });
  it('citywide and council districts work', () => {
    expect(buildReport('dot', bundle, defaultRoute(), HREF).areaName).toBe('Citywide');
    const cd = buildReport('dot', bundle, { ...defaultRoute(), kind: 'cd', areaId: '40' }, HREF);
    expect(cd.areaName).toBe('Council District 40');
    expect(cd.asks[0]).toContain('crosses Council District 35');
  });
  it('asks say crashes counted', () => {
    expect(buildReport('dot', bundle, cb('309'), HREF).asks[0]).toMatch(/\d+ bike crash(es)? counted and \d+ deaths? in 5 years/);
    expect(buildReport('dot', bundle, cb('309'), HREF).methods).toContain('Crashes counted');
  });
  it('citywide qualifies board tags with the borough and caps the board list', () => {
    const r = buildReport('board', bundle, defaultRoute(), HREF);
    expect(r.citywide).toBe(true);
    expect(r.shared[0].others.every((o) => /^(Mn|Bx|Bk|Qn|SI) CB \d+$/.test(o))).toBe(true);
    expect(r.fullList.length).toBeLessThanOrEqual(200);
    const big = { ...bundle, stretches: Array.from({ length: 250 }, (_, i) => ({ ...bundle.stretches[0], stretch_id: 'X' + i })) };
    const c = buildReport('board', big, defaultRoute(), HREF);
    expect(c.fullList.length).toBe(200);
    expect(c.listNote).toContain('Showing the first 200 of 250 stretches. Download the Stretches CSV for the full list.');
  });
});

describe('task 16 review leftovers', () => {
  it('counted note uses the confident-match definition', () => {
    const m = buildReport('dot', bundle, cb('309'), HREF).methods;
    expect(m).toContain('Crashes counted: bike crashes in the last 5 years matched to a street block with confidence, where the lane at the time was none, painted or shared. These drive the score.');
  });
  it('citywide DOT summary caps the shared list at 25 with a note', () => {
    const base = bundle.stretches.find((x) => x.cbs.length >= 2)!;
    const many = Array.from({ length: 40 }, (_, i) => ({ ...base, stretch_id: 'Y' + i, rank: i + 1 }));
    const big: DataBundle = { ...bundle, stretches: many,
      meta: { ...bundle.meta, citywide: { ...bundle.meta.citywide, shared_stretches: 40 } } };
    const r = buildReport('dot', big, defaultRoute(), HREF);
    expect(r.shared.length).toBe(25);
    expect(r.sharedNote).toBe('Showing 25 of 40 shared stretches. Download the Stretches CSV for the full list.');
    expect(buildReport('dot', bundle, cb('309'), HREF).sharedNote).toBeNull();
  });
  it('asks do not carry a stray replace artifact', () => {
    expect(buildReport('dot', bundle, cb('309'), HREF).asks[0]).toMatch(/bike crash(es)? counted/);
  });
});

describe('endsProse', () => {
  it('words open ends', () => {
    expect(endsProse('A STREET', 'B STREET')).toBe('A Street to B Street');
    expect(endsProse('A STREET', null)).toBe('A Street onward');
    expect(endsProse(null, 'B STREET')).toBe('up to B Street');
    expect(endsProse(null, null)).toBe('full stretch');
  });
});
