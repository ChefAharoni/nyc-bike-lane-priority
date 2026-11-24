<script lang="ts">
  import type { AreaTotals } from './types';
  import { fmtInt } from './format';

  let { totals, label }: { totals: AreaTotals; label: string } = $props();
  const items = $derived([
    { n: totals.crashes_5y, l: 'bike crashes, 5 years' },
    { n: totals.injured_5y, l: 'injured' },
    { n: totals.killed_5y, l: 'killed' },
    { n: totals.tier1_blocks, l: 'priority blocks with no bike lane' },
    { n: totals.shared_stretches, l: 'stretches shared with neighbors' },
  ]);
</script>

<section class="totals" aria-label="Totals for {label}">
  <h2>{label}</h2>
  <dl>
    {#each items as it (it.l)}
      <div><dt>{it.l}</dt><dd>{fmtInt(it.n)}</dd></div>
    {/each}
  </dl>
</section>

<style>
  h2 { margin: 0 0 0.5rem; font-size: 1.15rem; }
  dl { margin: 0; display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem 0.75rem; }
  div { min-width: 0; }
  dd { margin: 0; font-size: 1.35rem; font-weight: 800; font-variant-numeric: tabular-nums; order: -1; }
  div { display: flex; flex-direction: column; }
  dt { font-size: 0.8rem; color: var(--muted); line-height: 1.25; }
</style>
