import { createResource, createSignal, Show, For, createMemo, onMount, onCleanup } from 'solid-js';
import { useNavigate } from '@solidjs/router';
import { apiClient } from '../api';
import { ViewHeader } from '../components/ViewHeader';
import { AuctionCalendar, type DateRange } from '../components/AuctionCalendar';
import type { LotCard } from '../types';

type SortKey = 'arbitrage' | 'estimate' | 'resale' | 'earning' | 'timeLeft' | 'multiplier' | 'title' | 'demand';
type SortDir = 'asc' | 'desc';

type RegionFilter = '' | 'scandinavia' | 'sweden' | 'denmark' | 'germany' | 'uk' | 'other';

const REGION_COUNTRIES: Record<Exclude<RegionFilter, ''>, string[]> = {
  scandinavia: ['Sweden', 'Denmark', 'Norway', 'Finland'],
  sweden: ['Sweden'],
  denmark: ['Denmark'],
  germany: ['Germany'],
  uk: ['United Kingdom'],
  other: [],  // catch-all
};

const getCountry = (loc: string | null | undefined): string => {
  if (!loc) return '';
  const parts = loc.split(', ');
  return parts.length >= 2 ? parts[parts.length - 1] : '';
};

const matchesRegion = (loc: string | null | undefined, region: RegionFilter): boolean => {
  if (!region) return true;
  const country = getCountry(loc);
  if (region === 'other') {
    const allKnown = Object.values(REGION_COUNTRIES).flat();
    return !country || !allKnown.includes(country);
  }
  return REGION_COUNTRIES[region].includes(country);
};

