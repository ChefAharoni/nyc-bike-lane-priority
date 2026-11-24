export type Facility = 'none' | 'paint' | 'sharrow' | 'protected';
export type LaneAtCrash = Facility | 'unknown';
export type AreaKind = 'cb' | 'cd';
export interface AreaTotals { crashes_5y: number; injured_5y: number; killed_5y: number;
  lane_at_crash_5y: Record<LaneAtCrash, number>; ranked_blocks: number; tier1_blocks: number;
  tier2_blocks: number; stretches: number; shared_stretches: number; }
export interface Meta { data_date: string; built_at: string; window_start: string; recent_start: string;
  sources: Record<string, string>; counts: Record<string, number>; citywide: AreaTotals;
  unassigned: AreaTotals; }
export interface Area { kind: AreaKind; id: string; name: string; borough: string | null;
  bbox: [number, number, number, number]; totals: AreaTotals; }
export interface Areas { cb: Area[]; cd: Area[]; }
export interface Block { segmentid: string; street: string; borough: string | null;
  current_facility: Facility; tier: 1 | 2 | null; rank: number | null; rank_in_tier: number | null;
  score: number; crashes_5y: number; injured_5y: number; killed_5y: number; crashes_no_lane_5y: number;
  crashes_all_years: number; last_crash_date: string | null; posted_speed: number | null;
  travel_lanes: number | null; cb: string | null; cd: string | null; area_by_nearest: boolean;
  stretch_id: string | null; mid: [number, number]; }
export interface Stretch { stretch_id: string; street: string; borough: string; tier: 1 | 2; rank: number;
  from_street: string | null; to_street: string | null; blocks: number; segmentids: string[];
  gap_segmentids: string[]; score: number; crashes_5y: number; injured_5y: number; killed_5y: number;
  crashes_no_lane_5y: number; last_crash_date: string | null; cbs: string[]; cds: string[];
  bbox: [number, number, number, number]; }
export interface Street { street_key: string; street: string; borough: string; tier: 1 | 2; rank: number;
  score: number; blocks: number; crashes_5y: number; injured_5y: number; killed_5y: number;
  stretch_ids: string[]; cbs: string[]; cds: string[]; }
export interface SnapshotIndex { latest: string; dates: string[]; } // dates newest first
