<script lang="ts">
  import { COUNTED_NOTE, endsProse, type ReportModel } from './report';
  import { areaTag, areaTagCity, fmtDate, fmtEnds, fmtInt, fmtScore, titleCase } from './format';
  import type { AreaKind } from './types';

  let { model, kind, mapImage, mapNote }: {
    model: ReportModel; kind: AreaKind; mapImage: string | null; mapNote: string | null;
  } = $props();

  const t = $derived(model.totals);
  const title = $derived(model.kind === 'dot' ? 'Bike lane priority: summary for DOT' : 'Bike lane priority: board view');
  const tags = (cbs: string[], cds: string[]) => (kind === 'cb' ? cbs.map((c) => (model.citywide ? areaTagCity(c) : areaTag('cb', c))) : cds.map((c) => areaTag('cd', c))).join(' · ');
  const lane = $derived(t.lane_at_crash_5y);
</script>

<article class="report">
  <header>
    <h1>{title}</h1>
    <p class="area">{model.areaName}</p>
    <p class="meta">Data through {fmtDate(model.dataDate)} · Window {model.window}</p>
  </header>

  <section>
    <h2>Headline numbers</h2>
    <table class="kv">
      <tbody>
        <tr><th scope="row">Bike crashes, 5 years</th><td>{fmtInt(t.crashes_5y)}</td></tr>
        <tr><th scope="row">Riders injured</th><td>{fmtInt(t.injured_5y)}</td></tr>
        <tr><th scope="row">Riders killed</th><td>{fmtInt(t.killed_5y)}</td></tr>
        <tr><th scope="row">Crashes with no bike lane at the time</th><td>{fmtInt(lane.none)}</td></tr>
        <tr><th scope="row">Ranked Tier 1 blocks (no bike lane today)</th><td>{fmtInt(t.tier1_blocks)}</td></tr>
        <tr><th scope="row">Ranked Tier 2 blocks (painted or shared lane only)</th><td>{fmtInt(t.tier2_blocks)}</td></tr>
        <tr><th scope="row">Stretches</th><td>{fmtInt(t.stretches)}</td></tr>
        <tr><th scope="row">Stretches shared with a neighboring area</th><td>{fmtInt(t.shared_stretches)}</td></tr>
      </tbody>
    </table>
    {#if model.kind === 'board'}
      <table class="kv">
        <caption>Lane at the time of the crash</caption>
        <tbody>
          <tr><th scope="row">No lane</th><td>{fmtInt(lane.none)}</td></tr>
          <tr><th scope="row">Painted lane</th><td>{fmtInt(lane.paint)}</td></tr>
          <tr><th scope="row">Shared lane marking</th><td>{fmtInt(lane.sharrow)}</td></tr>
          <tr><th scope="row">Protected lane</th><td>{fmtInt(lane.protected)}</td></tr>
          <tr><th scope="row">Unknown</th><td>{fmtInt(lane.unknown)}</td></tr>
        </tbody>
      </table>
    {/if}
  </section>

  {#if model.kind === 'board'}
    <section>
      <h2>Map</h2>
      {#if mapImage}
        <img class="map" src={mapImage} alt="Map of {model.areaName} showing ranked blocks" />
      {:else}
        <p class="note">{mapNote ?? 'The map image was not available.'}</p>
      {/if}
      <p class="note">The map shows the layers that were on when this report was made. Red is Tier 1 (no bike lane today). Orange is Tier 2 (painted lane or shared lane marking).</p>
    </section>
  {/if}

  {#if model.kind === 'dot'}
    <section>
      <h2>Top Tier 1 stretches (no bike lane)</h2>
      {#if model.topStretches.length}
        <table class="list">
          <thead><tr><th>#</th><th>Stretch</th><th>Blocks</th><th>Crashes counted</th><th>Killed</th><th>Score</th><th>Areas</th></tr></thead>
          <tbody>
            {#each model.topStretches as { item: s, areaRank } (s.stretch_id)}
              <tr>
                <td>{areaRank}</td>
                <td><strong>{titleCase(s.street)}</strong><br />{fmtEnds(s.from_street, s.to_street)}</td>
                <td>{fmtInt(s.blocks)}</td><td>{fmtInt(s.crashes_5y)}</td><td>{fmtInt(s.killed_5y)}</td>
                <td>{fmtScore(s.score)}</td><td>{tags(s.cbs, s.cds)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
        <p class="note">{COUNTED_NOTE}</p>
      {:else}
        <p class="note">No Tier 1 stretches in this area.</p>
      {/if}

      <h2>Top whole streets</h2>
      {#if model.topStreets.length}
        <table class="list">
          <thead><tr><th>#</th><th>Street</th><th>Blocks</th><th>Crashes counted</th><th>Killed</th><th>Score</th><th>Areas</th></tr></thead>
          <tbody>
            {#each model.topStreets as { item: s, areaRank } (s.street_key)}
              <tr>
                <td>{areaRank}</td><td><strong>{titleCase(s.street)}</strong>, {s.borough}</td>
                <td>{fmtInt(s.blocks)}</td><td>{fmtInt(s.crashes_5y)}</td><td>{fmtInt(s.killed_5y)}</td>
                <td>{fmtScore(s.score)}</td><td>{tags(s.cbs, s.cds)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
        <p class="note">{COUNTED_NOTE}</p>
      {:else}
        <p class="note">No Tier 1 streets in this area.</p>
      {/if}
    </section>

    <section>
      <h2>Stretches shared with neighboring areas</h2>
      {#if model.shared.length}
        <ul class="plain">
          {#each model.shared as { stretch: s, others } (s.stretch_id)}
            <li><strong>{titleCase(s.street)}</strong>, {endsProse(s.from_street, s.to_street)} (Tier {s.tier}; {fmtInt(s.blocks)} {s.blocks === 1 ? 'block' : 'blocks'}).
              Also in {others.join(', ')}.</li>
          {/each}
        </ul>
        {#if model.sharedNote}<p class="note">{model.sharedNote}</p>{/if}
      {:else}
        <p class="note">No stretches in this area cross into a neighboring area.</p>
      {/if}

      <h2>What we ask</h2>
      {#if model.asks.length}
        <ol>{#each model.asks as a (a)}<li>{a}</li>{/each}</ol>
      {:else}
        <p class="note">No Tier 1 stretch in this area is shared with a neighboring area.</p>
      {/if}
    </section>
  {:else}
    <section class="break">
      <h2>All stretches, ranked</h2>
      {#if model.fullList.length}
        <table class="list">
          <thead><tr><th>#</th><th>Stretch</th><th>Tier</th><th>Blocks</th><th>Crashes counted</th><th>Killed</th><th>Score</th><th>Areas</th></tr></thead>
          <tbody>
            {#each model.fullList as { item: s, areaRank } (s.stretch_id)}
              <tr>
                <td>{areaRank}</td>
                <td><strong>{titleCase(s.street)}</strong><br />{fmtEnds(s.from_street, s.to_street)}</td>
                <td class="tier">Tier {s.tier}</td><td>{fmtInt(s.blocks)}</td><td>{fmtInt(s.crashes_5y)}</td><td>{fmtInt(s.killed_5y)}</td>
                <td>{fmtScore(s.score)}</td><td>{tags(s.cbs, s.cds)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
        {#if model.listNote}<p class="note">{model.listNote}</p>{/if}
        <p class="note">{COUNTED_NOTE}</p>
      {:else}
        <p class="note">No ranked stretches in this area.</p>
      {/if}
    </section>
  {/if}

  <section>
    <h2>How these numbers are made</h2>
    <p>{model.methods}</p>
    <p class="link">Link to this view: <span class="url">{model.permalink}</span></p>
  </section>
</article>
