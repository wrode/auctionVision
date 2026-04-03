import { Show, For, createSignal, createMemo } from 'solid-js';
import { LotDetail as LotDetailType, EnrichmentOutput } from '../types';
import { TimeRemaining } from './TimeRemaining';
import { ActionBar } from './ActionBar';

interface LotDetailProps {
  lot: LotDetailType;
  onAction?: (action: string) => void;
}

function fmt(value: number | null | undefined, currency?: string | null): string {
  if (value == null) return '\u2014';
  const sym = currency === 'EUR' ? '\u20AC' : currency === 'SEK' ? 'kr\u00A0' : currency === 'NOK' ? 'kr\u00A0' : currency ? `${currency}\u00A0` : '';
  return `${sym}${value.toLocaleString()}`;
}

function fmtCompact(value: number | null | undefined, currency?: string | null): string {
  if (value == null) return '\u2014';
  const sym = currency === 'EUR' ? '\u20AC' : currency === 'SEK' ? 'kr' : currency === 'NOK' ? 'kr' : currency ?? '';
  if (value >= 10000) return `${sym}${(value / 1000).toFixed(0)}K`;
  if (value >= 1000) return `${sym}${(value / 1000).toFixed(1)}K`;
  return `${sym}${value.toLocaleString()}`;
}

function getAgent(enrichments: EnrichmentOutput[] | undefined, agent: string): Record<string, any> | null {
  return enrichments?.find(e => e.agent_name === agent)?.output_json ?? null;
}

function pct(v: number | null | undefined): string { return `${Math.round((v ?? 0) * 100)}%`; }

type TabId = 'analysis' | 'pricing' | 'market' | 'details' | 'raw';

/* ── Score Gauge ── */
const R = 18;
const C = 2 * Math.PI * R; // ~113.1

function Gauge(props: { value: number | null | undefined; label: string; color: string }) {
  const v = () => props.value ?? 0;
  return (
    <div class="ld-gauge">
      <svg viewBox="0 0 48 48" class="ld-gauge-svg">
        <circle cx="24" cy="24" r={R} class="ld-gauge-track" />
        <circle
          cx="24" cy="24" r={R}
          class="ld-gauge-arc"
          style={{
            'stroke-dasharray': String(C),
            'stroke-dashoffset': String(C * (1 - v())),
            stroke: props.color
          }}
        />
      </svg>
      <span class="ld-gauge-num">{Math.round(v() * 100)}</span>
      <span class="ld-gauge-lbl">{props.label}</span>
    </div>
  );
}

