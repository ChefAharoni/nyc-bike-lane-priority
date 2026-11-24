import type { Block, Stretch } from './types';
import type { Ranked } from './rank';
import { titleCase } from './format';

type Cell = string | number | boolean | null | undefined | (string | number)[];

const NUMERIC = /^-?\d+(\.\d+)?$/;

function cell(v: Cell): string {
  let s = v === null || v === undefined ? '' : Array.isArray(v) ? v.join(';') : String(v);
  // Spreadsheets run text that starts with these characters as a formula, so mark it as plain text.
  if (typeof v !== 'number' && /^[=+\-@\t\r]/.test(s) && !NUMERIC.test(s)) s = `'${s}`;
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** Minimal RFC 4180 reader: quoted fields, doubled quotes, CRLF or LF rows. */
export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let f = '';
  let q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"') { if (text[i + 1] === '"') { f += '"'; i++; } else q = false; } else f += c;
    } else if (c === '"') q = true;
    else if (c === ',') { row.push(f); f = ''; }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(f); f = ''; rows.push(row); row = [];
    } else f += c;
  }
  if (f !== '' || row.length) { row.push(f); rows.push(row); }
  return rows;
}

/** Re-writes a CSV text through toCsv so every field is formula-safe. */
export function sanitizeCsv(text: string): string {
  const [head, ...rest] = parseCsv(text);
  if (!head) return '';
  return toCsv(rest.map((r) => Object.fromEntries(head.map((h, i) => [h, r[i] ?? '']))), head);
}

/** RFC 4180: header row first, fields quoted when needed, every row ends with CRLF. */
export function toCsv(rows: object[], columns: string[]): string {
  const lines = [columns.map((c) => cell(c)).join(',')];
  for (const r of rows) lines.push(columns.map((c) => cell((r as Record<string, Cell>)[c])).join(','));
  return lines.join('\r\n') + '\r\n';
}

/** Saves text as a file through a temporary link. */
export function downloadCsv(name: string, text: string): void {
  const url = URL.createObjectURL(new Blob(['\uFEFF', text], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** 'Brooklyn CB 9' + 'stretches' + date -> 'brooklyn-cb-9-stretches-2026-11-24.csv'. */
export function exportFileName(areaName: string, what: 'stretches' | 'blocks' | 'crashes', date: string): string {
  const slug = areaName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'citywide';
  return `${slug}-${what}-${date}.csv`;
}

export const STRETCH_COLUMNS = ['area_rank', 'tier', 'street', 'from_street', 'to_street', 'blocks', 'score',
  'crashes_5y', 'injured_5y', 'killed_5y', 'crashes_no_lane_5y', 'last_crash_date', 'community_boards',
  'council_districts', 'stretch_id'];

export function stretchRows(list: Ranked<Stretch>[]): object[] {
  return list.map(({ item: s, areaRank }) => ({
    area_rank: areaRank, tier: s.tier, street: titleCase(s.street),
    from_street: s.from_street ? titleCase(s.from_street) : 'continues',
    to_street: s.to_street ? titleCase(s.to_street) : 'continues',
    blocks: s.blocks, score: s.score.toFixed(1), crashes_5y: s.crashes_5y, injured_5y: s.injured_5y,
    killed_5y: s.killed_5y, crashes_no_lane_5y: s.crashes_no_lane_5y, last_crash_date: s.last_crash_date,
    community_boards: s.cbs, council_districts: s.cds, stretch_id: s.stretch_id,
  }));
}

export const BLOCK_COLUMNS = ['area_rank', 'tier', 'street', 'borough', 'current_facility', 'score', 'crashes_5y',
  'injured_5y', 'killed_5y', 'crashes_no_lane_5y', 'last_crash_date', 'posted_speed', 'travel_lanes',
  'community_board', 'council_district', 'stretch_id', 'segmentid'];

export function blockRows(list: Ranked<Block>[]): object[] {
  return list.map(({ item: b, areaRank }) => ({
    area_rank: areaRank, tier: b.tier, street: titleCase(b.street), borough: b.borough,
    current_facility: b.current_facility, score: b.score.toFixed(1), crashes_5y: b.crashes_5y,
    injured_5y: b.injured_5y, killed_5y: b.killed_5y, crashes_no_lane_5y: b.crashes_no_lane_5y,
    last_crash_date: b.last_crash_date, posted_speed: b.posted_speed, travel_lanes: b.travel_lanes,
    community_board: b.cb, council_district: b.cd, stretch_id: b.stretch_id, segmentid: b.segmentid,
  }));
}
