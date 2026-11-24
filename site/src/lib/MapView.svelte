<script lang="ts">
  import { onMount, untrack } from 'svelte';
  import * as maplibregl from 'maplibre-gl';
  import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import { Protocol } from 'pmtiles';
  import Layers, { type LayerVis } from './Layers.svelte';
  import type { DataBundle } from './load';
  import type { Route } from './route';
  import type { Area, AreaKind, LaneAtCrash } from './types';
  import { titleCase } from './format';
  import { colors, laneWords, layerIds, priorityState, sourceIds, type BlockState } from './mapstyle';

  let { data, route, kind, area, crashSegments, crashesDisabled, highlightStretchIds = [], onselect }: {
    data: DataBundle; route: Route; kind: AreaKind; area: Area | null;
    crashSegments: string[] | null; crashesDisabled: boolean; highlightStretchIds?: string[];
    onselect: (type: 'stretch' | 'block', id: string) => void;
  } = $props();

  const BASEMAP = 'https://tiles.openfreemap.org/styles/positron';
  const CITY: [number, number, number, number] = [-74.26, 40.49, -73.70, 40.92];
  const PHONE = () => window.matchMedia('(max-width: 767px)').matches;

  let el: HTMLDivElement;
  let map: maplibregl.Map | null = null;
  let ready = $state(false);
  let vis = $state<LayerVis>({ priority: true, lanes: true, crashes: true, area: true });
  let prevCrashes: boolean | null = null;
  let applied = new Map<string, BlockState>();
  let gen = 0;
  let clickedId: string | null = null;

  const abs = (p: string) => new URL(`data/${p}`, location.href).href;

  async function basemapStyle(): Promise<maplibregl.StyleSpecification> {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), 6000);
    try {
      const res = await fetch(BASEMAP, { signal: ctl.signal });
      if (!res.ok) throw new Error(String(res.status));
      return (await res.json()) as maplibregl.StyleSpecification;
    } catch {
      return { version: 8, sources: {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#e8ecf1' } }] };
    } finally { clearTimeout(t); }
  }

  const tierColor: maplibregl.ExpressionSpecification = ['case',
    ['==', ['feature-state', 'tier'], 1], colors.tier1, ['==', ['feature-state', 'tier'], 2], colors.tier2, '#000000'];
  const hasState: maplibregl.ExpressionSpecification = ['!=', ['feature-state', 'tier'], null];
  const sel: maplibregl.ExpressionSpecification = ['==', ['feature-state', 'selected'], true];
  const zoomWidth = (a: number, b: number, selA: number, selB: number): maplibregl.ExpressionSpecification =>
    ['interpolate', ['linear'], ['zoom'], 10, ['case', sel, selA, a], 17, ['case', sel, selB, b]];

  function addLayers(m: maplibregl.Map) {
    m.addSource(sourceIds.blocks, { type: 'vector', url: `pmtiles://${abs('blocks.pmtiles')}`, promoteId: { blocks: 'segmentid' } });
    m.addSource(sourceIds.lanes, { type: 'vector', url: `pmtiles://${abs('bike_lanes.pmtiles')}` });
    m.addSource(sourceIds.crashes, { type: 'vector', url: `pmtiles://${abs('crashes.pmtiles')}` });
    m.addSource(sourceIds.areas, { type: 'geojson', data: abs('areas.geojson') });

    m.addLayer({ id: layerIds.area, type: 'line', source: sourceIds.areas, filter: ['==', ['get', 'id'], '__none__'],
      paint: { 'line-color': colors.area, 'line-width': 2.5, 'line-dasharray': [3, 2] } });
    m.addLayer({ id: layerIds.lanesOffstreet, type: 'line', source: sourceIds.lanes, 'source-layer': 'lanes',
      filter: ['==', ['get', 'onoff'], 'OFF'], layout: { 'line-cap': 'round' },
      paint: { 'line-color': '#86EFAC', 'line-width': 1, 'line-opacity': 0.5 } });
    m.addLayer({ id: layerIds.lanesPaint, type: 'line', source: sourceIds.lanes, 'source-layer': 'lanes',
      filter: ['all', ['==', ['get', 'onoff'], 'ON'], ['!=', ['get', 'facility'], 'protected']],
      paint: { 'line-color': colors.lane, 'line-width': ['interpolate', ['linear'], ['zoom'], 10, 1, 17, 2.5],
        'line-opacity': 0.6, 'line-dasharray': [2, 2] } });
    m.addLayer({ id: layerIds.lanesProtected, type: 'line', source: sourceIds.lanes, 'source-layer': 'lanes',
      filter: ['all', ['==', ['get', 'onoff'], 'ON'], ['==', ['get', 'facility'], 'protected']],
      paint: { 'line-color': colors.lane, 'line-width': ['interpolate', ['linear'], ['zoom'], 10, 1.5, 17, 4] } });
    m.addLayer({ id: layerIds.priorityCasing, type: 'line', source: sourceIds.blocks, 'source-layer': 'blocks',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#0f1f3d', 'line-width': zoomWidth(0, 0, 13, 22), 'line-opacity': ['case', sel, 1, 0] } });
    m.addLayer({ id: layerIds.priority, type: 'line', source: sourceIds.blocks, 'source-layer': 'blocks',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': tierColor, 'line-width': zoomWidth(2.5, 7, 7, 13),
        'line-opacity': ['case', ['!', hasState], 0, ['==', ['feature-state', 'inArea'], false], 0.35, 1] } });
    m.addLayer({ id: layerIds.crashes, type: 'circle', source: sourceIds.crashes, 'source-layer': 'crashes', minzoom: 12,
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 12, 3, 17, 6],
        'circle-color': ['match', ['get', 'lane'], 'none', colors.crash.none, 'paint', colors.crash.paint,
          'sharrow', colors.crash.sharrow, 'protected', colors.crash.protected, colors.crash.unknown],
        'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1, 'circle-opacity': 0.9 } });
  }

  function applyVis() {
    if (!ready || !map) return;
    const set = (ids: string[], on: boolean) => ids.forEach((id) => map!.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none'));
    set([layerIds.priority, layerIds.priorityCasing], vis.priority);
    set([layerIds.lanesProtected, layerIds.lanesPaint, layerIds.lanesOffstreet], vis.lanes);
    set([layerIds.crashes], vis.crashes && !crashesDisabled);
    set([layerIds.area], vis.area);
  }

  function esc(s: string) {
    return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);
  }

  function crashPopup(p: Record<string, unknown>): string {
    const lane = laneWords[(p.lane as LaneAtCrash) ?? 'unknown'] ?? 'Unknown';
    const street = p.street ? titleCase(String(p.street)) : 'Street not recorded';
    const date = p.date ? String(p.date).slice(0, 10) : 'Date not recorded';
    return `<div class="crash-pop"><strong>${esc(street)}</strong><br>${esc(date)}<br>` +
      `Injured: ${esc(String(p.injured ?? 0))} · Killed: ${esc(String(p.killed ?? 0))}<br>Lane at the time: ${esc(lane)}</div>`;
  }

  onMount(() => {
    let dead = false;
    // Bundling hides the library's own module URL, so point it at the emitted worker file.
    maplibregl.setWorkerUrl(new URL(workerUrl, location.href).href);
    const protocol = new Protocol();
    maplibregl.addProtocol('pmtiles', protocol.tile);
    basemapStyle().then((style) => {
      if (dead) return;
      const m = new maplibregl.Map({
        container: el, style, bounds: CITY, fitBoundsOptions: { padding: 20 },
        canvasContextAttributes: { preserveDrawingBuffer: true },
        attributionControl: { compact: true, customAttribution: Object.keys(style.sources).length ? undefined : '© OpenStreetMap contributors · OpenFreeMap' },
      } as maplibregl.MapOptions);
      map = m;
      if (import.meta.env.DEV || import.meta.env.MODE === 'test') (window as unknown as { __map: unknown }).__map = m;
      m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');
      m.on('error', (e) => { console.warn('Map error (data layers keep working):', e.error?.message ?? e); });
      m.once('load', () => {
        try { addLayers(m); } catch (e) { console.error(e); return; }
        ready = true;
      });
      m.on('click', (e) => {
        const r = 5;
        const feats = m.queryRenderedFeatures([[e.point.x - r, e.point.y - r], [e.point.x + r, e.point.y + r]],
          { layers: [layerIds.crashes, layerIds.priority].filter((id) => m.getLayer(id)) });
        const crash = feats.find((f) => f.layer.id === layerIds.crashes);
        if (crash && vis.crashes && !crashesDisabled) {
          new maplibregl.Popup({ closeButton: true, maxWidth: '260px' })
            .setLngLat((crash.geometry as unknown as { coordinates: [number, number] }).coordinates)
            .setHTML(crashPopup(crash.properties ?? {})).addTo(m);
          return;
        }
        const pri = feats.find((f) => f.layer.id === layerIds.priority && f.state && f.state.tier);
        if (!pri || !vis.priority) return;
        const seg = String(pri.properties?.segmentid ?? pri.id ?? '');
        if (!seg) return;
        const pick = (type: 'stretch' | 'block', id: string) => {
          // Only a change of selection reaches the camera effect, so only then mark the click as ours.
          clickedId = route.selection?.id === id ? null : id;
          onselect(type, id);
        };
        if (route.view === 'blocks') { pick('block', seg); return; }
        const s = stretchOf.get(seg);
        if (s) pick('stretch', s);
      });
      m.on('mousemove', (e) => {
        if (!m.getLayer(layerIds.priority)) return;
        const r = 4;
        const f = m.queryRenderedFeatures([[e.point.x - r, e.point.y - r], [e.point.x + r, e.point.y + r]],
          { layers: [layerIds.priority, layerIds.crashes] });
        m.getCanvas().style.cursor = f.some((x) => x.layer.id === layerIds.crashes || (x.state && x.state.tier)) ? 'pointer' : '';
      });
    });
    return () => {
      dead = true;
      map?.remove(); map = null; ready = false;
      maplibregl.removeProtocol('pmtiles');
    };
  });

  /** A PNG of the map fitted to a box, for the printed report. Null when the map is not ready in time. The camera goes back afterwards. */
  export async function snapshot(bbox: [number, number, number, number] | null, timeoutMs = 3000): Promise<string | null> {
    const m = map;
    if (!m || !ready) return null;
    const home = { center: m.getCenter(), zoom: m.getZoom(), bearing: m.getBearing(), pitch: m.getPitch() };
    try {
      const b = bbox ?? CITY;
      m.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: 30, duration: 0 });
      const done = await new Promise<boolean>((resolve) => {
        const t = setTimeout(() => resolve(false), timeoutMs);
        const check = () => {
          if (m.loaded() && !m.isMoving()) { clearTimeout(t); resolve(true); } else m.once('idle', check);
        };
        m.triggerRepaint();
        m.once('idle', check);
      });
      if (!done) return null;
      return m.getCanvas().toDataURL('image/png');
    } catch {
      return null;
    } finally {
      m.jumpTo(home);
    }
  }

  // segmentid -> stretch id (gap blocks included) for click selection in streets view.
  const stretchOf = $derived.by(() => {
    const m = new Map<string, string>();
    for (const s of data.stretches) for (const id of [...s.segmentids, ...s.gap_segmentids]) m.set(id, s.stretch_id);
    return m;
  });

  $effect(() => { vis; crashesDisabled; ready; applyVis(); });

  // "Show crashes": only the selected item's crash dots, and the layer turned on.
  $effect(() => {
    const segs = crashSegments;
    if (!ready || !map) return;
    map.setFilter(layerIds.crashes, segs ? ['in', ['get', 'segmentid'], ['literal', segs]] : null);
    // Turn the layer on for the selection, and give the reader's own choice back when it ends.
    untrack(() => {
      if (segs && prevCrashes === null) { prevCrashes = vis.crashes; vis.crashes = true; }
      else if (!segs && prevCrashes !== null) { vis.crashes = prevCrashes; prevCrashes = null; }
    });
  });

  // Feature state: apply only the difference from what is on the map, in frame-sized chunks.
  const wanted = $derived(priorityState(data.blocks, data.stretches, route.view, kind, route.areaId, route.selection, highlightStretchIds));
  $effect(() => {
    const next = wanted;
    if (!ready || !map) return;
    const m = map;
    const my = ++gen;
    const t0 = performance.now();
    // Each op records itself in `applied` as it runs, so a run cancelled between chunks leaves
    // `applied` equal to what is really on the map and the next run diffs against the truth.
    const ops: (() => void)[] = [];
    const ref = (id: string) => ({ source: sourceIds.blocks, sourceLayer: 'blocks', id });
    for (const id of [...applied.keys()]) {
      if (!next.has(id)) ops.push(() => { m.removeFeatureState(ref(id)); applied.delete(id); });
    }
    for (const [id, st] of next) {
      const old = applied.get(id);
      if (!old || old.tier !== st.tier || old.inArea !== st.inArea || old.selected !== st.selected) {
        ops.push(() => { m.setFeatureState(ref(id), { tier: st.tier, inArea: st.inArea, selected: st.selected }); applied.set(id, st); });
      }
    }
    const CHUNK = 4000;
    let i = 0;
    const run = () => {
      if (my !== gen || !map) return;
      const end = Math.min(ops.length, i + CHUNK);
      for (; i < end; i++) ops[i]();
      if (i < ops.length) requestAnimationFrame(run);
      else if (import.meta.env.DEV || import.meta.env.MODE === 'test') {
        (window as unknown as { __fsMs: number; __fsOps: number }).__fsMs = performance.now() - t0;
        (window as unknown as { __fsOps: number }).__fsOps = ops.length;
      }
    };
    run();
  });

  // Area outline filter and fit.
  $effect(() => {
    if (!ready || !map) return;
    map.setFilter(layerIds.area, area
      ? ['all', ['==', ['get', 'kind'], area.kind], ['==', ['get', 'id'], area.id]]
      : ['==', ['get', 'id'], '__none__']);
  });
  const pad = () => (PHONE() ? 24 : 40);
  // The camera follows ids, not objects: a reload or date change that rebuilds `route` or `data` does not re-fit.
  const areaKey = $derived(area ? `${area.kind}:${area.id}` : null);
  $effect(() => {
    areaKey;
    if (!ready || !map) return;
    const b = untrack(() => area?.bbox) ?? CITY;
    map.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: pad(), duration: 600 });
  });

  // A whole street picked in the list: fit to the combined box of its stretches.
  const hlKey = $derived(highlightStretchIds.length ? highlightStretchIds.join(',') : null);
  $effect(() => {
    hlKey;
    if (!ready || !map || !hlKey) return;
    const ids = new Set(untrack(() => highlightStretchIds));
    const bs = untrack(() => data.stretches).filter((s) => ids.has(s.stretch_id)).map((s) => s.bbox);
    if (!bs.length) return;
    const b = [Math.min(...bs.map((x) => x[0])), Math.min(...bs.map((x) => x[1])),
      Math.max(...bs.map((x) => x[2])), Math.max(...bs.map((x) => x[3]))];
    map.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: pad(), duration: 600, maxZoom: 17 });
  });

  // List (or link) selection zooms to the stretch or block.
  const selKey = $derived(route.selection ? `${route.selection.type}:${route.selection.id}` : null);
  $effect(() => {
    selKey;
    if (!ready || !map) return;
    const s = untrack(() => route.selection);
    if (!s) { clickedId = null; return; }
    if (clickedId === s.id) { clickedId = null; return; }
    clickedId = null;
    untrack(() => {
      if (s.type === 'stretch') {
        const st = data.stretches.find((x) => x.stretch_id === s.id);
        if (st) map!.fitBounds([[st.bbox[0], st.bbox[1]], [st.bbox[2], st.bbox[3]]], { padding: pad(), duration: 600, maxZoom: 17 });
      } else {
        const b = data.blocks.find((x) => x.segmentid === s.id);
        if (b) map!.flyTo({ center: b.mid, zoom: 17, duration: 600 });
      }
    });
  });
</script>

<div class="mapview" bind:this={el}></div>
<Layers {vis} {crashesDisabled} onchange={(k, on) => { if (k === 'crashes') prevCrashes = null; vis[k] = on; }} />

<style>
  .mapview { position: absolute; inset: 0; }
  :global(.crash-pop) { font-size: 0.875rem; line-height: 1.4; color: var(--ink); }
</style>
