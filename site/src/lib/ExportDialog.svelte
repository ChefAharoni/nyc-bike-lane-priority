<script lang="ts">
  import { onMount } from 'svelte';
  import type { DataBundle } from './load';
  import type { Route } from './route';
  import type { ReportKind } from './report';
  import { blocksForArea, stretchesForArea } from './rank';
  import { BLOCK_COLUMNS, sanitizeCsv, STRETCH_COLUMNS, blockRows, downloadCsv, exportFileName, stretchRows, toCsv } from './csv';

  let { data, route, areaName, older, onprint, onclose }: {
    data: DataBundle; route: Route; areaName: string; older: boolean;
    onprint: (kind: ReportKind) => void; onclose: () => void;
  } = $props();

  let dlg: HTMLDialogElement;
  let which = $state<ReportKind>('dot');
  let status = $state('');
  const date = $derived(data.meta.data_date);
  const id = $derived(route.kind === 'citywide' ? null : route.areaId);

  onMount(() => {
    dlg.showModal();
    return () => { if (dlg.open) dlg.close(); };
  });

  function stretchesCsv() {
    const rows = stretchRows(stretchesForArea(data.stretches, route.kind, id, { sharedOnly: false }));
    downloadCsv(exportFileName(areaName, 'stretches', date), toCsv(rows, STRETCH_COLUMNS));
    status = `Downloaded the stretches file (${rows.length} rows).`;
  }
  function blocksCsv() {
    const rows = blockRows(blocksForArea(data.blocks, route.kind, id));
    downloadCsv(exportFileName(areaName, 'blocks', date), toCsv(rows, BLOCK_COLUMNS));
    status = `Downloaded the blocks file (${rows.length} rows).`;
  }
  async function crashesCsv() {
    const file = route.kind === 'citywide' || !id ? 'citywide' : `${route.kind}-${id}`;
    status = 'Preparing the crashes file…';
    try {
      const res = await fetch(`data/crashes/${file}.csv`);
      if (!res.ok) throw new Error(String(res.status));
      downloadCsv(exportFileName(areaName, 'crashes', date), sanitizeCsv(await res.text()));
      status = 'Downloaded the crashes file.';
    } catch {
      status = 'Could not download the crashes file. Try again in a moment.';
    }
  }
</script>

<dialog bind:this={dlg} aria-labelledby="export-title" class="export-backdrop"
  onclose={onclose} onclick={(e) => { if (e.target === dlg) dlg.close(); }}>
  <div class="box">
    <h2 id="export-title">Export: {areaName}</h2>
    <p class="sub">Data through {date}</p>

    <h3>Printable report (PDF)</h3>
    <div class="seg" role="group" aria-label="Report type">
      <button type="button" aria-pressed={which === 'dot'} onclick={() => (which = 'dot')}>DOT summary</button>
      <button type="button" aria-pressed={which === 'board'} onclick={() => (which = 'board')}>Board view</button>
    </div>
    <p class="help">
      {which === 'dot'
        ? 'A short summary for DOT and elected officials: headline numbers, top stretches and streets, shared streets and what we ask.'
        : 'For a board meeting: a map, full totals and the full ranked list.'}
    </p>
    <button type="button" class="primary" onclick={() => onprint(which)}>Open printable report</button>
    <p class="help">Your browser's print window opens. Choose "Save as PDF" as the destination.</p>

    <h3>CSV downloads</h3>
    <div class="row">
      <button type="button" onclick={stretchesCsv}>Stretches (CSV)</button>
      <button type="button" onclick={blocksCsv}>Blocks (CSV)</button>
      {#if !older}<button type="button" onclick={crashesCsv}>Crashes (CSV)</button>{/if}
    </div>
    {#if older}<p class="help">Crash dots show current data only.</p>{/if}
    <p class="status" role="status" aria-live="polite">{status}</p>

    <div class="foot"><button type="button" onclick={() => dlg.close()}>Close</button></div>
  </div>
</dialog>

<style>
  dialog { border: 0; padding: 0; border-radius: 10px; max-width: min(34rem, calc(100vw - 2rem)); width: 100%; color: var(--ink); box-shadow: 0 10px 40px rgba(0, 0, 0, 0.35); }
  dialog::backdrop { background: rgba(15, 31, 61, 0.55); }
  .box { padding: 1.25rem 1.4rem 1rem; }
  h2 { margin: 0; font-size: 1.25rem; color: var(--navy); }
  h3 { margin: 1.1rem 0 0.4rem; font-size: 1rem; }
  .sub, .help { margin: 0.25rem 0 0.6rem; font-size: 0.9rem; color: var(--muted); }
  .seg { display: flex; border: 2px solid var(--navy); border-radius: 6px; overflow: hidden; }
  .seg button { flex: 1; font: inherit; font-weight: 600; padding: 0.45rem; cursor: pointer; background: #fff; color: var(--navy); border: 0; }
  .seg button[aria-pressed='true'] { background: var(--navy); color: #fff; }
  /* inset ring: .seg clips overflow; navy on white and white on navy are both above 3:1 */
  .seg button:focus-visible { outline-offset: -3px; }
  .seg button[aria-pressed='true']:focus-visible { outline-color: #fff; }
  .row { display: flex; flex-wrap: wrap; gap: 0.5rem; }
  button { font: inherit; font-weight: 600; padding: 0.45rem 0.9rem; border-radius: 6px; border: 2px solid var(--navy); background: #fff; color: var(--navy); cursor: pointer; }
  button.primary { background: var(--area-dark); border-color: var(--area-dark); color: #fff; }
  .status { min-height: 1.3rem; margin: 0.6rem 0 0; font-size: 0.9rem; }
  .foot { display: flex; justify-content: flex-end; margin-top: 0.5rem; }
</style>
