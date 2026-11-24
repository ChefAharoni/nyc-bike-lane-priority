import type { AreaKind } from './types';

export interface Route {
  page: 'map' | 'about';
  kind: AreaKind | 'citywide';
  areaId: string | null;
  date: string | null;
  view: 'streets' | 'blocks';
  selection: { type: 'stretch' | 'block'; id: string } | null;
}

const DATE = /^\d{4}-\d{2}-\d{2}$/;
const ID = /^[A-Za-z0-9_-]+$/;

export const defaultRoute = (): Route => ({
  page: 'map', kind: 'citywide', areaId: null, date: null, view: 'streets', selection: null,
});

function decode(s: string): string {
  try { return decodeURIComponent(s); } catch { return s; }
}

/** What parseRouteChecked found wrong with an address: a link it could not read, or a date it dropped. */
export type RouteProblem = 'link' | 'date' | null;

/** Parses a location hash into a Route. Never throws; anything unrecognised becomes the default. */
export function parseRoute(hash: string): Route {
  return parseRouteChecked(hash).route;
}

/** Like parseRoute, but also says when the address was not understood (so the page can tell the reader). */
export function parseRouteChecked(hash: string): { route: Route; problem: RouteProblem } {
  const r = defaultRoute();
  let problem: RouteProblem = null;
  const blank = /^#?\/?$/.test(hash);
  try {
    const parts = hash.replace(/^#\/?/, '').split('/').map(decode);
    const head = parts[0] ?? '';
    if (head === 'about') return { route: { ...r, page: 'about' }, problem };
    let rest: string[];
    const [first, dateRaw] = head.split('@');
    if (first === 'citywide') {
      rest = parts.slice(1);
    } else if ((first === 'cb' || first === 'cd')) {
      // The area id (with optional @date) is the second segment.
      const [id, d] = (parts[1] ?? '').split('@');
      if (!ID.test(id)) return { route: r, problem: 'link' };
      r.kind = first;
      r.areaId = id;
      if (d && DATE.test(d)) r.date = d;
      else if (d !== undefined) problem = 'date';
      rest = parts.slice(2);
    } else {
      return { route: r, problem: blank ? null : 'link' };
    }
    if (first === 'citywide' && dateRaw !== undefined) {
      if (DATE.test(dateRaw)) r.date = dateRaw; else problem = 'date';
    }
    let i = 0;
    if (rest[i] === 'blocks') { r.view = 'blocks'; i++; }
    const t = rest[i];
    const id = rest[i + 1];
    if ((t === 's' || t === 'b') && id && ID.test(id)) {
      r.selection = { type: t === 's' ? 'stretch' : 'block', id };
    }
  } catch {
    return { route: defaultRoute(), problem: 'link' };
  }
  return { route: r, problem };
}

export function formatRoute(r: Route): string {
  if (r.page === 'about') return '#/about';
  const at = r.date ? `@${r.date}` : '';
  let h = r.kind === 'citywide' || !r.areaId ? `#/citywide${at}` : `#/${r.kind}/${r.areaId}${at}`;
  if (r.view === 'blocks') h += '/blocks';
  if (r.selection) h += `/${r.selection.type === 'stretch' ? 's' : 'b'}/${r.selection.id}`;
  return h;
}
