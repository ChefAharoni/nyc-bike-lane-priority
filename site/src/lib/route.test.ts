import { describe, expect, it } from 'vitest';
import { formatRoute, parseRoute, parseRouteChecked } from './route';

describe('route', () => {
  const forms = [
    '#/about',
    '#/citywide',
    '#/cb/309',
    '#/cd/40',
    '#/cb/309@2026-11-24',
    '#/cb/309/blocks',
    '#/cb/309@2026-11-24/blocks/b/0145699',
    '#/cb/309/s/S0145699',
    '#/citywide/blocks',
  ];
  for (const f of forms) it(`round-trips ${f}`, () => expect(formatRoute(parseRoute(f))).toBe(f));

  it('defaults to citywide streets', () => {
    for (const h of ['', '#', '#/', '#/garbage/here', '#/cb', '#/cb/']) {
      expect(parseRoute(h)).toEqual({ page: 'map', kind: 'citywide', areaId: null, date: null, view: 'streets', selection: null });
    }
  });
  it('ignores a bad date', () => expect(parseRoute('#/cb/309@garbage').date).toBeNull());
  it('unknown kind is citywide', () => {
    const r = parseRoute('#/xx/1');
    expect(r.kind).toBe('citywide');
    expect(r.areaId).toBeNull();
  });
  it('parses a stretch selection', () => {
    const r = parseRoute('#/cb/309/s/S0145699');
    expect(r.selection).toEqual({ type: 'stretch', id: 'S0145699' });
    expect(r.areaId).toBe('309');
  });
  it('parses blocks with a block selection and date', () => {
    const r = parseRoute('#/cd/40@2026-11-24/blocks/b/0145699');
    expect(r).toMatchObject({ kind: 'cd', areaId: '40', date: '2026-11-24', view: 'blocks', selection: { type: 'block', id: '0145699' } });
  });
  it('never throws on odd input', () => {
    for (const h of ['#/%E0%A4%A', '#/cb/309/s', '#/cb/309/s/', '#///', '#/cb/3 09']) expect(() => parseRoute(h)).not.toThrow();
  });

  describe('parseRouteChecked flags', () => {
    it('is quiet for good and blank addresses', () => {
      for (const h of ['', '#', '#/', '#/about', '#/citywide', '#/cb/309@2026-11-24/blocks']) {
        expect(parseRouteChecked(h).problem).toBeNull();
      }
    });
    it('flags unreadable links', () => {
      for (const h of ['#/xx/1', '#/cb/!!', '#/cb', '#/garbage/here']) {
        expect(parseRouteChecked(h).problem).toBe('link');
        expect(parseRouteChecked(h).route.kind).toBe('citywide');
      }
    });
    it('flags a dropped date but keeps the area', () => {
      const c = parseRouteChecked('#/cb/309@garbage');
      expect(c.problem).toBe('date');
      expect(c.route).toMatchObject({ kind: 'cb', areaId: '309', date: null });
      expect(parseRouteChecked('#/citywide@nope').problem).toBe('date');
    });
  });
});
