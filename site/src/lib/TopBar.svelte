<script lang="ts">
  import type { Areas, Meta, AreaKind, SnapshotIndex } from './types';
  import type { Route } from './route';
  import { fmtDate } from './format';
  import AreaPicker from './AreaPicker.svelte';
  import SnapshotPicker from './SnapshotPicker.svelte';

  let { route, kind, areas, meta, index, loadedDate, navigate, setKind, onexport }: {
    route: Route; kind: AreaKind; areas: Areas | null; meta: Meta | null;
    index: SnapshotIndex | null; loadedDate: string | null;
    navigate: (patch: Partial<Route>) => void; setKind: (k: AreaKind) => void; onexport: () => void;
  } = $props();
</script>

<header class="bar">
  <a class="brand" href="#/citywide" aria-label="NYC Bike Lane Priority, home">
    <span class="mark" aria-hidden="true"></span>
    <span class="name">NYC Bike Lane Priority</span>
  </a>

  <div class="seg" role="group" aria-label="Kind of area">
    <button type="button" aria-pressed={kind === 'cb'} onclick={() => setKind('cb')}>Community Board</button>
    <button type="button" aria-pressed={kind === 'cd'} onclick={() => setKind('cd')}>Council District</button>
  </div>

  {#if areas}
    <AreaPicker
      {kind}
      areas={areas[kind]}
      areaId={route.kind === kind ? route.areaId : null}
      onpick={(id) => navigate(id ? { kind: kind, areaId: id, selection: null } : { kind: 'citywide', areaId: null, selection: null })}
    />
  {/if}

  <div class="seg" role="group" aria-label="What to rank">
    <button type="button" aria-pressed={route.view === 'streets'} onclick={() => navigate({ view: 'streets', selection: null })}>Streets</button>
    <button type="button" aria-pressed={route.view === 'blocks'} onclick={() => navigate({ view: 'blocks', selection: null })}>Blocks</button>
  </div>

  <div class="end">
    {#if meta}<span class="stamp">Data through {fmtDate(meta.data_date)}</span>{/if}
    {#if index}<SnapshotPicker {index} current={loadedDate} onpick={(d) => navigate({ date: d })} />{/if}
    <button type="button" id="export-btn" class="ghost" aria-haspopup="dialog" disabled={route.page === 'about'}
      title={route.page === 'about' ? 'Open the map to export a report' : undefined} onclick={onexport}>Export</button>
    <a class="ghost" href="#/about">About this data</a>
  </div>
</header>

<style>
  .bar {
    display: flex; flex-wrap: wrap; align-items: center; gap: 0.6rem 1rem; padding: 0.6rem 1rem;
    background: var(--navy); color: #fff;
  }
  .brand { display: flex; align-items: center; gap: 0.6rem; color: #fff; text-decoration: none; margin-right: 0.5rem; }
  .mark {
    width: 1.5rem; height: 1.5rem; border-radius: 4px; flex: none;
    background: linear-gradient(90deg, var(--t1) 0 33%, var(--t2) 33% 66%, var(--ok) 66%);
  }
  .name { font-weight: 800; font-size: 1.05rem; letter-spacing: -0.01em; }
  .seg { display: inline-flex; border: 2px solid #fff; border-radius: 6px; overflow: hidden; }
  .seg button {
    font: inherit; font-weight: 600; font-size: 0.875rem; padding: 0 0.7rem; height: 2.05rem; cursor: pointer;
    background: transparent; color: #fff; border: 0;
  }
  .seg button[aria-pressed='true'] { background: #fff; color: var(--navy); }
  /* inset ring (the group clips overflow): amber on navy and navy on white are both above 3:1 */
  .seg button:focus-visible { outline-offset: -3px; }
  .seg button[aria-pressed='true']:focus-visible { outline-color: var(--navy); }
  .end { margin-left: auto; display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; }
  .stamp { font-size: 0.875rem; color: #cbd5e1; }
  .ghost {
    font: inherit; font-size: 0.875rem; font-weight: 600; color: #fff; background: transparent; text-decoration: none;
    border: 1px solid #94a3b8; border-radius: 6px; padding: 0.35rem 0.7rem; cursor: pointer;
  }
  .ghost:disabled { color: #94a3b8; cursor: not-allowed; }
  @media (max-width: 767px) {
    .end { margin-left: 0; }
    .name { font-size: 1rem; }
  }
</style>
