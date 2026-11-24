import type { Areas, Block, Meta, SnapshotIndex, Stretch, Street } from './types';

export interface DataBundle {
  meta: Meta; areas: Areas; blocks: Block[]; stretches: Stretch[]; streets: Street[];
  index: SnapshotIndex;
  /** The snapshot date actually loaded, or null for the live (current) files. */
  date: string | null;
  notice: string | null;
}

type Files = Omit<DataBundle, 'index' | 'date' | 'notice'>;

const DATE = /^\d{4}-\d{2}-\d{2}$/;
const cache = new Map<string, Promise<Files>>();
let indexP: Promise<SnapshotIndex> | null = null;

/** Clears cached loads (tests). */
export function resetLoadCache(): void {
  cache.clear();
  indexP = null;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`data/${path}`);
  if (!res.ok) throw new Error(`Could not load ${path} (${res.status})`);
  return res.json() as Promise<T>;
}

/** Snapshot files are gzip. A server that sets Content-Encoding makes the browser decode them already. */
async function getGz<T>(path: string): Promise<T> {
  const res = await fetch(`data/${path}`);
  if (!res.ok) throw new Error(`Could not load ${path} (${res.status})`);
  const buf = await res.arrayBuffer();
  const b = new Uint8Array(buf);
  if (b.length > 1 && b[0] === 0x1f && b[1] === 0x8b) {
    return new Response(new Blob([buf]).stream().pipeThrough(new DecompressionStream('gzip'))).json() as Promise<T>;
  }
  return JSON.parse(new TextDecoder().decode(b)) as T;
}

function memo(key: string, make: () => Promise<Files>): Promise<Files> {
  let p = cache.get(key);
  if (!p) {
    p = make();
    p.catch(() => cache.delete(key));
    cache.set(key, p);
  }
  return p;
}

const loadCurrent = (): Promise<Files> => memo('current', async () => {
  const [meta, areas, blocks, stretches, streets] = await Promise.all([
    getJson<Meta>('meta.json'), getJson<Areas>('areas.json'), getJson<Block[]>('blocks.json'),
    getJson<Stretch[]>('stretches.json'), getJson<Street[]>('streets.json'),
  ]);
  return { meta, areas, blocks, stretches, streets };
});

const loadSnapshot = (date: string): Promise<Files> => memo(date, async () => {
  const p = (n: string) => `snapshots/${date}/${n}.json.gz`;
  const [meta, areas, blocks, stretches, streets] = await Promise.all([
    getGz<Meta>(p('meta')), getGz<Areas>(p('areas')), getGz<Block[]>(p('blocks')),
    getGz<Stretch[]>(p('stretches')), getGz<Street[]>(p('streets')),
  ]);
  return { meta, areas, blocks, stretches, streets };
});

function loadIndex(): Promise<SnapshotIndex> {
  if (!indexP) {
    indexP = getJson<SnapshotIndex>('snapshots/index.json');
    indexP.catch(() => { indexP = null; });
  }
  return indexP;
}

/**
 * Loads the data set for a date. No date, a malformed date, or the latest date loads the live files.
 * A listed older date loads its snapshot. An unlisted date loads the nearest earlier snapshot with a notice.
 */
export async function loadData(date: string | null): Promise<DataBundle> {
  const index = await loadIndex();
  const live = async (notice: string | null): Promise<DataBundle> =>
    ({ ...(await loadCurrent()), index, date: null, notice });
  if (!date || !DATE.test(date) || date === index.latest) return live(null);
  if (date > index.latest) return live(`${date} is newer than the latest data; showing the latest data.`);
  if (index.dates.includes(date)) return { ...(await loadSnapshot(date)), index, date, notice: null };
  const earlier = index.dates.filter((d) => d < date).sort().reverse()[0];
  if (!earlier) return live(`${date} is older than any stored snapshot; showing the latest data.`);
  const notice = `${date} is no longer stored; showing ${earlier}.`;
  if (earlier === index.latest) return live(notice);
  return { ...(await loadSnapshot(earlier)), index, date: earlier, notice };
}
