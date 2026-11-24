<script lang="ts">
  import type { SnapshotIndex } from './types';

  let { index, current, onpick }: {
    index: SnapshotIndex; current: string | null; onpick: (date: string | null) => void;
  } = $props();
  const value = $derived(current ?? index.latest);
</script>

{#if index.dates.length > 1}
  <label class="snap">
    <span>Snapshot</span>
    <select {value} onchange={(e) => onpick(e.currentTarget.value === index.latest ? null : e.currentTarget.value)}>
      {#each index.dates as d (d)}
        <option value={d} selected={d === value}>{d}{d === index.latest ? ' (latest)' : ''}</option>
      {/each}
    </select>
  </label>
{/if}

<style>
  .snap { display: inline-flex; align-items: center; gap: 0.4rem; font-size: 0.875rem; color: #cbd5e1; }
  select { font: inherit; font-size: 0.875rem; color: #fff; background: transparent; border: 1px solid #94a3b8; border-radius: 6px; padding: 0.3rem 0.4rem; cursor: pointer; }
  option { color: var(--ink); }
</style>
