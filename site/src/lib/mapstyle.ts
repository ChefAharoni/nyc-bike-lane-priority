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
} as const;

export const sourceIds = { blocks: 'blocks', lanes: 'lanes', crashes: 'crashes', areas: 'areas' } as const;

export const colors = {
  tier1: '#DC2626', tier2: '#F97316', lane: '#16A34A', area: '#2563EB',
  crash: { none: '#7F1D1D', paint: '#C2410C', sharrow: '#C2410C', protected: '#15803D', unknown: '#6B7280' } as Record<LaneAtCrash, string>,
} as const;

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
