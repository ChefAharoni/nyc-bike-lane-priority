<script lang="ts">
  import type { AreaKind, Block, Stretch } from './types';
  import type { DataBundle } from './load';
  import type { Route } from './route';
  import { formatRoute } from './route';
  import { areaTag, areaTagCity, fmtDate, fmtEnds, fmtInt, fmtScore, titleCase } from './format';

  let { data, route, showCrashes, crashesDisabled, onnavigate, onshowblocks, onshowcrashes, onclose }: {
    data: DataBundle; route: Route; showCrashes: boolean; crashesDisabled: boolean;
    onnavigate: (patch: Partial<Route>) => void; onshowblocks: () => void; onshowcrashes: () => void; onclose: () => void;
  } = $props();

  const sel = $derived(route.selection);
  const stretch = $derived<Stretch | null>(sel?.type === 'stretch'
    ? data.stretches.find((s) => s.stretch_id === sel.id) ?? null : null);
  const block = $derived<Block | null>(sel?.type === 'block'
    ? data.blocks.find((b) => b.segmentid === sel.id) ?? null : null);
  const parent = $derived<Stretch | null>(block?.stretch_id
    ? data.stretches.find((s) => s.stretch_id === block.stretch_id) ?? null : null);

  const TIER = { 1: 'No bike lane today', 2: 'Paint or sharrow only' } as const;
  const FACILITY: Record<string, string> = { none: 'No bike lane', paint: 'Painted lane', sharrow: 'Shared lane marking', protected: 'Protected lane' };

  const NOW: Record<string, string> = { none: 'No bike lane today', paint: 'Painted lane', sharrow: 'Sharrow', protected: 'Protected lane' };

  const tag = (kind: AreaKind, id: string) => (kind === 'cb' && route.kind === 'citywide' ? areaTagCity(id) : areaTag(kind, id));
  const areaName = (kind: AreaKind, id: string) => data.areas[kind].find((a) => a.id === id)?.name ?? tag(kind, id);
  const areaHref = (kind: AreaKind, id: string) =>
    formatRoute({ ...route, kind, areaId: id });

  const none = (n: number | null, unit = '') => (n === null ? 'Not recorded' : `${fmtInt(n)}${unit}`);
  const last = (d: string | null) => (d ? fmtDate(d) : 'None recorded');

  let toast = $state<string | null>(null);
  let timer: ReturnType<typeof setTimeout> | undefined;
  async function copy() {
    try {
      await navigator.clipboard.writeText(location.href);
      toast = 'Link copied';
    } catch {
      toast = 'Could not copy; copy the address from the browser bar.';
    }
    clearTimeout(timer);
    timer = setTimeout(() => (toast = null), 2500);
  }
</script>

