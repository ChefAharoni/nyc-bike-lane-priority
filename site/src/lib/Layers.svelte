<script lang="ts">
  export interface LayerVis {
    priority: boolean; lanes: boolean; crashes: boolean; area: boolean; boards: boolean; districts: boolean;
  }
  let { vis, crashesDisabled = false, onchange }: {
    vis: LayerVis; crashesDisabled?: boolean; onchange: (key: keyof LayerVis, on: boolean) => void;
  } = $props();
  const items: { key: keyof LayerVis; label: string; swatch: string }[] = [
    { key: 'priority', label: 'Priority blocks', swatch: 'sw-pri' },
    { key: 'lanes', label: 'Bike lanes today', swatch: 'sw-lane' },
    { key: 'crashes', label: 'Crashes (zoom in)', swatch: 'sw-crash' },
    { key: 'area', label: 'Area outline', swatch: 'sw-area' },
    { key: 'boards', label: 'Community Boards', swatch: 'sw-boards' },
    { key: 'districts', label: 'Council Districts', swatch: 'sw-districts' },
  ];
  // On phones the panel starts collapsed behind a button; on wider screens CSS always shows it.
  let open = $state(typeof matchMedia === 'function' ? !matchMedia('(max-width: 767px)').matches : true);
</script>

<div class="layers">
  <button type="button" class="toggle" aria-expanded={open} aria-controls="layer-list" onclick={() => (open = !open)}>Layers</button>
  <fieldset id="layer-list" class:collapsed={!open}>
    <legend>Layers</legend>
    {#each items as it (it.key)}
      {@const off = it.key === 'crashes' && crashesDisabled}
      <label class:off>
        <input type="checkbox" checked={vis[it.key] && !off} disabled={off}
          onchange={(e) => onchange(it.key, e.currentTarget.checked)} />
        <span class="sw {it.swatch}" aria-hidden="true"></span>
        {it.label}
      </label>
    {/each}
    {#if crashesDisabled}<p class="note">Crash dots show current data only.</p>{/if}
  </fieldset>
</div>

<style>
  .layers { position: absolute; top: 0.6rem; right: 0.6rem; z-index: 2; }
  fieldset { margin: 0; background: #fff; border: 1px solid var(--line);
    border-radius: 8px; padding: 0.4rem 0.7rem 0.5rem; box-shadow: 0 1px 4px rgb(0 0 0 / 0.2); font-size: 0.875rem; }
  legend { font-weight: 700; color: var(--navy); padding: 0 0.25rem; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; }
  label { display: flex; align-items: center; gap: 0.45rem; padding: 0.2rem 0; cursor: pointer; white-space: nowrap; }
  label.off { color: #98a2b3; cursor: not-allowed; }
  input { width: 1.05rem; height: 1.05rem; accent-color: var(--area); margin: 0; }
  .note { margin: 0.2rem 0 0; max-width: 11rem; font-size: 0.8rem; color: var(--muted); }
  .toggle { display: none; font: inherit; font-weight: 700; font-size: 0.875rem; color: var(--navy); background: #fff; border: 1px solid var(--line);
    border-radius: 8px; padding: 0.45rem 0.8rem; box-shadow: 0 1px 4px rgb(0 0 0 / 0.2); cursor: pointer; margin-left: auto; }
  .sw { display: inline-block; width: 1.1rem; height: 0.28rem; border-radius: 2px; }
  .sw-pri { background: linear-gradient(90deg, var(--t1) 50%, var(--t2) 50%); }
  .sw-lane { background: var(--ok); }
  .sw-crash { height: 0.6rem; width: 0.6rem; border-radius: 50%; background: #7f1d1d; margin: 0 0.25rem; }
  .sw-area { background: repeating-linear-gradient(90deg, var(--area) 0 4px, transparent 4px 6px); }
  .sw-boards { background: #475569; height: 0.18rem; }
  .sw-districts { background: repeating-linear-gradient(90deg, #7c3aed 0 5px, transparent 5px 7px); height: 0.18rem; }
  @media (max-width: 767px) {
    .layers { display: flex; flex-direction: column; align-items: flex-end; gap: 0.35rem; }
    .toggle { display: block; }
    fieldset.collapsed { display: none; }
    legend { display: none; }
  }
</style>
