<script lang="ts">
  import type { AreaKind } from './types';
  import type { DataBundle } from './load';
  import type { Route } from './route';
  import { areaTag, areaTagCity, fmtEnds, fmtInt, fmtScore, titleCase } from './format';
  import { blocksForArea, streetsForArea, stretchesForArea } from './rank';

  let { data, route, kind, sharedOnly, mode, highlightStreet, onselect, onstreet, onunfilter }: {
    data: DataBundle; route: Route; kind: AreaKind; sharedOnly: boolean; mode: 'stretches' | 'streets';
    highlightStreet: string | null;
    onselect: (type: 'stretch' | 'block', id: string) => void; onstreet: (key: string) => void;
    onunfilter: () => void;
  } = $props();

  interface Row {
    key: string; tier: 1 | 2; rank: number; title: string; sub: string; count: string; score: string;
    tags: string; selected: boolean; pick: () => void;
  }
  const STEP = 100;
  let shown = $state(STEP);
  let listEl: HTMLUListElement | undefined = $state();

  const tags = (all: string[], id: string | null) =>
    (id && all.includes(id) ? [id, ...all.filter((a) => a !== id)] : all).map((a) => (!id && kind === 'cb' ? areaTagCity(a) : areaTag(kind, a))).join(' · ');
  const FACILITY: Record<string, string> = { none: 'No bike lane', paint: 'Painted lane', sharrow: 'Shared lane marking', protected: 'Protected lane' };

  // "Show blocks" on a stretch: the blocks view lists just that stretch's blocks.
  const filterStretch = $derived(route.view === 'blocks' && route.selection?.type === 'stretch'
    ? data.stretches.find((s) => s.stretch_id === route.selection!.id) ?? null : null);
  const members = $derived(filterStretch ? new Set(filterStretch.segmentids) : null);

  const rows = $derived.by<Row[]>(() => {
    const id = route.areaId;
    const sel = route.selection;
    if (route.view === 'blocks') {
      const list = members
        ? blocksForArea(data.blocks, 'citywide', null).filter((r) => members.has(r.item.segmentid))
        : blocksForArea(data.blocks, route.kind, id);
      return list.map(({ item: b, areaRank }) => ({
        key: b.segmentid, tier: b.tier as 1 | 2, rank: areaRank, title: titleCase(b.street),
        sub: `${FACILITY[b.current_facility] ?? ''} · ${b.borough ?? ''}`.replace(/ · $/, ''),
        count: `${fmtInt(b.crashes_5y)} crashes counted`, score: fmtScore(b.score),
        tags: (kind === 'cb' ? b.cb : b.cd) ? (route.kind === 'citywide' && kind === 'cb' ? areaTagCity(b.cb as string) : areaTag(kind, (kind === 'cb' ? b.cb : b.cd) as string)) : '',
        selected: sel?.type === 'block' && sel.id === b.segmentid, pick: () => onselect('block', b.segmentid),
      }));
    }
    if (mode === 'streets') {
      return streetsForArea(data.streets, route.kind, id).map(({ item: s, areaRank }) => ({
        key: s.street_key, tier: s.tier, rank: areaRank, title: titleCase(s.street), sub: s.borough,
        count: `${fmtInt(s.blocks)} blocks`, score: fmtScore(s.score),
        tags: tags(kind === 'cb' ? s.cbs : s.cds, id),
        selected: highlightStreet === s.street_key, pick: () => onstreet(s.street_key),
      }));
    }
    return stretchesForArea(data.stretches, route.kind, id, { sharedOnly }).map(({ item: s, areaRank }) => ({
      key: s.stretch_id, tier: s.tier, rank: areaRank, title: titleCase(s.street), sub: fmtEnds(s.from_street, s.to_street),
      count: `${fmtInt(s.blocks)} ${s.blocks === 1 ? 'block' : 'blocks'}`, score: fmtScore(s.score),
      tags: tags(kind === 'cb' ? s.cbs : s.cds, id),
      selected: sel?.type === 'stretch' && sel.id === s.stretch_id, pick: () => onselect('stretch', s.stretch_id),
    }));
  });

  // Paging resets only when the list itself changes, not when the selection moves.
  const listKey = $derived(`${route.kind}|${route.areaId}|${route.view}|${mode}|${sharedOnly}|${filterStretch?.stretch_id ?? ''}`);
  $effect(() => { listKey; shown = STEP; });
  // A selected row beyond the shown rows (for example from a shared link) stays visible.
  const selIndex = $derived(rows.findIndex((r) => r.selected));
  const visible = $derived(rows.slice(0, Math.max(shown, selIndex + 1)));

  function keydown(e: KeyboardEvent) {
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp' && e.key !== 'Home' && e.key !== 'End') return;
    const btns = Array.from(listEl?.querySelectorAll<HTMLButtonElement>('button.row') ?? []);
    const i = btns.indexOf(document.activeElement as HTMLButtonElement);
    if (i < 0) return;
    e.preventDefault();
    const next = e.key === 'Home' ? 0 : e.key === 'End' ? btns.length - 1 : e.key === 'ArrowDown' ? Math.min(i + 1, btns.length - 1) : Math.max(i - 1, 0);
    btns[next]?.focus();
  }
