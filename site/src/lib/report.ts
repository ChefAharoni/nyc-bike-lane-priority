import type { DataBundle } from './load';
import { areaTag, areaTagCity, fmtInt, titleCase } from './format';
import { isShared, otherAreas, streetsForArea, stretchesForArea, type Ranked } from './rank';
import { formatRoute, parseRoute, type Route } from './route';
import type { AreaKind, AreaTotals, Stretch, Street } from './types';

export type ReportKind = 'dot' | 'board';

export interface ReportModel {
  kind: ReportKind; areaName: string; dataDate: string; window: string;
  permalink: string; totals: AreaTotals; topStretches: Ranked<Stretch>[]; topStreets: Ranked<Street>[];
  shared: { stretch: Stretch; others: string[] }[]; sharedNote: string | null;
  asks: string[]; fullList: Ranked<Stretch>[]; methods: string; citywide: boolean; listNote: string | null;
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** "CB 8" for boards, "Council District 35" for districts. */
export const reportAreaLabel = (kind: AreaKind, id: string, citywide = false): string =>
  kind === 'cb' ? (citywide ? areaTagCity(id) : areaTag('cb', id)) : `Council District ${id}`;

/** Block ends in a sentence: open ends read "onward", "up to" or "full stretch". */
export function endsProse(from: string | null, to: string | null): string {
  if (from && to) return `${titleCase(from)} to ${titleCase(to)}`;
  if (from) return `${titleCase(from)} onward`;
  if (to) return `up to ${titleCase(to)}`;
  return 'full stretch';
}

export const COUNTED_NOTE = 'Crashes counted: bike crashes in the last 5 years matched to a street block with confidence, where the lane at the time was none, painted or shared. These drive the score.';
const CAP = 200;

function permalink(href: string, date: string): string {
  const i = href.indexOf('#');
  const base = i < 0 ? href : href.slice(0, i);
  const r = parseRoute(i < 0 ? '' : href.slice(i));
  return base + formatRoute({ ...r, date: r.date ?? date });
}

function methods(window: string, dataDate: string, recentStart: string): string {
  return `This report covers ${window}, a five year window that ends on the data date ${dataDate}. ` +
    'A crash counts when a person riding a bicycle, e-bike or e-scooter was injured or killed, as recorded by the police. ' +
    `${COUNTED_NOTE} ` +
    'Each crash is matched to the nearest street block, and the lane status is the bike lane that existed on that block at the time of the crash, not the lane there today. ' +
    `Each block gets a score: every death counts 10, every injury counts 1, crashes since ${recentStart} count in full, and older crashes count half. ` +
    'Neighboring blocks on the same street are joined into stretches. ' +
    'Tier 1 means no bike lane today. Tier 2 means a painted lane or a shared lane marking only. ' +
    'Blocks with a protected lane are not ranked. Tier 1 comes before Tier 2, and inside a tier the highest score comes first.';
}

export function buildReport(kind: ReportKind, bundle: DataBundle, route: Route, href: string): ReportModel {
  const { meta } = bundle;
  const areaKind: AreaKind = route.kind === 'citywide' ? 'cb' : route.kind;
  const area = route.kind !== 'citywide' && route.areaId
    ? bundle.areas[route.kind].find((a) => a.id === route.areaId) ?? null : null;
  const isCity = route.kind === 'citywide';
  const empty = !isCity && !area;
  const areaName = isCity ? 'Citywide' : area ? area.name : `Unknown area ${route.areaId ?? ''}`.trim();
  const totals = area ? area.totals : meta.citywide;
  const id = isCity ? null : route.areaId;

  const all = empty ? [] : stretchesForArea(bundle.stretches, route.kind, id, { sharedOnly: false });
  const tier1 = all.filter((x) => x.item.tier === 1);
  const streets = empty ? [] : streetsForArea(bundle.streets, route.kind, id).filter((x) => x.item.tier === 1);
  const sharedAll = all.filter((x) => isShared(x.item, areaKind)).map((x) => ({
    stretch: x.item,
    others: (id ? otherAreas(x.item, areaKind, id) : (areaKind === 'cb' ? x.item.cbs : x.item.cds))
      .map((a) => reportAreaLabel(areaKind, a, isCity)),
  }));
  const SHARED_CAP = 25;
  const sharedCapped = kind === 'dot' && isCity && sharedAll.length > SHARED_CAP;
  const shared = sharedCapped ? sharedAll.slice(0, SHARED_CAP) : sharedAll;
  const sharedNote = sharedCapped
    ? `Showing ${SHARED_CAP} of ${fmtInt(totals.shared_stretches)} shared stretches. Download the Stretches CSV for the full list.` : null;
  const asks = sharedAll.filter((s) => s.stretch.tier === 1).slice(0, 8).map(({ stretch: s, others }) => {
    const where = s.from_street || s.to_street ? `${titleCase(s.street)}, ${endsProse(s.from_street, s.to_street)} (` : `${titleCase(s.street)} (full stretch; `;
    return `Protected bike lane on ${where}${plural(s.blocks, 'block', 'blocks')}; ` +
      `${plural(s.crashes_5y, 'bike crash', 'bike crashes')} counted and ${plural(s.killed_5y, 'death', 'deaths')} in 5 years; ` +
      `crosses ${others.join(', ')}).`;
  });

  const capped = kind === 'board' && isCity && all.length > CAP;
  const fullList = kind === 'board' ? (capped ? all.slice(0, CAP) : all) : [];
  const listNote = capped ? `Showing the first ${CAP} of ${fmtInt(all.length)} stretches. Download the Stretches CSV for the full list.` : null;
  const window = `${meta.window_start} to ${meta.data_date}`;
  return {
    kind, areaName, dataDate: meta.data_date, window,
    permalink: permalink(href, meta.data_date), totals,
    topStretches: tier1.slice(0, 10), topStreets: streets.slice(0, 5),
    shared, sharedNote, asks, fullList, citywide: isCity, listNote,
    methods: methods(window, meta.data_date, meta.recent_start),
  };
}