{#snippet actions(blocksBtn: boolean)}
  <div class="actions">
    {#if blocksBtn}
      <button type="button" onclick={onshowblocks} aria-pressed={route.view === 'blocks'}>Show blocks</button>
    {/if}
    <button type="button" onclick={onshowcrashes} aria-pressed={showCrashes} disabled={crashesDisabled}>
      {showCrashes ? 'Hide crashes' : 'Show crashes'}
    </button>
    <button type="button" onclick={copy}>Copy link</button>
  </div>
  {#if crashesDisabled}<p class="note">Crash dots show current data only.</p>{/if}
{/snippet}

{#if stretch}
  <section class="detail" aria-label="Details: {titleCase(stretch.street)}">
    <div class="top">
      <div>
        <h2>{titleCase(stretch.street)}</h2>
        <p class="ends">{fmtEnds(stretch.from_street, stretch.to_street)}</p>
      </div>
      <button type="button" class="x" aria-label="Close details" onclick={onclose}>×</button>
    </div>
    <p class="tier"><span class="badge t{stretch.tier}">T{stretch.tier}</span> {TIER[stretch.tier]}</p>
    <dl>
      <div><dt>Crashes counted</dt><dd>{fmtInt(stretch.crashes_5y)}</dd></div>
      <div><dt>Injured</dt><dd>{fmtInt(stretch.injured_5y)}</dd></div>
      <div><dt>Killed</dt><dd>{fmtInt(stretch.killed_5y)}</dd></div>
      <div><dt>With no lane at the time</dt><dd>{fmtInt(stretch.crashes_no_lane_5y)}</dd></div>
      <div><dt>Last crash</dt><dd class="small">{last(stretch.last_crash_date)}</dd></div>
      <div><dt>Blocks</dt><dd>{fmtInt(stretch.blocks)}</dd></div>
    </dl>
    <div class="areas">
      <p><strong>Community Boards</strong></p>
      <ul>{#each stretch.cbs as id (id)}<li><a href={areaHref('cb', id)}>{areaName('cb', id)}</a></li>{/each}</ul>
      <p><strong>Council Districts</strong></p>
      <ul>{#each stretch.cds as id (id)}<li><a href={areaHref('cd', id)}>{areaName('cd', id)}</a></li>{/each}</ul>
    </div>
    {@render actions(true)}
  </section>
{:else if block}
  <section class="detail" aria-label="Details: {titleCase(block.street)}">
    <div class="top">
      <div>
        <h2>{titleCase(block.street)}</h2>
        <p class="ends">{block.borough ?? ''} · block {block.segmentid}</p>
      </div>
      <button type="button" class="x" aria-label="Close details" onclick={onclose}>×</button>
    </div>
    <p class="tier">
      {#if block.rank !== null && block.tier}<span class="badge t{block.tier}">T{block.tier}</span> {TIER[block.tier]}
      · {FACILITY[block.current_facility] ?? ''}{:else}Not ranked · {NOW[block.current_facility] ?? ''}{/if}
    </p>
    <dl>
      <div><dt>Rank, all blocks</dt><dd>{block.rank ?? 'None'}</dd></div>
      <div><dt>Score</dt><dd>{fmtScore(block.score)}</dd></div>
      <div><dt>Crashes counted</dt><dd>{fmtInt(block.crashes_5y)}</dd></div>
      <div><dt>Injured</dt><dd>{fmtInt(block.injured_5y)}</dd></div>
      <div><dt>Killed</dt><dd>{fmtInt(block.killed_5y)}</dd></div>
      <div><dt>With no lane at the time</dt><dd>{fmtInt(block.crashes_no_lane_5y)}</dd></div>
      <div><dt>Crashes, all years</dt><dd>{fmtInt(block.crashes_all_years)}</dd></div>
      <div><dt>Last crash</dt><dd class="small">{last(block.last_crash_date)}</dd></div>
      <div><dt>Posted speed</dt><dd>{none(block.posted_speed, ' mph')}</dd></div>
      <div><dt>Travel lanes</dt><dd>{none(block.travel_lanes)}</dd></div>
    </dl>
    <div class="areas">
      {#if parent}
        <p><strong>Part of</strong>
          <a href={formatRoute({ ...route, view: 'streets', selection: { type: 'stretch', id: parent.stretch_id } })}
            onclick={(e) => { e.preventDefault(); onnavigate({ view: 'streets', selection: { type: 'stretch', id: parent.stretch_id } }); }}>
            {titleCase(parent.street)}, {fmtEnds(parent.from_street, parent.to_street)}</a></p>
      {/if}
      <p><strong>Areas</strong></p>
      <ul>
        {#if block.cb}<li><a href={areaHref('cb', block.cb)}>{areaName('cb', block.cb)}</a>{block.area_by_nearest ? ' (nearest board)' : ''}</li>{/if}
        {#if block.cd}<li><a href={areaHref('cd', block.cd)}>{areaName('cd', block.cd)}</a></li>{/if}
      </ul>
    </div>
    {@render actions(false)}
  </section>
{/if}

{#if toast}<div class="toast" role="status">{toast}</div>{/if}

<style>
  .detail { padding: 0.9rem 1rem; border-bottom: 2px solid var(--navy); background: #f8fafc; }
  .top { display: flex; justify-content: space-between; gap: 0.5rem; }
  h2 { margin: 0; font-size: 1.15rem; }
  .ends { margin: 0.1rem 0 0; color: var(--muted); }
  .x { font: inherit; font-size: 1.5rem; line-height: 1; width: 2.2rem; height: 2.2rem; background: transparent; border: 1px solid var(--line); border-radius: 6px; cursor: pointer; color: var(--navy); flex: none; }
  .tier { margin: 0.5rem 0; font-weight: 600; }
  .badge { display: inline-grid; place-items: center; min-width: 2rem; height: 1.6rem; border-radius: 5px; font-weight: 800; font-size: 0.8rem; margin-right: 0.3rem; }
  .t1 { background: var(--t1); color: #fff; }
  .t2 { background: var(--t2); color: #1c1100; }
  dl { margin: 0; display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem 0.6rem; }
  dl div { display: flex; flex-direction: column; min-width: 0; }
  dd { margin: 0; order: -1; font-size: 1.2rem; font-weight: 800; font-variant-numeric: tabular-nums; }
  dd.small { font-size: 0.95rem; line-height: 1.7rem; }
  dt { font-size: 0.78rem; color: var(--muted); line-height: 1.25; }
  .areas { margin-top: 0.7rem; font-size: 0.92rem; }
  .areas p { margin: 0.3rem 0 0; }
  .areas ul { margin: 0.15rem 0 0; padding: 0; list-style: none; display: flex; flex-wrap: wrap; gap: 0.15rem 0.9rem; }
  .actions { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.8rem; }
  .actions button { font: inherit; font-weight: 600; font-size: 0.9rem; padding: 0.45rem 0.8rem; background: #fff; color: var(--area-dark); border: 2px solid var(--area); border-radius: 6px; cursor: pointer; }
  .actions button[aria-pressed='true'] { background: var(--area); color: #fff; }
  .actions button:disabled { color: #98a2b3; border-color: #cbd5e1; background: #f1f5f9; }
  .note { margin: 0.4rem 0 0; font-size: 0.85rem; color: var(--muted); }
  .toast { position: fixed; bottom: 1.2rem; left: 50%; transform: translateX(-50%); z-index: 20; background: var(--navy); color: #fff; padding: 0.6rem 1.1rem; border-radius: 8px; box-shadow: 0 2px 10px rgb(0 0 0 / 0.3); font-weight: 600; }
</style>
