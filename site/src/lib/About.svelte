<script lang="ts">
  import type { Areas, Meta } from './types';
  import { fmtDate, fmtInt } from './format';

  let { meta, areas }: { meta: Meta | null; areas: Areas | null } = $props();

  // Fixed rules of the score (not data): a death counts 10, an injury 1, and older crashes count half.
  const DEATH = 10;
  const INJURY = 1;
  const HALF = 0.5;
  const example = { killed: 1, injured: 6, old: 1 };
  const exampleScore = example.killed * DEATH + (example.injured - example.old) * INJURY + example.old * INJURY * HALF;

  type Audience = 'public' | 'decision';
  let audience = $state<Audience>('public');

  const OD = 'https://data.cityofnewyork.us/d/';
  const sources: { name: string; id: string; what: string }[] = [
    { name: 'Motor Vehicle Collisions: Crashes', id: 'h9gi-nx95', what: 'where and when each crash happened, and the street names in the police report' },
    { name: 'Motor Vehicle Collisions: Persons', id: 'f55k-p6yu', what: 'who was hurt, and whether they were on a bicycle, e-bike or e-scooter' },
    { name: 'Motor Vehicle Collisions: Vehicles', id: 'bm4k-52h4', what: 'the type of each vehicle, used to tell e-bikes and e-scooters from mopeds' },
    { name: 'Bicycle Routes', id: 'mzxg-pwib', what: 'every bike lane and shared lane marking, with install and removal dates' },
    { name: 'LION street map', id: '2v4z-66xt', what: 'the street blocks that crashes are matched to' },
    { name: 'City Council Districts', id: '872g-cjhh', what: 'district boundaries' },
    { name: 'Community Districts', id: '5crt-au7u', what: 'Community Board boundaries' },
  ];
  const day = (d: string | undefined) => (d ? fmtDate(d.slice(0, 10)) : '');
  const sourceDate = (key: string) => day(meta?.sources[key]);
  const srcKey = ['crashes', 'persons', 'vehicles', 'routes', 'lion', 'council', 'community'];
</script>

