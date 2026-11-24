import type { AreaKind, Block, Stretch, Street } from './types';

export interface Ranked<T> { item: T; areaRank: number; }
type Kind = AreaKind | 'citywide';

const areasOf = (s: { cbs: string[]; cds: string[] }, kind: AreaKind) => (kind === 'cb' ? s.cbs : s.cds);
const effKind = (k: Kind): AreaKind => (k === 'citywide' ? 'cb' : k);

/** Stable sort by tier (1 then 2), preserving input (citywide rank) order inside a tier, then number from 1. */
function number<T extends { tier: 1 | 2 | null }>(items: T[]): Ranked<T>[] {
  const ordered = [...items.filter((x) => x.tier === 1), ...items.filter((x) => x.tier === 2)];
  return ordered.map((item, i) => ({ item, areaRank: i + 1 }));
}

export function isShared(s: Stretch, kind: AreaKind): boolean {
  return areasOf(s, kind).length >= 2;
}

export function otherAreas(s: Stretch, kind: AreaKind, id: string): string[] {
  return areasOf(s, kind).filter((a) => a !== id);
}

export function stretchesForArea(s: Stretch[], kind: Kind, id: string | null,
  opts: { sharedOnly: boolean }): Ranked<Stretch>[] {
  let list = s;
  if (kind !== 'citywide') {
    if (!id) return [];
    list = list.filter((x) => areasOf(x, kind).includes(id));
  }
  if (opts.sharedOnly) list = list.filter((x) => isShared(x, effKind(kind)));
  return number(list);
}

export function blocksForArea(b: Block[], kind: Kind, id: string | null): Ranked<Block>[] {
  let list = b.filter((x) => x.rank !== null);
  if (kind !== 'citywide') {
    if (!id) return [];
    list = list.filter((x) => (kind === 'cb' ? x.cb : x.cd) === id);
  }
  return number(list);
}

export function streetsForArea(s: Street[], kind: Kind, id: string | null): Ranked<Street>[] {
  let list = s;
  if (kind !== 'citywide') {
    if (!id) return [];
    list = list.filter((x) => areasOf(x, kind).includes(id));
  }
  return number(list);
}
