import type { Area, AreaKind } from './types';

const INT = new Intl.NumberFormat('en-US');
export const fmtInt = (n: number): string => INT.format(n);
export const fmtScore = (n: number): string => n.toFixed(1);

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
/** '2026-11-24' -> 'Nov 24, 2026' (no timezone conversion). */
export function fmtDate(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number);
  if (!y || !m || !d) return iso;
  return `${MONTHS[m - 1]} ${d}, ${y}`;
}

export const areaLabel = (a: Area): string => a.name;

/** Short tag: CB 9 (board ids are borough digit + 2-digit number) or CD 40. */
export function areaTag(kind: AreaKind, id: string): string {
  return kind === 'cb' ? `CB ${Number(id.slice(1))}` : `CD ${id}`;
}

/** 'EAST 1ST STREET' -> 'East 1st Street'. */
export function titleCase(s: string): string {
  return s.toLowerCase().split(' ').map((w) => (/^\d/.test(w) ? w : w.charAt(0).toUpperCase() + w.slice(1))).join(' ');
}

/** Block ends as plain text; a missing end reads as "continues". */
export function fmtEnds(from: string | null, to: string | null): string {
  const f = from ? titleCase(from) : 'continues';
  const t = to ? titleCase(to) : 'continues';
  return `${f} → ${t}`;
}

/** Sort by borough, then number. */
export function sortAreas(areas: Area[]): Area[] {
  return [...areas].sort((a, b) => (a.borough ?? '').localeCompare(b.borough ?? '') || Number(a.id) - Number(b.id));
}

/** Every typed word must start a word in the name, or equal the id. "brooklyn 9", "9", "40". */
export function matchArea(areas: Area[], query: string): Area[] {
  const tokens = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (!tokens.length) return areas;
  return areas.filter((a) => {
    const words = a.name.toLowerCase().split(/\s+/);
    return tokens.every((t) => a.id === t || words.some((w) => w.startsWith(t)));
  });
}

const BORO = ['', 'Mn', 'Bx', 'Bk', 'Qn', 'SI'];
/** Board tag with the borough, for citywide lists: Bk CB 9. */
export const areaTagCity = (id: string): string => `${BORO[Number(id[0])] ?? '?'} ${areaTag('cb', id)}`;