export const BestBuys = () => {
  const navigate = useNavigate();
  const [viewData] = createResource(() =>
    apiClient.fetchView('best-buys', { limit: 500 }),
  );
  const [allLots] = createResource(() =>
    apiClient.fetchView('all-lots', { limit: 2000 }),
  );

  const [sortKey, setSortKey] = createSignal<SortKey>('arbitrage');
  const [sortDir, setSortDir] = createSignal<SortDir>('desc');
  const [now, setNow] = createSignal(Date.now());
  const [search, setSearch] = createSignal('');
  const [regionFilter, setRegionFilter] = createSignal<RegionFilter>('');
  const [dateRange, setDateRange] = createSignal<DateRange | null>(null);
  const [topNLimit, setTopNLimit] = createSignal<number | null>(null);

  onMount(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 30_000);
    onCleanup(() => window.clearInterval(interval));
  });

  const defaultSortDir = (key: SortKey): SortDir =>
    key === 'title' || key === 'timeLeft' ? 'asc' : 'desc';

  const toggleSort = (key: SortKey) => {
    if (sortKey() === key) {
      setSortDir(d => d === 'desc' ? 'asc' : 'desc');
    } else {
      setSortKey(key);
      setSortDir(defaultSortDir(key));
    }
  };

  const sortIndicator = (key: SortKey) => {
    if (sortKey() !== key) return '';
    return sortDir() === 'desc' ? ' \u25BC' : ' \u25B2';
  };

  const getResaleMid = (lot: LotCard) => {
    if (lot.ai_value_low != null && lot.ai_value_high != null) {
      return (lot.ai_value_low + lot.ai_value_high) / 2;
    }
    return null;
  };

  const getDisplayedResaleEstimate = (lot: LotCard) =>
    getResaleMid(lot) ?? lot.expected_resale_eur ?? null;

  const getMultiplier = (lot: LotCard) => {
    const resale = lot.expected_resale_eur
      ?? getResaleMid(lot);
    const cost = lot.landed_cost_eur
      ?? (lot.estimate_low != null && lot.estimate_low > 0 ? lot.estimate_low * 1.2 : null);
    if (resale != null && cost != null && cost > 0) {
      return resale / cost;
    }
    return null;
  };

  const getAssumedBid = (lot: LotCard) => {
    if (lot.current_bid != null) return lot.current_bid;
    if (lot.estimate_low != null && lot.estimate_low > 0) return lot.estimate_low / 2;
    return null;
  };

  const getEstimatedEarning = (lot: LotCard) => {
    const resale = getDisplayedResaleEstimate(lot);
    const assumedBid = getAssumedBid(lot);
    if (resale == null || assumedBid == null) return null;
    return resale - assumedBid;
  };

  const compareLotsByEstimatedEarning = (a: LotCard, b: LotCard) => {
    const av = getEstimatedEarning(a);
    const bv = getEstimatedEarning(b);
    if (av == null && bv == null) {
      return (b.scores.arbitrage ?? 0) - (a.scores.arbitrage ?? 0);
    }
    if (av == null) return 1;
    if (bv == null) return -1;
    if (bv !== av) return bv - av;
    return (b.scores.arbitrage ?? 0) - (a.scores.arbitrage ?? 0);
  };

  const getTimeLeftMs = (lot: LotCard) => {
    if (!lot.auction_end_time) return null;
    return new Date(lot.auction_end_time).getTime() - now();
  };

  // Base lots: filtered by search/region but NOT by date (calendar sees these)
  const baseLots = createMemo(() => {
    const lots = viewData()?.lots || [];
    const q = search().toLowerCase();

    return lots.filter(lot => {
      if (q && !lot.title.toLowerCase().includes(q)) return false;
      if (regionFilter() && !matchesRegion(lot.seller_location, regionFilter())) return false;
      return true;
    });
  });

  // Final lots: baseLots filtered by date, limited to top N, then sorted
  const filteredLots = createMemo(() => {
    let lots = baseLots();
    const dr = dateRange();

    if (dr) {
      lots = lots.filter(lot => {
        if (!lot.auction_end_time) return false;
        const d = lot.auction_end_time.slice(0, 10);
        return d >= dr.start && d <= dr.end;
      });
    }

    const n = topNLimit();
    if (n !== null) {
      lots = [...lots].sort(compareLotsByEstimatedEarning).slice(0, n);
    }

    return [...lots].sort((a, b) => {
      let av: number | null = null;
      let bv: number | null = null;

      switch (sortKey()) {
        case 'arbitrage': av = a.scores.arbitrage ?? null; bv = b.scores.arbitrage ?? null; break;
        case 'estimate': av = a.estimate_low ?? null; bv = b.estimate_low ?? null; break;
        case 'resale': av = getDisplayedResaleEstimate(a); bv = getDisplayedResaleEstimate(b); break;
        case 'earning': av = getEstimatedEarning(a); bv = getEstimatedEarning(b); break;
        case 'timeLeft': av = getTimeLeftMs(a); bv = getTimeLeftMs(b); break;
        case 'multiplier': av = getMultiplier(a); bv = getMultiplier(b); break;
        case 'demand': av = a.scores.demand ?? null; bv = b.scores.demand ?? null; break;
        case 'title':
          return sortDir() === 'desc'
            ? b.title.localeCompare(a.title)
            : a.title.localeCompare(b.title);
      }

      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
      return sortDir() === 'desc' ? (bv - av) : (av - bv);
    });
  });

  const fmt = (n: number | null | undefined) => n != null ? n.toLocaleString() : '\u2014';
  const pct = (n: number | null | undefined) => n != null ? `${(n * 100).toFixed(0)}%` : '\u2014';
  const fmtBidUpdatedAt = (value: string | null | undefined) => {
    if (!value) return null;
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return null;
    return parsed.toLocaleString([], {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  const getBidTooltip = (lot: LotCard) => {
    const updatedAt = fmtBidUpdatedAt(lot.current_bid_updated_at);
    const bidCountLabel = lot.bid_count != null
      ? `${lot.bid_count} bid${lot.bid_count === 1 ? '' : 's'}`
      : null;
    if (lot.current_bid != null && updatedAt) {
      return `${bidCountLabel ?? 'Bid count unknown'}. Current bid last updated ${updatedAt}.`;
    }
    if (lot.current_bid != null) {
      return bidCountLabel ? `${bidCountLabel}. Current bid available.` : 'Current bid available.';
    }
    if (updatedAt) {
      return `${bidCountLabel ?? 'No bids recorded'} as of ${updatedAt}. Estimated earning uses 50% of the auction estimate.`;
    }
    if (bidCountLabel) {
      return `${bidCountLabel}. Estimated earning uses 50% of the auction estimate.`;
    }
    return 'No bid recorded. Estimated earning uses 50% of the auction estimate.';
  };

  const getBidCountLabel = (lot: LotCard) => {
    if (lot.bid_count == null) return null;
    return `${lot.bid_count} bid${lot.bid_count === 1 ? '' : 's'}`;
  };

  const fmtTimeLeft = (ms: number | null, fallback?: string | null) => {
    if (ms == null) return fallback ?? '\u2014';
    if (ms <= 0) return 'Ended';

    const totalSeconds = Math.floor(ms / 1000);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    if (minutes > 0) return `${minutes}m`;
    return `${seconds}s`;
  };

  const multiplierClass = (m: number | null) => {
    if (m === null) return '';
    if (m >= 3) return 'mult-strong';
    if (m >= 2) return 'mult-good';
    if (m >= 1.5) return 'mult-fair';
    return 'mult-low';
  };

  const earningClass = (earning: number | null) => {
    if (earning === null) return '';
    if (earning > 0) return 'earning-positive';
    if (earning < 0) return 'earning-negative';
    return '';
  };

  const demandClass = (score: number | null | undefined) => {
    if (score == null) return '';
    if (score >= 0.5) return 'demand-hot';
    if (score >= 0.3) return 'demand-warm';
    if (score >= 0.1) return 'demand-mild';
    return 'demand-low';
  };

  return (
    <>
      <ViewHeader
        title="Pipeline"
        lotCount={filteredLots().length}
        loading={viewData.loading}
      />
      <Show when={!allLots.loading && (allLots()?.lots?.length ?? 0) > 0}>
        <AuctionCalendar
          lots={allLots()!.lots}
          rankedLots={baseLots()}
          onSelectionChange={setDateRange}
          onTopNChange={setTopNLimit}
        />
      </Show>
      <div class="content-scroll">
        <Show when={!viewData.loading} fallback={<div class="loading"><span class="spinner"></span>Loading...</div>}>
          <table class="lot-table">
            <thead>
              <tr>
                <th class="th-img"></th>
                <th class="th-title">
                  <input
                    type="text"
                    placeholder="Search..."
                    class="th-search-input"
                    value={search()}
                    onInput={e => setSearch(e.currentTarget.value)}
                    onclick={e => e.stopPropagation()}
                  />
                </th>
                <th class="th-loc">
                  <select
                    class="th-loc-select"
                    value={regionFilter()}
                    onChange={e => setRegionFilter(e.currentTarget.value as RegionFilter)}
                  >
                    <option value="">Location</option>
                    <option value="scandinavia">Scandinavia</option>
                    <option value="sweden">Sweden</option>
                    <option value="denmark">Denmark</option>
                    <option value="germany">Germany</option>
                    <option value="uk">UK</option>
                    <option value="other">Other</option>
                  </select>
                </th>
                <th class="th-num sortable" onclick={() => toggleSort('estimate')}>Auc. Est.{sortIndicator('estimate')}</th>
                <th class="th-num sortable" onclick={() => toggleSort('resale')}>Resale Est.{sortIndicator('resale')}</th>
                <th class="th-num sortable" onclick={() => toggleSort('earning')}>Est. Earning{sortIndicator('earning')}</th>
                <th class="th-num">Bid</th>
                <th class="th-num sortable" onclick={() => toggleSort('demand')}>Demand{sortIndicator('demand')}</th>
                <th class="th-num sortable" onclick={() => toggleSort('timeLeft')}>Time Left{sortIndicator('timeLeft')}</th>
                <th class="th-link"></th>
              </tr>
            </thead>
            <tbody>
              <For each={filteredLots()}>
                {(lot) => {
                  const mult = getMultiplier(lot);
                  const earning = getEstimatedEarning(lot);
                  const timeLeftMs = getTimeLeftMs(lot);
                  return (
                    <tr class="lot-row" onclick={() => navigate(`/lots/${lot.id}`)}>
                      <td class="td-img">
                        <Show when={lot.image_url} fallback={<div class="row-img-placeholder" />}>
                          <img src={lot.image_url!} alt="" class="row-img" loading="lazy" />
                        </Show>
                      </td>
                      <td class="td-title">{lot.title}</td>
                      <td class="td-loc" title={lot.seller_location ?? ''}>{lot.seller_location?.split(',')[0] ?? '\u2014'}</td>
                      <td class="td-num">{lot.estimate_low != null ? `${fmt(lot.estimate_low)} ${lot.currency || 'EUR'}` : '\u2014'}</td>
                      <td class="td-num td-resale">
                        {lot.ai_value_low != null && lot.ai_value_high != null
                          ? `${fmt(lot.ai_value_low)}\u2013${fmt(lot.ai_value_high)} EUR`
                          : lot.expected_resale_eur != null
                            ? `${fmt(lot.expected_resale_eur)} EUR`
                            : '\u2014'}
                      </td>
                      <td class={`td-num td-earning ${earningClass(earning)}`}>
                        {earning != null ? `${earning > 0 ? '+' : ''}${fmt(earning)} EUR` : '\u2014'}
                      </td>
                      <td class="td-num td-bid">
                        <span
                          class="bid-tooltip-anchor"
                          tabindex={0}
                          aria-label={getBidTooltip(lot)}
                        >
                          <span class="bid-value">{lot.current_bid != null ? `${fmt(lot.current_bid)}` : '\u2014'}</span>
                          <Show when={getBidCountLabel(lot)}>
                            <span class="bid-meta">{getBidCountLabel(lot)}</span>
                          </Show>
                          <span class="bid-tooltip">{getBidTooltip(lot)}</span>
                        </span>
                      </td>
                      <td class={`td-num td-demand ${demandClass(lot.scores.demand)}`} title={lot.demand_summary ?? ''}>
                        <Show when={lot.scores.demand != null && (lot.scores.demand ?? 0) > 0} fallback={<span>{'\u2014'}</span>}>
                          <span class="demand-score">{pct(lot.scores.demand)}</span>
                        </Show>
                      </td>
                      <td class="td-num td-time">{fmtTimeLeft(timeLeftMs, lot.time_remaining)}</td>
                      <td class="td-link">
                        <Show when={lot.lot_url}>
                          <a
                            href={lot.lot_url!}
                            target="_blank"
                            rel="noopener noreferrer"
                            onclick={(e: MouseEvent) => e.stopPropagation()}
                          >
                            &rarr;
                          </a>
                        </Show>
                      </td>
                    </tr>
                  );
                }}
              </For>
            </tbody>
          </table>
        </Show>
      </div>
    </>
  );
};
