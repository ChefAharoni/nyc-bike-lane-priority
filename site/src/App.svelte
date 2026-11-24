<script lang="ts">
  import { onMount, tick, untrack } from 'svelte';
  import TopBar from './lib/TopBar.svelte';
  import Totals from './lib/Totals.svelte';
  import RankedList from './lib/RankedList.svelte';
  import MapView from './lib/MapView.svelte';
  import Detail from './lib/Detail.svelte';
  import Notice from './lib/Notice.svelte';
  import ExportDialog from './lib/ExportDialog.svelte';
  import Report from './lib/Report.svelte';
  import About from './lib/About.svelte';
  import { buildReport, type ReportKind, type ReportModel } from './lib/report';
  import './print.css';
  import { loadData, type DataBundle } from './lib/load';
  import { formatRoute, parseRouteChecked, type Route } from './lib/route';
  import type { AreaKind } from './lib/types';

  const first = parseRouteChecked(location.hash);
  const initial = first.route;
  let route = $state<Route>(initial);
  let data = $state<DataBundle | null>(null);
  /** The date the current `data` was requested for (route.date at load time). */
  let loadedFor = $state<string | null>(initial.date);
  let error = $state<string | null>(null);
  const PROBLEM: Record<'link' | 'date', string> = {
    link: "That link wasn't recognized; showing citywide.",
    date: "That date wasn't recognized; showing the latest data.",
  };
  // A short list of dismissible notices (newest last, at most 3) so one never hides another.
  let notices = $state<{ id: number; text: string }[]>([]);
  let noticeId = 0;
  function pushNotice(text: string) {
    if (notices.some((n) => n.text === text)) return;
    notices = [...notices, { id: ++noticeId, text }].slice(-3);
  }
  if (first.problem) pushNotice(PROBLEM[first.problem]);
  if (first.problem) history.replaceState(null, '', formatRoute(first.route));
  function read(): Route {
    const c = parseRouteChecked(location.hash);
    if (c.problem) {
      pushNotice(PROBLEM[c.problem]);
      history.replaceState(null, '', formatRoute(c.route));
    }
    return c.route;
  }
  let sharedOnly = $state(false);
  let mode = $state<'stretches' | 'streets'>('stretches');
  let highlightStreet = $state<string | null>(null);
  let kindChoice = $state<AreaKind>(initial.kind === 'citywide' ? 'cb' : initial.kind);

  const kind = $derived<AreaKind>(route.kind === 'citywide' ? kindChoice : route.kind);
  const area = $derived(data && route.areaId && route.kind !== 'citywide'
    ? data.areas[route.kind].find((a) => a.id === route.areaId) ?? null : null);
  const label = $derived(area ? area.name : 'Citywide');

  function navigate(patch: Partial<Route>) {
    location.hash = formatRoute({ ...route, ...patch });
  }
  function setKind(k: AreaKind) {
    kindChoice = k;
    if (route.kind !== 'citywide' && route.kind !== k) navigate({ kind: 'citywide', areaId: null, selection: null });
  }

  onMount(() => {
    const onHash = () => { route = read(); };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  });

  // Load (or switch) the data set whenever the requested date changes; the old data stays up meanwhile.
  let loadSeq = 0;
  $effect(() => {
    const want = route.date;
    // Already showing exactly this date (for example right after a fallback rewrote the address): nothing to load.
    if (untrack(() => data && loadedFor === want)) return;
    const my = ++loadSeq;
    loadData(want).then((d) => {
      if (my !== loadSeq) return;
      data = d;
      loadedFor = want;
      error = null;
      if (d.notice) pushNotice(d.notice);
      // Show the date that really loaded in the address (a pruned date becomes the one used).
      if (want !== d.date) {
        loadedFor = d.date;
        history.replaceState(null, '', formatRoute({ ...route, date: d.date }));
        route = read();
      }
    }, (e) => {
      if (my !== loadSeq) return;
      const msg = e instanceof Error ? e.message : String(e);
      if (!want) { error = msg; return; }
      // An older date that will not load falls back to the latest data, and the address says so.
      loadData(null).then((d) => {
        if (my !== loadSeq) return;
        data = d;
        error = null;
        pushNotice(`Couldn't load ${want}; showing the latest data.`);
        loadedFor = null;
        history.replaceState(null, '', formatRoute({ ...route, date: null }));
        route = read();
      }, (e2) => { if (my === loadSeq) error = e2 instanceof Error ? e2.message : String(e2); });
    });
  });
  const settled = $derived(!!data && loadedFor === route.date);
  const older = $derived(!!data && data.date !== null);

  $effect(() => { if (route.kind !== 'citywide') kindChoice = route.kind; });
  $effect(() => { route.view; route.areaId; mode; highlightStreet = null; });
  // The stretches of the whole street picked in the list (shown on the map, fitted to their box).
  const highlightStreetStretchIds = $derived(highlightStreet && data
    ? data.streets.find((s) => s.street_key === highlightStreet)?.stretch_ids ?? [] : []);
  const highlightStretchIds = $derived(route.view === 'streets' && mode === 'streets' ? highlightStreetStretchIds : []);

  // An area id the data does not know falls back to citywide with a notice.
  $effect(() => {
    if (data && settled && route.page === 'map' && route.kind !== 'citywide' && !area) {
      pushNotice('Area not found; showing citywide.');
      history.replaceState(null, '', formatRoute({ ...route, kind: 'citywide', areaId: null, selection: null }));
      route = read();
    }
  });

  // A selection the loaded data does not contain (a stale link, or a date without that street) is dropped.
  $effect(() => {
    const sel = route.selection;
    if (!data || !settled || !sel) return;
    const found = sel.type === 'stretch'
      ? data.stretches.some((x) => x.stretch_id === sel.id)
      : data.blocks.some((x) => x.segmentid === sel.id);
    if (!found) {
      pushNotice("That street isn't in the ranking for this date.");
      history.replaceState(null, '', formatRoute({ ...route, selection: null }));
      route = read();
    }
  });

  // "Show crashes" belongs to one selection; it resets when the selection changes or an older date is shown.
  let showCrashes = $state(false);
  const selKey = $derived(route.selection ? `${route.selection.type}:${route.selection.id}` : null);
  $effect(() => { selKey; showCrashes = false; });
  const crashSegments = $derived.by<string[] | null>(() => {
    const sel = route.selection;
    if (!showCrashes || older || !data || !sel) return null;
    if (sel.type === 'block') return [sel.id];
    return data.stretches.find((x) => x.stretch_id === sel.id)?.segmentids ?? null;
  });

  $effect(() => {
    document.title = route.page === 'about' ? 'About this data · NYC Bike Lane Priority'
      : area ? `${area.name} · NYC Bike Lane Priority` : 'NYC Bike Lane Priority';
  });

  const totals = $derived(data ? (area ? area.totals : data.meta.citywide) : null);

  // Export: the dialog picks a report, the report renders into a print-only container, then the browser prints.
  let exporting = $state(false);
  let preparing = $state(false);
  let printing = $state<{ model: ReportModel; image: string | null; note: string | null } | null>(null);
  let mapView: { snapshot: (b: [number, number, number, number] | null) => Promise<string | null> } | undefined = $state();

  async function printReport(which: ReportKind) {
    if (!data) return;
    exporting = false;
    preparing = true;
    const model = buildReport(which, data, route, location.href);
    let image: string | null = null;
    let note: string | null = null;
    if (which === 'board') {
      image = (await mapView?.snapshot(area?.bbox ?? null)) ?? null;
      if (!image) note = 'The map image was not ready in time, so it is left out of this report.';
    }
    printing = { model, image, note };
    await tick();
    preparing = false;
    // Let the report lay out (and the image decode) before the print window opens.
    await new Promise((r) => requestAnimationFrame(() => r(null)));
    const done = () => { printing = null; window.removeEventListener('afterprint', done); document.getElementById('export-btn')?.focus(); };
    window.addEventListener('afterprint', done);
    window.print();
  }