</script>

{#if filterStretch}
  <div class="filter">
    <span>Blocks of {titleCase(filterStretch.street)}</span>
    <button type="button" onclick={onunfilter}>Show all blocks</button>
  </div>
{/if}
{#if rows.length === 0}
  <p class="empty">No ranked streets in this area for this window.</p>
{:else}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <ul class="rows" bind:this={listEl} onkeydown={keydown} aria-label="Ranked list, {fmtInt(rows.length)} items">
    {#each visible as r (r.key)}
      <li>
        <button type="button" class="row" class:sel={r.selected} aria-current={r.selected ? 'true' : undefined} onclick={r.pick}>
          <span class="rank" aria-label="Rank {r.rank}">{r.rank}</span>
          <span class="badge t{r.tier}" title={r.tier === 1 ? 'Tier 1: no bike lane' : 'Tier 2: painted lane or shared lane marking'}>T{r.tier}</span>
          <span class="main">
            <span class="title">{r.title}</span>
            <span class="sub">{r.sub}</span>
            <span class="meta">{r.count} · score {r.score}{#if r.tags}{' · '}<span class="tags">{r.tags}</span>{/if}</span>
          </span>
        </button>
      </li>
    {/each}
  </ul>
  {#if visible.length < rows.length}
    <button type="button" class="more" onclick={() => (shown = visible.length + STEP)}>
      Show more ({fmtInt(rows.length - visible.length)} left)
    </button>
  {/if}
{/if}

<style>
  .filter { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; padding: 0.55rem 1rem; background: var(--area-soft); border-bottom: 1px solid var(--line); font-weight: 600; }
  .filter button { font: inherit; font-size: 0.85rem; font-weight: 600; background: #fff; color: var(--area-dark); border: 1px solid var(--area); border-radius: 6px; padding: 0.25rem 0.6rem; cursor: pointer; }
  .rows { list-style: none; margin: 0; padding: 0; }
  li { border-bottom: 1px solid var(--line); }
  .row {
    display: grid; grid-template-columns: 2.1rem 2.1rem 1fr; gap: 0.6rem; align-items: start; width: 100%;
    text-align: left; font: inherit; color: inherit; background: transparent; border: 0;
    border-left: 4px solid transparent; padding: 0.7rem 0.9rem 0.7rem 0.6rem; cursor: pointer;
  }
  .row:hover { background: #f1f5f9; }
  .row.sel { background: var(--area-soft); border-left-color: var(--area); }
  .rank { font-weight: 800; font-size: 1.1rem; font-variant-numeric: tabular-nums; text-align: right; color: var(--navy); line-height: 1.9rem; }
  .badge {
    display: inline-grid; place-items: center; width: 2.1rem; height: 1.9rem; border-radius: 5px;
    font-weight: 800; font-size: 0.85rem;
  }
  .t1 { background: var(--t1); color: #fff; }
  .t2 { background: var(--t2); color: #1c1100; }
  .main { display: flex; flex-direction: column; min-width: 0; gap: 0.1rem; }
  .title { font-weight: 700; line-height: 1.9rem; }
  .sub { font-size: 0.92rem; }
  .meta { font-size: 0.85rem; color: var(--muted); font-variant-numeric: tabular-nums; }
  .tags { font-weight: 600; color: var(--area-dark); }
  .empty { padding: 1.25rem 1rem; margin: 0; color: var(--muted); }
  .more {
    display: block; width: calc(100% - 2rem); margin: 0.75rem 1rem 1rem; padding: 0.6rem; font: inherit; font-weight: 600;
    background: #fff; color: var(--area-dark); border: 2px solid var(--area); border-radius: 6px; cursor: pointer;
  }
</style>