/* ── Main Component ── */
export const LotDetail = (props: LotDetailProps) => {
  const [selImg, setSelImg] = createSignal(props.lot.image_url || '');
  const [expanded, setExpanded] = createSignal<Set<string>>(new Set());
  const toggle = (s: string) => { const e = new Set(expanded()); e.has(s) ? e.delete(s) : e.add(s); setExpanded(e); };

  const imgs = () => {
    const all = [props.lot.image_url, ...(props.lot.images || []).map(i => i.url)].filter((u): u is string => !!u);
    return [...new Set(all)];
  };

  const pf = () => props.lot.parsed_fields;
  const cur = () => pf()?.currency ?? props.lot.currency;
  const attr = () => getAgent(props.lot.enrichments, 'attribution');
  const arb = () => getAgent(props.lot.enrichments, 'arbitrage');
  const taste = () => getAgent(props.lot.enrichments, 'taste');
  const wild = () => getAgent(props.lot.enrichments, 'wildcard');

  const hasAnalysis = () =>
    attr()?.designer_candidate || attr()?.object_type || attr()?.era ||
    taste()?.mode || wild()?.reasons?.length ||
    pf()?.raw_designer_mentions?.length || pf()?.raw_material_mentions?.length;

  const hasEnrich = () =>
    (props.lot.enrichments?.length ?? 0) > 0 || props.lot.ai_value_low != null ||
    props.lot.buyer_profile != null || props.lot.listing != null;

  const hasMarket = () =>
    props.lot.best_market || props.lot.buyer_profile || props.lot.listing || props.lot.inspection_checklist?.length;

  const hasDetails = () =>
    pf()?.description || pf()?.condition_text || pf()?.dimensions_text || pf()?.provenance_text ||
    pf()?.raw_designer_mentions?.length || pf()?.raw_material_mentions?.length;

  const hasRaw = () =>
    hasEnrich() || (props.lot.fetch_history && props.lot.fetch_history.length > 0);

  const hasScores = () =>
    props.lot.scores.arbitrage != null || props.lot.scores.taste != null || props.lot.scores.wildcard != null;

  const vtabs = createMemo((): { id: TabId; label: string }[] =>
    ([
      { id: 'analysis' as TabId, label: 'Analysis', v: !!hasAnalysis() },
      { id: 'pricing' as TabId, label: 'Pricing', v: true },
      { id: 'market' as TabId, label: 'Market', v: !!hasMarket() },
      { id: 'details' as TabId, label: 'Details', v: !!hasDetails() },
      { id: 'raw' as TabId, label: 'Raw', v: !!hasRaw() },
    ]).filter(t => t.v).map(({ id, label }) => ({ id, label }))
  );

  const [tab, setTab] = createSignal<TabId>(vtabs()[0]?.id ?? 'pricing');

  return (
    <div class="ld">
      {/* ═══ LEFT ═══ */}
      <div class="ld-left">
        <div class="ld-gallery">
          <Show
            when={selImg()}
            fallback={<div class="ld-no-img"><span>No image available</span></div>}
          >
            <img src={selImg()} alt={props.lot.title} class="ld-hero" />
          </Show>
        </div>

        <Show when={imgs().length > 1}>
          <div class="ld-thumbstrip">
            <For each={imgs()}>
              {(img) => (
                <img
                  src={img} alt=""
                  class={`ld-thumb ${selImg() === img ? 'on' : ''}`}
                  onclick={() => setSelImg(img)}
                />
              )}
            </For>
          </div>
        </Show>

        <div class="ld-meta">
          <div class="ld-meta-row">
            <span class="ld-meta-k">Source</span>
            <span class="ld-meta-v">
              <Show when={props.lot.lot_url} fallback={props.lot.source}>
                <a href={props.lot.lot_url!} target="_blank" rel="noopener noreferrer">{props.lot.source}</a>
              </Show>
            </span>
          </div>
          <Show when={pf()?.auction_house_name}>
            <div class="ld-meta-row">
              <span class="ld-meta-k">House</span>
              <span class="ld-meta-v">{pf()!.auction_house_name}</span>
            </div>
          </Show>
          <Show when={pf()?.seller_location}>
            <div class="ld-meta-row">
              <span class="ld-meta-k">Location</span>
              <span class="ld-meta-v">{pf()!.seller_location}</span>
            </div>
          </Show>
          <Show when={pf()?.category_raw}>
            <div class="ld-meta-row">
              <span class="ld-meta-k">Category</span>
              <span class="ld-meta-v">{pf()!.category_raw}</span>
            </div>
          </Show>
        </div>

        <div class="ld-actions" onclick={(e) => e.stopPropagation()}>
          <ActionBar lot={props.lot} onAction={props.onAction} />
        </div>
      </div>

      {/* ═══ RIGHT ═══ */}
      <div class="ld-right">
        <h1 class="ld-title">{props.lot.title}</h1>

        {/* ── Signal Bar ── */}
        <div class="ld-signal">
          <Show when={hasScores()}>
            <div class="ld-gauge-row">
              <Show when={props.lot.scores.arbitrage != null}>
                <Gauge value={props.lot.scores.arbitrage} label="ARB" color="#00c853" />
              </Show>
              <Show when={props.lot.scores.taste != null}>
                <Gauge value={props.lot.scores.taste} label="TASTE" color="#ffab00" />
              </Show>
              <Show when={props.lot.scores.wildcard != null}>
                <Gauge value={props.lot.scores.wildcard} label="WILD" color="#00bcd4" />
              </Show>
              <Show when={props.lot.scores.urgency != null}>
                <Gauge value={props.lot.scores.urgency} label="URG" color="#ff6e40" />
              </Show>
            </div>
            <div class="ld-signal-divider" />
          </Show>

          <div class="ld-sig-cells">
            <div class="ld-sig-cell">
              <span class="ld-sig-k">Bid</span>
              <span class="ld-sig-v">{fmt(props.lot.current_bid, cur())}</span>
            </div>
            <Show when={props.lot.estimate_low}>
              <div class="ld-sig-cell">
                <span class="ld-sig-k">Estimate</span>
                <span class="ld-sig-v">{fmtCompact(props.lot.estimate_low, cur())} – {fmtCompact(props.lot.estimate_high, cur())}</span>
              </div>
            </Show>
            <Show when={props.lot.ai_value_low}>
              <div class="ld-sig-cell ld-sig-gold">
                <span class="ld-sig-k">Fair Value</span>
                <span class="ld-sig-v">{fmtCompact(props.lot.ai_value_low, cur())} – {fmtCompact(props.lot.ai_value_high, cur())}</span>
                <Show when={props.lot.estimate_confidence}>
                  <span class="ld-sig-conf">{props.lot.estimate_confidence}</span>
                </Show>
              </div>
            </Show>
            <div class="ld-sig-cell ld-sig-time">
              <span class="ld-sig-k">Ends</span>
              <span class="ld-sig-v"><TimeRemaining endTime={props.lot.auction_end_time ?? undefined} showText={true} /></span>
            </div>
          </div>
        </div>

        {/* ── Tabs ── */}
        <div class="ld-tabs">
          <For each={vtabs()}>
            {(t) => (
              <button class={`ld-tab ${tab() === t.id ? 'on' : ''}`} onclick={() => setTab(t.id)}>
                {t.label}
              </button>
            )}
          </For>
        </div>

        <div class="ld-panel">
          {/* ═══ ANALYSIS ═══ */}
          <Show when={tab() === 'analysis'}>
            <Show when={hasAnalysis()} fallback={
              <div class="ld-empty"><span class="ld-empty-badge">Pending</span><p>Analysis runs automatically after enrichment</p></div>
            }>
              <div class="ld-field-grid">
                <Show when={attr()?.designer_candidate}>
                  <div class="ld-f"><span class="ld-fk">Designer</span><span class="ld-fv">{attr()!.designer_candidate}
                    <Show when={attr()!.designer_confidence}><span class="ld-conf">{pct(attr()!.designer_confidence)}</span></Show>
                  </span></div>
                </Show>
                <Show when={attr()?.producer_candidate}>
                  <div class="ld-f"><span class="ld-fk">Producer</span><span class="ld-fv">{attr()!.producer_candidate}</span></div>
                </Show>
                <Show when={attr()?.object_type}>
                  <div class="ld-f"><span class="ld-fk">Type</span><span class="ld-fv">{attr()!.object_type}</span></div>
                </Show>
                <Show when={attr()?.era}>
                  <div class="ld-f"><span class="ld-fk">Era</span><span class="ld-fv">{attr()!.era}</span></div>
                </Show>
                <Show when={attr()?.materials?.length}>
                  <div class="ld-f"><span class="ld-fk">Materials</span><span class="ld-fv">{attr()!.materials.join(', ')}</span></div>
                </Show>
              </div>

              <Show when={attr()?.risk_flags?.length}>
                <div class="ld-flags">
                  <For each={attr()!.risk_flags}>{(f) => <span class="ld-flag ld-flag-risk">{f}</span>}</For>
                </div>
              </Show>
              <Show when={attr()?.attribution_flags?.length}>
                <div class="ld-flags">
                  <For each={attr()!.attribution_flags}>{(f) => <span class="ld-flag ld-flag-note">{f}</span>}</For>
                </div>
              </Show>

              <Show when={taste()}>
                <div class="ld-section-line">Taste Profile</div>
                <Show when={taste()!.mode}>
                  <div class="ld-f"><span class="ld-fk">Match</span><span class={`ld-fv ld-taste-${taste()!.mode}`}>{taste()!.mode}</span></div>
                </Show>
                <Show when={taste()!.similar_to?.length}>
                  <div class="ld-f"><span class="ld-fk">Similar To</span><span class="ld-fv">{taste()!.similar_to.join(', ')}</span></div>
                </Show>
                <Show when={taste()!.reasons?.length}>
                  <ul class="ld-reasons"><For each={taste()!.reasons}>{(r) => <li>{r}</li>}</For></ul>
                </Show>
              </Show>

              <Show when={wild()}>
                <div class="ld-section-line">Wildcard Signals</div>
                <Show when={wild()!.reasons?.length}>
                  <ul class="ld-reasons"><For each={wild()!.reasons}>{(r) => <li>{r}</li>}</For></ul>
                </Show>
                <Show when={wild()!.risks?.length}>
                  <ul class="ld-reasons ld-reasons-risk"><For each={wild()!.risks}>{(r) => <li>{r}</li>}</For></ul>
                </Show>
              </Show>

              <Show when={pf()?.raw_designer_mentions?.length || pf()?.raw_material_mentions?.length}>
                <div class="ld-section-line">Parsed Mentions</div>
                <Show when={pf()?.raw_designer_mentions?.length}>
                  <div class="ld-f"><span class="ld-fk">Designers</span><span class="ld-fv">{pf()!.raw_designer_mentions!.join(', ')}</span></div>
                </Show>
                <Show when={pf()?.raw_material_mentions?.length}>
                  <div class="ld-f"><span class="ld-fk">Materials</span><span class="ld-fv">{pf()!.raw_material_mentions!.join(', ')}</span></div>
                </Show>
              </Show>
            </Show>
          </Show>

          {/* ═══ PRICING ═══ */}
          <Show when={tab() === 'pricing'}>
            {/* Price comparison cards */}
            <div class="ld-price-cards">
              <div class="ld-price-card">
                <span class="ld-pc-label">Current Bid</span>
                <span class="ld-pc-val">{fmt(props.lot.current_bid, cur())}</span>
              </div>
              <Show when={props.lot.estimate_low || props.lot.estimate_high}>
                <div class="ld-price-card">
                  <span class="ld-pc-label">Auction Estimate</span>
                  <span class="ld-pc-val">{fmt(props.lot.estimate_low, cur())} – {fmt(props.lot.estimate_high, cur())}</span>
                </div>
              </Show>
              <Show when={props.lot.ai_value_low || props.lot.ai_value_high}>
                <div class="ld-price-card ld-price-card-gold">
                  <span class="ld-pc-label">AI Fair Value</span>
                  <span class="ld-pc-val">{fmt(props.lot.ai_value_low, cur())} – {fmt(props.lot.ai_value_high, cur())}</span>
                  <Show when={props.lot.estimate_confidence}>
                    <span class="ld-pc-conf">{props.lot.estimate_confidence} confidence</span>
                  </Show>
                </div>
              </Show>
            </div>

            {/* Reasoning */}
            <Show when={props.lot.ai_value_basis}>
              <div class="ld-insight">
                <span class="ld-insight-label">Valuation Insight</span>
                <p>{props.lot.ai_value_basis}</p>
              </div>
            </Show>

            {/* Comparables table */}
            <Show when={props.lot.estimate_basis?.length}>
              <div class="ld-section-line">Comparable Sales</div>
              <div class="ld-comps">
                <div class="ld-comps-head">
                  <span>Platform</span><span>Description</span><span>Price</span>
                </div>
                <For each={props.lot.estimate_basis}>
                  {(ref) => (
                    <div class="ld-comps-row">
                      <span class="ld-comps-plat">{ref.platform || ref.source}</span>
                      <span class="ld-comps-desc">
                        {ref.url
                          ? <a href={ref.url} target="_blank" rel="noopener noreferrer">{ref.detail}</a>
                          : ref.detail}
                      </span>
                      <span class="ld-comps-price">{fmt(ref.price_eur, 'EUR')}</span>
                    </div>
                  )}
                </For>
              </div>
            </Show>

            {/* Arbitrage breakdown */}
            <Show when={arb()}>
              <div class="ld-section-line">Arbitrage Analysis</div>
              <div class="ld-field-grid">
                <Show when={arb()!.expected_resale_value}>
                  <div class="ld-f"><span class="ld-fk">Expected Resale</span><span class="ld-fv">{fmt(arb()!.expected_resale_value, cur())}</span></div>
                </Show>
                <Show when={arb()!.landed_cost_estimate}>
                  <div class="ld-f"><span class="ld-fk">Landed Cost</span><span class="ld-fv">{fmt(arb()!.landed_cost_estimate, cur())}</span></div>
                </Show>
                <Show when={arb()!.fair_value_range}>
                  <div class="ld-f"><span class="ld-fk">Fair Value Range</span><span class="ld-fv">{fmt(arb()!.fair_value_range!.low, cur())} – {fmt(arb()!.fair_value_range!.high, cur())}</span></div>
                </Show>
                <Show when={arb()!.estimated_margin_range}>
                  <div class="ld-f"><span class="ld-fk">Est. Margin</span><span class="ld-fv" style="color: #00c853; font-weight: 700;">{fmt(arb()!.estimated_margin_range!.low, cur())} – {fmt(arb()!.estimated_margin_range!.high, cur())}</span></div>
                </Show>
              </div>
              <Show when={arb()!.reasons?.length}>
                <ul class="ld-reasons"><For each={arb()!.reasons}>{(r) => <li>{r}</li>}</For></ul>
              </Show>
            </Show>
          </Show>

          {/* ═══ MARKET ═══ */}
          <Show when={tab() === 'market'}>
            <Show when={props.lot.best_market}>
              <div class="ld-f"><span class="ld-fk">Best Market</span><span class="ld-fv"><span class="ld-market-badge">{props.lot.best_market}</span>
                <Show when={props.lot.best_market_reasoning}><span class="ld-market-note">{props.lot.best_market_reasoning}</span></Show>
              </span></div>
            </Show>
            <Show when={props.lot.buyer_profile}>
              <div class="ld-f"><span class="ld-fk">Buyer Profile</span><span class="ld-fv">{props.lot.buyer_profile!.who_buys}</span></div>
              <div class="ld-f"><span class="ld-fk">Sell Where</span><span class="ld-fv">{props.lot.buyer_profile!.sell_where}</span></div>
              <Show when={props.lot.buyer_profile!.demand_level}>
                <div class="ld-f"><span class="ld-fk">Demand</span><span class={`ld-fv ld-demand-${props.lot.buyer_profile!.demand_level}`}>{props.lot.buyer_profile!.demand_level}</span></div>
              </Show>
            </Show>
            <Show when={props.lot.conviction}>
              <div class="ld-f"><span class="ld-fk">Conviction</span><span class={`ld-fv ld-conviction-${props.lot.conviction}`}>{props.lot.conviction}</span></div>
            </Show>

            <Show when={props.lot.listing}>
              <div class="ld-section-line">Resale Copy</div>
              <Show when={props.lot.listing!.resale_title}>
                <div class="ld-f"><span class="ld-fk">Title</span><span class="ld-fv" style="font-weight: 600">{props.lot.listing!.resale_title}</span></div>
              </Show>
              <Show when={props.lot.listing!.resale_description}>
                <div class="ld-insight"><p>{props.lot.listing!.resale_description}</p></div>
              </Show>
              <Show when={props.lot.listing!.tags?.length}>
                <div class="ld-flags"><For each={props.lot.listing!.tags}>{(t) => <span class="ld-flag ld-flag-tag">{t}</span>}</For></div>
              </Show>
            </Show>

            <Show when={props.lot.inspection_checklist?.length}>
              <div class="ld-section-line">Inspection Checklist</div>
              <ul class="ld-checklist">
                <For each={props.lot.inspection_checklist}>{(item) => <li>{item}</li>}</For>
              </ul>
            </Show>
          </Show>

          {/* ═══ DETAILS ═══ */}
          <Show when={tab() === 'details'}>
            <Show when={pf()?.description}>
              <div class="ld-insight"><span class="ld-insight-label">Description</span><p>{pf()!.description}</p></div>
            </Show>
            <div class="ld-field-grid">
              <Show when={pf()?.condition_text}>
                <div class="ld-f"><span class="ld-fk">Condition</span><span class="ld-fv">{pf()!.condition_text}</span></div>
              </Show>
              <Show when={pf()?.dimensions_text}>
                <div class="ld-f"><span class="ld-fk">Dimensions</span><span class="ld-fv">{pf()!.dimensions_text}</span></div>
              </Show>
            </div>
            <Show when={pf()?.provenance_text}>
              <div class="ld-insight"><span class="ld-insight-label">Provenance</span><p>{pf()!.provenance_text}</p></div>
            </Show>
            <Show when={pf()?.raw_designer_mentions?.length}>
              <div class="ld-f"><span class="ld-fk">Designer Mentions</span><span class="ld-fv">{pf()!.raw_designer_mentions!.join(', ')}</span></div>
            </Show>
            <Show when={pf()?.raw_material_mentions?.length}>
              <div class="ld-f"><span class="ld-fk">Materials</span><span class="ld-fv">{pf()!.raw_material_mentions!.join(', ')}</span></div>
            </Show>
          </Show>

          {/* ═══ RAW ═══ */}
          <Show when={tab() === 'raw'}>
            <Show when={hasEnrich()}>
              <For each={props.lot.enrichments}>
                {(en) => (
                  <div class="ld-raw-block">
                    <div class="ld-raw-header" onclick={() => toggle(en.agent_name)}>
                      <span class="ld-raw-name">{en.agent_name}</span>
                      <span class="ld-raw-meta">
                        <Show when={en.confidence != null}><span class="ld-conf">{pct(en.confidence)}</span></Show>
                        <span class={`ld-raw-chevron ${expanded().has(en.agent_name) ? 'open' : ''}`}>{'\u25BC'}</span>
                      </span>
                    </div>
                    <Show when={expanded().has(en.agent_name)}>
                      <pre class="ld-raw-json">{JSON.stringify(en.output_json, null, 2)}</pre>
                      <Show when={en.completed_at}>
                        <span class="ld-raw-ts">{new Date(en.completed_at!).toLocaleString()}</span>
                      </Show>
                    </Show>
                  </div>
                )}
              </For>
            </Show>
            <Show when={props.lot.fetch_history && props.lot.fetch_history.length > 0}>
              <div class="ld-section-line">Fetch History</div>
              <For each={props.lot.fetch_history}>
                {(rec) => (
                  <div class="ld-fetch-row">
                    <span class={`ld-fetch-dot ${rec.success ? 'ok' : 'err'}`} />
                    <span class="ld-fetch-type">{rec.fetch_type}</span>
                    <Show when={rec.http_status}><span class="ld-fetch-http">{rec.http_status}</span></Show>
                    <span class="ld-fetch-ts">{new Date(rec.fetched_at).toLocaleString()}</span>
                    <Show when={rec.error_message}><span class="ld-fetch-err">{rec.error_message}</span></Show>
                  </div>
                )}
              </For>
            </Show>
          </Show>
        </div>
      </div>
    </div>
  );
};