<main class="about">
  <h1>About this data</h1>
  <p class="lede">
    This site ranks New York City street blocks by how many bike riders were hurt there without a protected bike lane.
    This page explains where the numbers come from and where they are weak.
  </p>

  <div class="seg" role="group" aria-label="Who is reading">
    <button type="button" aria-pressed={audience === 'public'} onclick={() => (audience = 'public')}>Public</button>
    <button type="button" aria-pressed={audience === 'decision'} onclick={() => (audience = 'decision')}>Decision makers</button>
  </div>
  <p class="switchnote">The switch changes what is stressed. The facts are the same in both.</p>

  {#if !meta}
    <p class="msg">Loading the numbers…</p>
  {:else}
    <section class="lead" aria-label={audience === 'public' ? 'For the press and public' : 'For decision makers'}>
      {#if audience === 'public'}
        <h2>If you are writing or reading about a street</h2>
        <ul>
          <li>Say the time window out loud: the last five years, {fmtDate(meta.window_start)} to {fmtDate(meta.data_date)}. Not "ever".</li>
          <li>A block is a small sample. For a story about a street, use the Whole streets view or a stretch, which adds up neighboring blocks.</li>
          <li>The ranking shows where riders were hurt with no protection. It does not say a lane would have prevented each crash.</li>
        </ul>
      {:else}
        <h2>If you are deciding where to act</h2>
        <ul>
          <li>Start with Tier 1, then Tier 2. Look for stretches, where many blocks in a row score high, over single blocks.</li>
          <li>Stretches that cross boards or districts are tagged with every area they touch. Those are the places to coordinate across offices.</li>
          <li>This is a starting list for a conversation with DOT, not a design. Cost, parking, traffic and lane design need engineering review.</li>
        </ul>
      {/if}
    </section>

    <nav aria-label="On this page">
      <ul class="toc">
        <li><a href="#a-crash">What counts</a></li>
        <li><a href="#a-match">Matching</a></li>
        <li><a href="#a-tiers">Tiers</a></li>
        <li><a href="#a-score">Score</a></li>
        <li><a href="#a-shapes">Streets</a></li>
        <li><a href="#a-areas">Areas</a></li>
        <li><a href="#a-time">Dates</a></li>
        <li><a href="#a-limits">Limits</a></li>
        <li><a href="#a-sources">Sources</a></li>
      </ul>
    </nav>

    <section id="a-crash">
      <h2>What counts as a bike crash</h2>
      <p>
        A bike crash is a police-reported crash where at least one person on a bicycle, e-bike or e-scooter was injured or killed.
        Mopeds and motorcycles are left out. Crashes with no injury, near misses and crashes nobody reported are not in the data.
      </p>
      <p>
        The record holds {fmtInt(meta.counts.bike_crashes)} bike crashes over all years. The site scores the last five years, from
        {fmtDate(meta.window_start)} to {fmtDate(meta.data_date)}.
      </p>
      <h3>Crashes counted and all bike crashes</h3>
      <p>
        <strong>Crashes counted</strong> means bike crashes in the last 5 years matched to a street block with confidence, where the lane at the
        time was none, painted or shared. These drive the score and the ranked lists.
      </p>
      <p>
        The totals at the top of the map are wider. They count every bike crash in the area by its location, including crashes on streets that
        already had a protected lane and crashes that could not be matched to a block. Citywide that is {fmtInt(meta.citywide.crashes_5y)} crashes
        in the window, with {fmtInt(meta.citywide.killed_5y)} riders killed and {fmtInt(meta.citywide.injured_5y)} injured.
        So the totals are larger than the sum of the ranked lists.
      </p>
    </section>

    <section id="a-match">
      <h2>How a crash is matched to a street and its lane</h2>
      <p>
        Each crash has a point and the street names the police wrote down. A crash goes to the nearest block, within 30 meters (about 100 feet),
        whose street name matches the crash report, unless a differently named street is clearly closer. Then the match is marked medium confidence.
        A medium match can also mean the crash sits at a corner where the two streets have different lanes. A high match means the name agrees. Low matches, where only distance was available, are not scored.
      </p>
      <p>
        The lane is the one that existed on that block on the day of the crash, found from each bike route's install and removal dates. A lane built
        after a crash gives no credit to that crash. A lane removed later does not erase it.
      </p>
      <div class="note green">
        <strong>Hand check.</strong> Before launch we checked 30 crashes from the last 5 years: 10 where the lane at the time was none, 10 painted or shared, and 10 protected.
        Only high and medium confidence matches were drawn, and each was compared with street imagery from close to the crash date. All 30 had the
        right block and the right lane label: 30 of 30 correct, and 0 wrong "no lane" labels.
        {#if audience === 'decision'}It was a small sample of confident matches, so it supports trust in the method but does not give an exact error rate, and it did not test low confidence matches.{/if}
      </div>
    </section>

    <section id="a-tiers">
      <h2>Tiers</h2>
      <ul>
        <li><strong>Tier 1:</strong> no bike lane today. Ranked first.</li>
        <li><strong>Tier 2:</strong> a painted lane or a shared lane marking today. Nothing physical stops a car.</li>
        <li><strong>Protected:</strong> a physical barrier today. Not ranked, since it is already protected.</li>
      </ul>
      <p>
        Every Tier 1 block ranks above every Tier 2 block, even when a Tier 2 block has a higher score. Today the ranking has
        {fmtInt(meta.counts.ranked_blocks)} ranked blocks: {fmtInt(meta.counts.tier1_blocks)} in Tier 1 and {fmtInt(meta.counts.tier2_blocks)} in Tier 2.
      </p>
    </section>

    <section id="a-score">
      <h2>The score</h2>
      <p>
        Each block gets a score from the crashes counted on it. A death counts {DEATH}. An injury counts {INJURY}. Crashes since
        {fmtDate(meta.recent_start)} count in full, and crashes in years 3 to 5 count half.
      </p>
      <div class="calc" role="group" aria-label="Worked example">
        <div class="row"><span>{example.killed} death</span><span>{example.killed} × {DEATH} = {example.killed * DEATH}</span></div>
        <div class="row"><span>{example.injured - example.old} injuries in the last two years</span><span>{example.injured - example.old} × {INJURY} = {(example.injured - example.old) * INJURY}</span></div>
        <div class="row"><span>{example.old} injury in years 3 to 5, at half weight</span><span>{example.old} × {HALF} = {example.old * INJURY * HALF}</span></div>
        <div class="row"><span>Score</span><span>{exampleScore}</span></div>
      </div>
      <p>
        The weights are a judgment about harm, not a law of nature. A block can rank high because of one death, so look at the injuries and the
        neighboring blocks too.
        {#if audience === 'decision'}If your office weighs harm differently, the ranking can be run again with other weights.{/if}
      </p>
    </section>

    <section id="a-shapes">
      <h2>Blocks, stretches and whole streets</h2>
      <p>
        A <strong>block</strong> is one piece of street between two intersections. The <strong>Blocks</strong> view ranks these.
        A <strong>stretch</strong> joins neighboring blocks on the same street in the same tier, so a corridor reads as one item. A stretch can include up to 2 blocks in a row with no counted crash, so a quiet block does not break it.
        A <strong>whole street</strong> adds up every ranked block on a street name. The <strong>Streets</strong> view shows stretches by
        default, and the Stretches and Whole streets buttons switch between them.
        There are {fmtInt(meta.counts.stretches)} stretches in the ranking.
      </p>
      <p>
        A stretch that crosses an area boundary is shown whole and tagged with every board or district it crosses.
        {fmtInt(meta.citywide.shared_stretches)} stretches are shared this way. Area totals count only the crashes inside the area,
        so a shared stretch's own numbers can be larger than the part inside one board.
      </p>
    </section>

    <section id="a-areas">
      <h2>Community Boards and Council Districts</h2>
      <p>
        You can look at the city by the {areas ? areas.cb.length : 59} Community Boards or the {areas ? areas.cd.length : 51} Council Districts. A block belongs to the area that contains its midpoint.
        Parks and airports sit outside every board, so those blocks are assigned to the nearest board and marked "nearest board" in the detail panel.
      </p>
      <h3>Shared links</h3>
      <p>
        The address of the page keeps your area, date, view and selected street, so a link opens the same place. It does not keep the
        Whole streets button or the Shared with neighbors only box. Those return to their defaults when the link is opened.
      </p>
    </section>

    <section id="a-layers">
      <h2>Map layers</h2>
      <p>The Layers panel on the map turns each of these on or off. Turn them all off for a plain street map.</p>
      <ul>
        <li><strong>Priority blocks:</strong> red where there is no bike lane today, orange where there is only paint or a sharrow. Lines are drawn for the ranked streets or blocks in the list.</li>
        <li><strong>Bike lanes today:</strong> solid green for protected lanes, dashed green for painted lanes and sharrows, light green for off-street paths.</li>
        <li><strong>Crashes:</strong> one dot per bike crash in the last 5 years, colored by the lane at the time of the crash. Dots appear when you zoom in.</li>
        <li><strong>Area outline:</strong> the boundary of the board or district you picked.</li>
        <li><strong>Community Boards</strong> and <strong>Council Districts:</strong> every boundary in the city, with names when you zoom in. They are off at first.</li>
      </ul>
      <p>Zoomed out over the whole city, some quieter blocks are left out to keep the map readable. Every ranked block shows once you zoom in or pick an area.</p>
    </section>

    <section id="a-time">
      <h2>Dates, snapshots and reports</h2>
      <p>
        "Data through" is the date of the latest crash in the police data, {fmtDate(meta.data_date)}. The police publish with a lag, so the
        most recent days are usually incomplete and fill in later. The window is the five years from {fmtDate(meta.window_start)}.
      </p>
      <p>
        The site keeps a snapshot of the ranking every day for 90 days, then one per month. Use the date picker to see an older one.
        Snapshots are pruned over time, so a printed or saved report is the permanent record of what the numbers said on the day you made it.
      </p>
    </section>

    <section id="a-limits">
      <h2>Limits</h2>
      <ul>
        <li>
          Some crashes are not placed on a street block, so they are not in the ranking. Over all years, {fmtInt(meta.counts.unmatched_no_coords)} bike crashes have no coordinates
          (these are also missing from the map), and {fmtInt(meta.counts.unmatched_too_far)} more have coordinates but no street block within 30 meters.
        </li>
        <li>The lane today comes from the city's bike route data, a snapshot that can lag behind the street. Check on site before you rely on it.</li>
        <li>Ridership is not in the score. A street where few people ride can look safer only because fewer people are exposed.</li>
        <li>Only crashes with a hurt rider count. Unreported crashes and near misses are invisible here.</li>
        <li>A ranking says where riders were hurt. It does not predict crashes, estimate cost, or design a lane.</li>
        <li>A block belongs to one area by its midpoint, so a long street can appear in more than one area.</li>
      </ul>
    </section>

    <section id="a-sources">
      <h2>Data sources</h2>
      <p>All of these are NYC Open Data. Each name links to the dataset page.</p>
      <ul class="src">
        {#each sources as s, i (s.id)}
          <li>
            <a href={OD + s.id} rel="noopener">{s.name}</a>: {s.what}.
            {#if sourceDate(srcKey[i])}<span class="muted">Fetched {sourceDate(srcKey[i])}.</span>{/if}
          </li>
        {/each}
      </ul>
    </section>
  {/if}

  <p class="back"><a href="#/citywide">Back to the map</a></p>
</main>

<style>
  .about { flex: 1; min-height: 0; overflow-y: auto; width: 100%; box-sizing: border-box; padding: 1.5rem 1rem 3rem; max-width: 46rem; margin: 0 auto; line-height: 1.6; font-size: 1.0625rem; }
  h1 { margin: 0 0 0.5rem; font-size: clamp(1.75rem, 6vw, 2.25rem); color: var(--navy); }
  h2 { margin: 0 0 0.6rem; font-size: 1.35rem; color: var(--navy); }
  h3 { margin: 1.1rem 0 0.3rem; font-size: 1.05rem; }
  section { margin: 0 0 2.25rem; scroll-margin-top: 1rem; }
  p, ul { margin: 0 0 0.9rem; }
  ul { padding-left: 1.3rem; }
  li { margin-bottom: 0.4rem; }
  .lede { font-size: 1.15rem; }
  .seg { display: inline-flex; border: 2px solid var(--navy); border-radius: 6px; overflow: hidden; max-width: 100%; }
  .seg button { font: inherit; font-weight: 600; font-size: 0.95rem; padding: 0.55rem 1rem; min-height: 44px; cursor: pointer; background: #fff; color: var(--navy); border: 0; }
  .seg button[aria-pressed='true'] { background: var(--navy); color: #fff; }
  .seg button:focus-visible, a:focus-visible { outline: 3px solid var(--area); outline-offset: 2px; }
  .seg button:focus-visible { outline-color: var(--navy); outline-offset: -3px; }
  .seg button[aria-pressed='true']:focus-visible { outline-color: #fff; }
  .switchnote { font-size: 0.9rem; color: var(--muted); margin: 0.5rem 0 1.25rem; }
  .lead { background: var(--area-soft); border-left: 5px solid var(--area); padding: 0.9rem 1.1rem 0.3rem; border-radius: 0 8px 8px 0; }
  .toc { list-style: none; padding: 0; display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 0 0 2rem; }
  .toc a { display: block; padding: 0.4rem 0.85rem; border: 1px solid var(--line); border-radius: 999px; font-size: 0.9rem; font-weight: 600; text-decoration: none; color: var(--ink); }
  .note { border-left: 5px solid var(--ok); background: #f0fdf4; padding: 0.7rem 1rem; border-radius: 0 8px 8px 0; margin: 0 0 1rem; }
  .calc { border: 1px solid var(--line); border-radius: 10px; padding: 0.75rem 1rem; margin: 0 0 1rem; background: #fff; }
  .row { display: flex; justify-content: space-between; gap: 1rem; padding: 0.3rem 0; border-bottom: 1px dashed var(--line); }
  .row:last-child { border: 0; font-weight: 700; font-size: 1.15rem; padding-top: 0.6rem; }
  .row span:last-child { text-align: right; white-space: nowrap; }
  .src li { overflow-wrap: anywhere; }
  .muted, .msg { color: var(--muted); }
  a { color: var(--area-dark); }
  .back { margin-top: 1rem; }
</style>
