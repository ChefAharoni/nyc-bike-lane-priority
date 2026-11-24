<script lang="ts">
  import type { Area, AreaKind } from './types';
  import { matchArea, sortAreas } from './format';

  let { kind, areas, areaId, onpick }: {
    kind: AreaKind; areas: Area[]; areaId: string | null; onpick: (id: string | null) => void;
  } = $props();

  let open = $state(false);
  let query = $state('');
  let active = $state(0);
  let input: HTMLInputElement | undefined = $state();
  let trigger: HTMLButtonElement | undefined = $state();
  const refocus = () => setTimeout(() => trigger?.focus(), 0);
  const uid = Math.random().toString(36).slice(2, 8);

  const sorted = $derived(sortAreas(areas));
  const current = $derived(areas.find((a) => a.id === areaId) ?? null);
  // Option list: "Citywide" first (null id), then matching areas.
  const options = $derived<{ id: string | null; label: string }[]>([
    ...(query.trim() === '' || 'citywide'.startsWith(query.trim().toLowerCase())
      ? [{ id: null, label: 'Citywide' }] : []),
    ...matchArea(sorted, query).map((a) => ({ id: a.id, label: a.name })),
  ]);

  function show() {
    open = true; query = '';
    const i = options.findIndex((o) => o.id === areaId);
    active = i < 0 ? 0 : i;
    queueMicrotask(() => input?.focus());
  }
  function pick(i: number) {
    const o = options[i];
    if (!o) return;
    open = false;
    onpick(o.id);
    refocus();
  }
  function key(e: KeyboardEvent) {
    if (e.key === 'ArrowDown') { e.preventDefault(); active = Math.min(active + 1, options.length - 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); active = Math.max(active - 1, 0); }
    else if (e.key === 'Enter') { e.preventDefault(); pick(active); }
    else if (e.key === 'Escape') { open = false; refocus(); }
  }
  $effect(() => {
    if (!open) return;
    document.getElementById(`${uid}-o${active}`)?.scrollIntoView({ block: 'nearest' });
  });
</script>

<div class="picker">
  {#if !open}
    <button type="button" class="trigger" aria-haspopup="listbox" aria-label="Area: {current ? current.name : 'Citywide'}" bind:this={trigger} onclick={show}>
      <span>{current ? current.name : 'Citywide'}</span>
      <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" stroke-width="2"/></svg>
    </button>
  {:else}
    <input
      bind:this={input}
      bind:value={query}
      class="search"
      role="combobox"
      aria-label={kind === 'cb' ? 'Search community boards' : 'Search council districts'}
      aria-expanded="true"
      aria-controls="{uid}-list"
      aria-activedescendant="{uid}-o{active}"
      placeholder={kind === 'cb' ? 'Type a board, like 9' : 'Type a district, like 40'}
      autocomplete="off"
      oninput={() => (active = 0)}
      onkeydown={key}
      onblur={() => setTimeout(() => (open = false), 120)}
    />
    <ul class="list" id="{uid}-list" role="listbox" aria-label="Areas">
      {#each options as o, i (o.id ?? 'citywide')}
        <li
          id="{uid}-o{i}"
          role="option"
          aria-selected={o.id === areaId}
          class:active={i === active}
          onmousedown={(e) => { e.preventDefault(); pick(i); }}
        >{o.label}</li>
      {:else}
        <li class="none" role="presentation">No area matches "{query}".</li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .picker { position: relative; min-width: 12.5rem; }
  .trigger, .search {
    width: 100%; height: 2.25rem; padding: 0 0.75rem; border-radius: 6px; font: inherit; font-weight: 600;
    background: #fff; color: var(--ink); border: 2px solid transparent;
  }
  .trigger { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; cursor: pointer; }
  .search { border-color: var(--area); outline: none; }
  .list {
    position: absolute; z-index: 20; top: calc(100% + 4px); left: 0; min-width: 100%; width: max-content; max-width: 90vw;
    max-height: 60vh; overflow: auto; margin: 0; padding: 0.25rem; list-style: none;
    background: #fff; color: var(--ink); border-radius: 8px; box-shadow: 0 8px 28px rgb(15 23 42 / 0.28);
  }
  li { padding: 0.55rem 0.7rem; border-radius: 5px; cursor: pointer; }
  li.active { background: var(--area-soft); }
  li[aria-selected='true'] { font-weight: 700; }
  li.none { color: var(--muted); cursor: default; }
</style>
