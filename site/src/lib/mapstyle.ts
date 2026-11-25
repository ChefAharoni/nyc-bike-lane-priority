import type { AreaKind, Block, LaneAtCrash, Stretch } from './types';
import type { Route } from './route';

export interface BlockState { tier: 1 | 2; selected: boolean; inArea: boolean; }

export const layerIds = {
  priorityCasing: 'priority-casing',
  priority: 'priority',
  lanesProtected: 'lanes-protected',
  lanesPaint: 'lanes-paint',
  lanesOffstreet: 'lanes-offstreet',
  crashes: 'crashes',
  area: 'area-outline',
  boardLines: 'board-lines',
  boardLabels: 'board-labels',
  districtLines: 'district-lines',
  districtLabels: 'district-labels',
} as const;

export const sourceIds = { blocks: 'blocks', lanes: 'lanes', crashes: 'crashes', areas: 'areas', areaLabels: 'area-labels' } as const;

export const colors = {
  tier1: '#DC2626', tier2: '#F97316', lane: '#16A34A', area: '#2563EB',
  boards: '#475569', districts: '#7C3AED',
  crash: { none: '#7F1D1D', paint: '#C2410C', sharrow: '#C2410C', protected: '#15803D', unknown: '#6B7280' } as Record<LaneAtCrash, string>,
} as const;

type Ring = [number, number][];
interface AreaFeature { properties: { kind: string; id: string; name: string };
  geometry: { type: 'Polygon'; coordinates: Ring[] } | { type: 'MultiPolygon'; coordinates: Ring[][] } }

/** Signed area and centroid of a ring (shoelace formula, planar lon/lat: fine at city scale). */
function ringCentroid(r: Ring): { a: number; x: number; y: number } {
  let a = 0, x = 0, y = 0;
  for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
    const f = r[j][0] * r[i][1] - r[i][0] * r[j][1];
    a += f; x += (r[j][0] + r[i][0]) * f; y += (r[j][1] + r[i][1]) * f;
  }
  return a === 0 ? { a: 0, x: r[0][0], y: r[0][1] } : { a: a / 2, x: x / (3 * a), y: y / (3 * a) };
}

/**
 * One label point per area: the centroid of its largest polygon's outer ring.
 * (Labelling the polygons directly repeats the name once per map tile.)
 */
export function areaLabelPoints(fc: { features: AreaFeature[] }) {
  return {
    type: 'FeatureCollection' as const,
    features: fc.features.map((f) => {
      const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
      const best = polys.map((p) => ringCentroid(p[0])).sort((m, n) => Math.abs(n.a) - Math.abs(m.a))[0];
      return { type: 'Feature' as const, properties: f.properties,
        geometry: { type: 'Point' as const, coordinates: [best.x, best.y] } };
    }),
  };
}

export const laneWords: Record<LaneAtCrash, string> = {
  none: 'No bike lane', paint: 'Painted lane', sharrow: 'Sharrow', protected: 'Protected lane', unknown: 'Unknown',
};

/**
 * Feature state for each priority block, keyed by segmentid.
 * Streets view: every member block of a stretch (gap blocks included) takes the stretch tier.
 * `highlightStretchIds` (a whole street's stretches) are drawn selected, in streets view.
 * Blocks view: only ranked blocks. `inArea` is true for blocks in the current area (all, when no area).
 */
export function priorityState(
  blocks: Block[], stretches: Stretch[], view: 'streets' | 'blocks', kind: AreaKind, areaId: string | null,
  selection: Route['selection'] = null,
  highlightStretchIds: readonly string[] = [],
): Map<string, BlockState> {
  const out = new Map<string, BlockState>();
  const inArea = (b: Block | undefined) =>
    !areaId || (!!b && (kind === 'cb' ? b.cb : b.cd) === areaId);
  if (view === 'blocks') {
    // A selected stretch (the "Show blocks" view) highlights its member blocks.
    const members = selection?.type === 'stretch'
      ? new Set(stretches.find((s) => s.stretch_id === selection.id)?.segmentids ?? []) : null;
    for (const b of blocks) {
      if (b.rank === null || b.tier === null) continue;
      out.set(b.segmentid, {
        tier: b.tier, inArea: inArea(b),
        selected: selection?.type === 'block' ? selection.id === b.segmentid : !!members?.has(b.segmentid),
      });
    }
    return out;
  }
  const hl = new Set(highlightStretchIds);
  const byId = new Map<string, Block>();
  for (const b of blocks) byId.set(b.segmentid, b);
  for (const s of stretches) {
    const selected = (selection?.type === 'stretch' && selection.id === s.stretch_id) || hl.has(s.stretch_id);
    for (const id of [...s.segmentids, ...s.gap_segmentids]) {
      out.set(id, { tier: s.tier, inArea: inArea(byId.get(id)), selected });
    }
  }
  return out;
}