</script>

<div class="app">
  <TopBar {route} {kind} areas={data?.areas ?? null} meta={data?.meta ?? null}
    index={data?.index ?? null} loadedDate={data?.date ?? null} {navigate} {setKind} onexport={() => (exporting = true)} />

  {#if data && older}
    <Notice tone="info">
      Viewing data as of {data.date}. <a href={formatRoute({ ...route, date: null })}>Back to latest</a>
    </Notice>
  {/if}

  {#each notices as n (n.id)}
    <Notice ondismiss={() => (notices = notices.filter((x) => x.id !== n.id))}>{n.text}</Notice>
  {/each}

  {#if route.page === 'about'}
    <About meta={data?.meta ?? null} areas={data?.areas ?? null} />
  {:else}
    <main class="shell">
      <div id="map" class="map" role="region" aria-label="Map">
        {#if data}
          <MapView bind:this={mapView} {data} {route} {kind} {area} {crashSegments} crashesDisabled={older} {highlightStretchIds}
            onselect={(type, id) => navigate({ selection: { type, id } })} />
        {/if}
      </div>
      <aside class="panel" aria-label="Ranking">
        {#if data && route.selection}
          <div class="pinned">
            <Detail {data} {route} {showCrashes} crashesDisabled={older} onnavigate={navigate}
              onshowblocks={() => navigate({ view: route.view === 'blocks' ? 'streets' : 'blocks' })}
              onshowcrashes={() => (showCrashes = !showCrashes)}
              onclose={() => navigate({ selection: null })} />
          </div>
        {/if}
        <div class="scroll">
        {#if error}
          <p class="msg">Could not load the data. {error}</p>
        {:else if !data || !totals}
          <p class="msg">Loading data…</p>
        {:else}
          <div class="head">
            <Totals {totals} {label} />
            {#if route.view === 'streets'}
              <div class="seg" role="group" aria-label="List type">
                <button type="button" aria-pressed={mode === 'stretches'} onclick={() => (mode = 'stretches')}>Stretches</button>
                <button type="button" aria-pressed={mode === 'streets'} onclick={() => (mode = 'streets')}>Whole streets</button>
              </div>
              {#if mode === 'stretches'}
                <label class="check">
                  <input type="checkbox" bind:checked={sharedOnly} />
                  Shared with neighbors only
                </label>
              {/if}
            {/if}
          </div>
          <RankedList
            {data} {route} {kind} {sharedOnly} {mode} {highlightStreet}
            onselect={(type, id) => navigate({ selection: route.selection?.id === id ? null : { type, id } })}
            onstreet={(k) => (highlightStreet = highlightStreet === k ? null : k)}
            onunfilter={() => navigate({ selection: null })}
          />
        {/if}
        </div>
      </aside>
    </main>
  {/if}
</div>

{#if exporting && data}
  <ExportDialog {data} {route} areaName={label} {older} onprint={printReport} onclose={() => { exporting = false; if (!preparing) document.getElementById('export-btn')?.focus(); }} />
{/if}

{#if preparing}
  <div class="busy" role="status">Preparing report…</div>
{/if}

{#if printing}
  <div class="print-only" aria-hidden="true">
    <Report model={printing.model} kind={route.kind === 'citywide' ? 'cb' : route.kind} mapImage={printing.image} mapNote={printing.note} />
  </div>
{/if}

<style>
  .busy { position: fixed; top: 4.5rem; left: 50%; transform: translateX(-50%); z-index: 50; background: var(--navy); color: #fff; padding: 0.6rem 1.2rem; border-radius: 8px; font-weight: 600; box-shadow: 0 4px 16px rgba(0,0,0,0.3); }
  .app { display: flex; flex-direction: column; height: 100dvh; }
  .shell { flex: 1; min-height: 0; display: grid; grid-template-columns: 340px 1fr; }
  .panel { grid-column: 1; grid-row: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; background: var(--paper); border-right: 1px solid var(--line); }
  .pinned { flex: none; max-height: 55%; overflow-y: auto; }
  .scroll { flex: 1; min-height: 0; overflow-y: auto; }
  .map { position: relative; grid-column: 2; grid-row: 1; background: #e2e8f0; min-height: 0; }
  .head { padding: 0.9rem 1rem 0.75rem; border-bottom: 2px solid var(--navy); display: flex; flex-direction: column; gap: 0.75rem; }
  .seg { display: flex; border: 2px solid var(--navy); border-radius: 6px; overflow: hidden; }
  .seg button { flex: 1; font: inherit; font-weight: 600; font-size: 0.875rem; padding: 0.4rem; cursor: pointer; background: #fff; color: var(--navy); border: 0; }
  /* inset ring: .seg clips overflow; navy on white and white on navy are both above 3:1 */
  .seg button:focus-visible { outline-offset: -3px; }
  .seg button[aria-pressed='true']:focus-visible { outline-color: #fff; }
  .seg button[aria-pressed='true'] { background: var(--navy); color: #fff; }
  .check { display: flex; align-items: center; gap: 0.5rem; font-size: 0.95rem; cursor: pointer; }
  .check input { width: 1.15rem; height: 1.15rem; accent-color: var(--area); }
  .msg { padding: 1.25rem 1rem; color: var(--muted); }
  @media (max-width: 767px) {
    .app { height: auto; min-height: 100dvh; }
    .shell { display: flex; flex-direction: column; }
    .map { height: 55vh; flex: none; }
    .panel { display: block; overflow: visible; border-right: 0; }
    .pinned { max-height: none; }
    .scroll { overflow: visible; }
  }
</style>
