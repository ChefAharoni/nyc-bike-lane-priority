import { gzipSync } from 'node:zlib';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { loadData, resetLoadCache } from './load';

const NAMES = ['meta', 'areas', 'blocks', 'stretches', 'streets'] as const;
const body = (tag: string, name: string) => (name === 'meta' ? { data_date: tag } : name === 'areas' ? { cb: [], cd: [] } : [{ tag }]);

interface Mock { urls: string[]; }

/** Mocks fetch: current files carry tag "live", snapshot files carry their date. mode picks how snapshots are sent. */
function mockFetch(dates: string[], mode: 'gzip' | 'plain' = 'gzip'): Mock {
  const seen: Mock = { urls: [] };
  const index = { latest: dates[0], dates };
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    seen.urls.push(url);
    const path = url.replace(/^data\//, '');
    if (path === 'snapshots/index.json') return new Response(JSON.stringify(index));
    const snap = /^snapshots\/(\d{4}-\d{2}-\d{2})\/(\w+)\.json\.gz$/.exec(path);
    if (snap) {
      const json = JSON.stringify(body(snap[1], snap[2]));
      if (mode === 'plain') return new Response(json);
      const gz = gzipSync(Buffer.from(json));
      return new Response(new Uint8Array(gz));
    }
    const cur = /^(\w+)\.json$/.exec(path);
    if (cur && (NAMES as readonly string[]).includes(cur[1])) return new Response(JSON.stringify(body('live', cur[1])));
    return new Response('nope', { status: 404 });
  }));
  return seen;
}

describe('loadData', () => {
  beforeEach(() => { resetLoadCache(); vi.unstubAllGlobals(); });

  it('loads the live files for no date and for the latest date', async () => {
    const seen = mockFetch(['2026-11-24', '2026-11-23']);
    const a = await loadData(null);
    expect(a.meta.data_date).toBe('live');
    expect(a.date).toBeNull();
    expect(a.notice).toBeNull();
    const b = await loadData('2026-11-24');
    expect(b.meta.data_date).toBe('live');
    expect(b.date).toBeNull();
    expect(seen.urls.some((u) => u.includes('snapshots/2026-11-24/'))).toBe(false);
  });

  it('loads a listed older date from its gzipped snapshot', async () => {
    const seen = mockFetch(['2026-11-24', '2026-11-23']);
    const d = await loadData('2026-11-23');
    expect(d.date).toBe('2026-11-23');
    expect(d.notice).toBeNull();
    expect(d.meta.data_date).toBe('2026-11-23');
    expect(d.areas).toEqual({ cb: [], cd: [] });
    expect(seen.urls).toContain('data/snapshots/2026-11-23/blocks.json.gz');
  });

  it('parses a snapshot the browser already decoded (plain JSON bytes)', async () => {
    mockFetch(['2026-11-24', '2026-11-23'], 'plain');
    const d = await loadData('2026-11-23');
    expect(d.date).toBe('2026-11-23');
    expect(d.blocks).toEqual([{ tag: '2026-11-23' }]);
  });

  it('falls back to the nearest earlier snapshot for a pruned date', async () => {
    mockFetch(['2026-11-23', '2026-10-01']);
    const d = await loadData('2026-10-15');
    expect(d.date).toBe('2026-10-01');
    expect(d.meta.data_date).toBe('2026-10-01');
    expect(d.notice).toBe('2026-10-15 is no longer stored; showing 2026-10-01.');
  });

  it('loads current with a notice when the date is earlier than every snapshot', async () => {
    mockFetch(['2026-11-23', '2026-10-01']);
    const d = await loadData('2026-01-01');
    expect(d.date).toBeNull();
    expect(d.meta.data_date).toBe('live');
    expect(d.notice).toBe('2026-01-01 is older than any stored snapshot; showing the latest data.');
  });

  it('treats a malformed date as current with no notice', async () => {
    mockFetch(['2026-11-23', '2026-10-01']);
    const d = await loadData('garbage');
    expect(d.date).toBeNull();
    expect(d.notice).toBeNull();
  });

  it('a date later than the latest loads the live files with a newer-than-latest notice', async () => {
    mockFetch(['2026-11-24', '2026-11-23']);
    const d = await loadData('2026-12-31');
    expect(d.date).toBeNull();
    expect(d.notice).toBe('2026-12-31 is newer than the latest data; showing the latest data.');
  });
});
