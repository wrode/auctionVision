import { createMemo, createSignal, createEffect, For, Show, onCleanup } from 'solid-js';
import type { LotCard } from '../types';

export interface DateRange {
  start: string; // YYYY-MM-DD
  end: string;
}

interface CalendarProps {
  lots: LotCard[];
  rankedLots?: LotCard[];
  onSelectionChange?: (range: DateRange | null) => void;
  onTopNChange?: (n: number | null) => void;
}

/* ── Shared helpers ── */

const dateKey = (date: Date) => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};

const hasAiEstimate = (lot: LotCard) => lot.ai_value_low != null && lot.ai_value_high != null;
const getResaleMid = (lot: LotCard) =>
  lot.ai_value_low != null && lot.ai_value_high != null
    ? (lot.ai_value_low + lot.ai_value_high) / 2
    : null;
const getDisplayedResaleEstimate = (lot: LotCard) =>
  getResaleMid(lot) ?? lot.expected_resale_eur ?? null;
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

/* ── Weekly Revenue Bar ── */

interface BarProps {
  lots: LotCard[];
}

const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export const WeeklyRevenueBar = (props: BarProps) => {
  const weekData = createMemo(() => {
    const today = new Date();
    const dow = today.getDay();
    const mondayOffset = dow === 0 ? 1 : 8 - dow;
    const startDate = new Date(today);
    if (dow === 1) {
      startDate.setHours(0, 0, 0, 0);
    } else {
      startDate.setDate(today.getDate() + mondayOffset);
      startDate.setHours(0, 0, 0, 0);
    }

    const earningsByDate: Record<string, number> = {};
    const lotCountByDate: Record<string, number> = {};
    for (const lot of props.lots) {
      if (!lot.auction_end_time) continue;
      const d = lot.auction_end_time.slice(0, 10);
      const earning = getEstimatedEarning(lot);
      if (earning != null && earning > 0) {
        earningsByDate[d] = (earningsByDate[d] || 0) + earning;
      }
      lotCountByDate[d] = (lotCountByDate[d] || 0) + 1;
    }

    const days: { label: string; dateStr: string; revenue: number; lots: number; isToday: boolean }[] = [];
    const cursor = new Date(startDate);
    const todayStr = dateKey(today);
    for (let i = 0; i < 7; i++) {
      const ds = dateKey(cursor);
      days.push({
        label: DAY_LABELS[i],
        dateStr: ds,
        revenue: earningsByDate[ds] || 0,
        lots: lotCountByDate[ds] || 0,
        isToday: ds === todayStr,
      });
      cursor.setDate(cursor.getDate() + 1);
    }

    const maxRevenue = Math.max(...days.map(d => d.revenue), 1);
    const totalRevenue = days.reduce((s, d) => s + d.revenue, 0);
    const totalLots = days.reduce((s, d) => s + d.lots, 0);

    const rangeStart = new Date(startDate);
    const rangeEnd = new Date(startDate);
    rangeEnd.setDate(rangeEnd.getDate() + 6);
    const fmtOpts: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' };
    const rangeLabel = `${rangeStart.toLocaleDateString('en', fmtOpts)} – ${rangeEnd.toLocaleDateString('en', fmtOpts)}`;

    return { days, maxRevenue, totalRevenue, totalLots, rangeLabel };
  });

  const fmtK = (n: number) => {
    if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k`;
    return Math.round(n).toLocaleString();
  };

  return (
    <div class="week-revenue">
      <div class="wr-header">
        <div class="wr-header-left">
          <span class="wr-title">Est. Revenue This Week</span>
          <span class="wr-range">{weekData().rangeLabel}</span>
        </div>
        <div class="wr-header-right">
          <span class="wr-total">{fmtK(weekData().totalRevenue)} EUR</span>
          <span class="wr-lot-count">{weekData().totalLots} lots</span>
        </div>
      </div>
      <div class="wr-chart">
        <For each={weekData().days}>
          {(day) => {
            const pct = () => weekData().maxRevenue > 0 ? (day.revenue / weekData().maxRevenue) * 100 : 0;
            return (
              <div class="wr-bar-col" classList={{ 'wr-bar-today': day.isToday }}>
                <div class="wr-bar-value">{day.revenue > 0 ? fmtK(day.revenue) : ''}</div>
                <div class="wr-bar-track">
                  <div
                    class="wr-bar-fill"
                    classList={{ 'wr-bar-empty': day.revenue === 0 }}
                    style={{ height: `${Math.max(pct(), day.revenue > 0 ? 4 : 0)}%` }}
                  />
                </div>
                <div class="wr-bar-label">{day.label}</div>
                <div class="wr-bar-lots">{day.lots > 0 ? `${day.lots}` : ''}</div>
              </div>
            );
          }}
        </For>
      </div>
    </div>
  );
};

/* ── Heatmap Calendar ── */

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
const fmtCurrency = (amount: number | null) =>
  amount != null ? `${amount > 0 ? '+' : ''}${Math.round(amount).toLocaleString()} EUR` : '\u2014';
const fmtCurrencyPlain = (amount: number | null) =>
  amount != null ? `${Math.round(amount).toLocaleString()} EUR` : '\u2014';

/** GitHub-style heatmap with drag-to-select weeks and top-N summary controls. */
export const AuctionCalendar = (props: CalendarProps) => {
  const dayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const topNOptions = [3, 5, 7, 10, 20];

  const [selStart, setSelStart] = createSignal<number | null>(null);
  const [selEnd, setSelEnd] = createSignal<number | null>(null);
  const [dragging, setDragging] = createSignal(false);
  const [topN, setTopN] = createSignal<number | null>(5);

  const selRange = createMemo(() => {
    const s = selStart();
    const e = selEnd();
    if (s === null || e === null) return null;
    return { lo: Math.min(s, e), hi: Math.max(s, e) };
  });

  const isWeekSelected = (weekIdx: number) => {
    const r = selRange();
    if (!r) return false;
    return weekIdx >= r.lo && weekIdx <= r.hi;
  };

  const onGlobalMouseUp = () => {
    if (dragging()) setDragging(false);
  };
  if (typeof window !== 'undefined') {
    window.addEventListener('mouseup', onGlobalMouseUp);
    onCleanup(() => window.removeEventListener('mouseup', onGlobalMouseUp));
  }

  const clearSelection = () => {
    setTopN(null);
    setSelStart(null);
    setSelEnd(null);
  };

  const selectAll = () => {
    setDragging(false);
    setSelStart(0);
    setSelEnd(calendarData().weeks.length - 1);
  };

  const selectMonth = (col: number, endCol: number) => {
    setDragging(false);
    setSelStart(col);
    setSelEnd(endCol);
  };

  const calendarData = createMemo(() => {
    const counts: Record<string, number> = {};
    const rankedCounts: Record<string, number> = {};
    for (const lot of props.lots) {
      if (!lot.auction_end_time) continue;
      const dateStr = lot.auction_end_time.slice(0, 10);
      counts[dateStr] = (counts[dateStr] || 0) + 1;
    }
    for (const lot of (props.rankedLots ?? props.lots)) {
      if (!lot.auction_end_time) continue;
      const dateStr = lot.auction_end_time.slice(0, 10);
      rankedCounts[dateStr] = (rankedCounts[dateStr] || 0) + 1;
    }

    const today = new Date();
    const dayOfWeek = today.getDay();
    const mondayOffset = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
    const startDate = new Date(today);
    startDate.setDate(today.getDate() + mondayOffset - 14);
    startDate.setHours(0, 0, 0, 0);

    type Cell = { date: Date; dateStr: string; count: number; rankedCount: number; isToday: boolean; isPast: boolean };
    const weeks: Cell[][] = [];
    const totalWeeks = 12;
    let maxCount = 0;
    const cursor = new Date(startDate);

    for (let w = 0; w < totalWeeks; w++) {
      const week: Cell[] = [];
      for (let d = 0; d < 7; d++) {
        const ds = dateKey(cursor);
        const count = counts[ds] || 0;
        const rankedCount = rankedCounts[ds] || 0;
        if (count > maxCount) maxCount = count;
        const isToday =
          cursor.getFullYear() === today.getFullYear() &&
          cursor.getMonth() === today.getMonth() &&
          cursor.getDate() === today.getDate();
        week.push({ date: new Date(cursor), dateStr: ds, count, rankedCount, isToday, isPast: cursor < today && !isToday });
        cursor.setDate(cursor.getDate() + 1);
      }
      weeks.push(week);
    }

    const monthLabels: { label: string; col: number; endCol: number }[] = [];
    let lastMonth = -1;
    for (let w = 0; w < weeks.length; w++) {
      const m = weeks[w][0].date.getMonth();
      if (m !== lastMonth) {
        if (monthLabels.length > 0) monthLabels[monthLabels.length - 1].endCol = w - 1;
        monthLabels.push({ label: weeks[w][0].date.toLocaleString('en', { month: 'short' }), col: w, endCol: weeks.length - 1 });
        lastMonth = m;
      }
    }

    return { weeks, maxCount, monthLabels };
  });

  createEffect(() => {
    const r = selRange();
    const { weeks } = calendarData();
    if (!r) {
      props.onSelectionChange?.(null);
      props.onTopNChange?.(null);
      return;
    }
    props.onSelectionChange?.({
      start: weeks[r.lo][0].dateStr,
      end: weeks[r.hi][6].dateStr,
    });
  });

  createEffect(() => {
    if (selRange()) {
      props.onTopNChange?.(topN());
    }
  });

  const selectionSummary = createMemo(() => {
    const r = selRange();
    const { weeks } = calendarData();
    if (!r) return null;

    const startDate = weeks[r.lo][0].dateStr;
    const endDate = weeks[r.hi][6].dateStr;
    const inRange = (lot: LotCard) => {
      if (!lot.auction_end_time) return false;
      const d = lot.auction_end_time.slice(0, 10);
      return d >= startDate && d <= endDate;
    };

    const selectedLots = props.lots.filter(inRange);
    const rankedPool = (props.rankedLots ?? props.lots).filter(inRange);
    const ranked = [...rankedPool].sort(compareLotsByEstimatedEarning);
    const limit = topN() ?? ranked.length;
    const topLots = ranked.slice(0, limit);
    const arbScores = topLots.map((lot) => lot.scores.arbitrage).filter((score): score is number => score != null);
    const earnings = topLots.map((lot) => getEstimatedEarning(lot)).filter((value): value is number => value != null);
    const landedCosts = topLots.map((lot) => lot.landed_cost_eur).filter((v): v is number => v != null);
    const resaleValues = topLots.map((lot) => getDisplayedResaleEstimate(lot)).filter((v): v is number => v != null);

    let totalHammer = 0;
    let totalPremium = 0;
    let totalTransport = 0;
    let lotsWithLanded = 0;
    for (const lot of topLots) {
      if (lot.landed_cost_eur != null && lot.estimate_low != null && lot.estimate_low > 0) {
        const hammer = (lot.current_bid != null && lot.current_bid > 0) ? lot.current_bid : lot.estimate_low / 2;
        const prem = hammer * 0.20;
        const vat = prem * 0.25;
        const transport = lot.landed_cost_eur - hammer - prem - vat;
        totalHammer += hammer;
        totalPremium += prem + vat;
        totalTransport += Math.max(0, transport);
        lotsWithLanded++;
      }
    }

    const now = Date.now();
    const withEarning = topLots.filter((lot) => {
      const hasResale = hasAiEstimate(lot) || lot.expected_resale_eur != null;
      const hasBid = (lot.current_bid != null && lot.current_bid > 0) || (lot.estimate_low != null && lot.estimate_low > 0);
      return hasResale && hasBid;
    }).length;

    const basisCounts = topLots
      .map((lot) => lot.estimate_basis?.length ?? 0)
      .filter((c) => c > 0);
    const avgComps = basisCounts.length > 0
      ? basisCounts.reduce((s, c) => s + c, 0) / basisCounts.length
      : 0;

    const riskFlagged = topLots.filter((lot) => lot.risk_flags && lot.risk_flags.length > 0).length;
    const noBids = topLots.filter((lot) => lot.current_bid == null || lot.current_bid <= 0).length;
    const belowMaxBid = topLots.filter((lot) =>
      lot.max_bid_eur != null && lot.current_bid != null && lot.current_bid < lot.max_bid_eur
    ).length;
    const endingSoon = topLots.filter((lot) => {
      if (!lot.auction_end_time) return false;
      const ms = new Date(lot.auction_end_time).getTime() - now;
      return ms > 0 && ms < 86_400_000;
    }).length;

    return {
      startDate,
      endDate,
      totalLots: selectedLots.length,
      topSelectedCount: topLots.length,
      topAvgArb: arbScores.length > 0 ? arbScores.reduce((sum, score) => sum + score, 0) / arbScores.length : 0,
      totalEstimatedEarning: earnings.length > 0 ? earnings.reduce((sum, value) => sum + value, 0) : null,
      totalLandedCost: landedCosts.length > 0 ? landedCosts.reduce((sum, v) => sum + v, 0) : null,
      landedBreakdown: lotsWithLanded > 0 ? { hammer: totalHammer, premium: totalPremium, transport: totalTransport } : null,
      totalResale: resaleValues.length > 0 ? resaleValues.reduce((sum, v) => sum + v, 0) : null,
      rankedPoolTotal: rankedPool.length,
      withEarning,
      avgComps,
      riskFlagged,
      noBids,
      belowMaxBid,
      endingSoon,
    };
  });

  const intensity = (count: number, max: number): number => {
    if (count === 0 || max === 0) return 0;
    const ratio = count / max;
    if (ratio <= 0.25) return 1;
    if (ratio <= 0.5) return 2;
    if (ratio <= 0.75) return 3;
    return 4;
  };

  const fmtDateShort = (dateStr: string) => {
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en', { month: 'short', day: 'numeric' });
  };

  const isAllSelected = () => {
    const r = selRange();
    return r !== null && r.lo === 0 && r.hi === calendarData().weeks.length - 1;
  };

  return (
    <div class="auction-calendar">
      <div class="cal-top-row">
        <div class="cal-heatmap">
          <div class="cal-grid">
            <div class="cal-day-labels">
              <div class="cal-month-spacer" />
              <For each={dayLabels}>
                {(label, i) => (
                  <div class="cal-day-label" classList={{ 'cal-day-hidden': i() % 2 === 1 }}>
                    {label}
                  </div>
                )}
              </For>
            </div>

            <div class="cal-weeks">
              <div class="cal-month-row">
                <For each={calendarData().weeks}>
                  {(_week, w) => {
                    const ml = calendarData().monthLabels.find((m) => m.col === w());
                    return (
                      <div
                        class="cal-month-cell"
                        classList={{ 'cal-month-clickable': !!ml }}
                        onClick={() => ml && selectMonth(ml.col, ml.endCol)}
                      >
                        {ml ? ml.label : ''}
                      </div>
                    );
                  }}
                </For>
              </div>

              <For each={[0, 1, 2, 3, 4, 5, 6]}>
                {(dayIdx) => (
                  <div class="cal-row">
                    <For each={calendarData().weeks}>
                      {(week, w) => {
                        const cell = week[dayIdx];
                        const level = intensity(cell.count, calendarData().maxCount);
                        const selected = () => isWeekSelected(w());
                        return (
                          <div
                            class="cal-cell"
                            classList={{
                              'cal-today': cell.isToday,
                              'cal-past': cell.isPast && !selected(),
                              [`cal-level-${level}`]: true,
                              'cal-selected': selected(),
                              'cal-dimmed': selRange() !== null && !selected(),
                            }}
                            title={`${cell.dateStr}: ${cell.count} auction${cell.count !== 1 ? 's' : ''} ending`}
                            onMouseDown={(e) => {
                              e.preventDefault();
                              setDragging(true);
                              setSelStart(w());
                              setSelEnd(w());
                            }}
                            onMouseEnter={() => {
                              if (dragging()) setSelEnd(w());
                            }}
                          />
                        );
                      }}
                    </For>
                  </div>
                )}
              </For>

              <div class="cal-sel-bar">
                <For each={calendarData().weeks}>
                  {(_week, w) => (
                    <div class="cal-sel-tick" classList={{ 'cal-sel-tick-active': isWeekSelected(w()) }} />
                  )}
                </For>
              </div>

              <div class="cal-pct-row">
                <For each={calendarData().weeks}>
                  {(week) => {
                    const total = week.reduce((s, c) => s + c.count, 0);
                    const ranked = week.reduce((s, c) => s + c.rankedCount, 0);
                    const pct = total > 0 ? Math.round((ranked / total) * 100) : null;
                    return (
                      <div class="cal-pct-cell" title={total > 0 ? `${ranked}/${total} lots match filter` : 'No lots'}>
                        {pct !== null ? `${pct}%` : ''}
                      </div>
                    );
                  }}
                </For>
              </div>
            </div>
          </div>

          <div class="cal-footer">
            <div class="cal-legend">
              <span class="cal-legend-label">Less</span>
              <div class="cal-cell cal-level-0 cal-legend-cell" />
              <div class="cal-cell cal-level-1 cal-legend-cell" />
              <div class="cal-cell cal-level-2 cal-legend-cell" />
              <div class="cal-cell cal-level-3 cal-legend-cell" />
              <div class="cal-cell cal-level-4 cal-legend-cell" />
              <span class="cal-legend-label">More</span>
            </div>
            <button
              class="cal-filter-btn"
              classList={{ 'cal-filter-btn-active': isAllSelected() }}
              onClick={selectAll}
            >
              All
            </button>
            <Show when={selRange() !== null}>
              <button class="cal-filter-btn" onClick={clearSelection}>Clear</button>
            </Show>
          </div>
        </div>

        <Show when={selectionSummary()}>
          {(summary) => (
            <div class="cal-summary">
              <div class="cms-header">
                <div class="cms-header-left">
                  <span class="cms-date-range">{fmtDateShort(summary().startDate)} – {fmtDateShort(summary().endDate)}</span>
                  <span class="cms-header-count">{summary().totalLots} lots</span>
                </div>
                <div class="cms-topn-row">
                  <span class="cms-topn-label">Top</span>
                  <For each={topNOptions}>
                    {(n) => (
                      <button
                        class="cal-filter-btn"
                        classList={{ 'cal-filter-btn-active': topN() === n }}
                        onClick={() => setTopN(n)}
                      >
                        {n}
                      </button>
                    )}
                  </For>
                  <button
                    class="cal-filter-btn"
                    classList={{ 'cal-filter-btn-active': (topN() ?? summary().rankedPoolTotal) >= summary().rankedPoolTotal }}
                    onClick={() => setTopN(null)}
                  >
                    All
                  </button>
                </div>
              </div>

              <Show when={summary().totalLots > 0} fallback={<div class="cms-empty">No auctions ending in this period</div>}>
                <div class="cms-body">
                  <div class="cms-costs-row">
                    <div class="cms-earning-block">
                      <span
                        class="cms-earning-value"
                        classList={{
                          'cms-profit': (summary().totalEstimatedEarning ?? 0) > 0,
                          'cms-loss': (summary().totalEstimatedEarning ?? 0) < 0,
                        }}
                      >
                        {fmtCurrency(summary().totalEstimatedEarning)}
                      </span>
                      <span class="cms-label">est. earning</span>
                    </div>
                    <div class="cms-stat cms-landed-wrapper">
                      <span class="cms-value">{fmtCurrencyPlain(summary().totalLandedCost)}</span>
                      <span class="cms-label">landed cost</span>
                      <Show when={summary().landedBreakdown}>
                        <div class="cms-landed-breakdown">
                          <div class="cms-breakdown-row">
                            <span>Hammer (bid/est)</span>
                            <span>{fmtCurrencyPlain(summary().landedBreakdown!.hammer)}</span>
                          </div>
                          <div class="cms-breakdown-row">
                            <span>Premium + VAT</span>
                            <span>{fmtCurrencyPlain(summary().landedBreakdown!.premium)}</span>
                          </div>
                          <div class="cms-breakdown-row">
                            <span>Transport</span>
                            <span>{fmtCurrencyPlain(summary().landedBreakdown!.transport)}</span>
                          </div>
                        </div>
                      </Show>
                    </div>
                    <div class="cms-stat">
                      <span class="cms-value">{fmtCurrencyPlain(summary().totalResale)}</span>
                      <span class="cms-label">est. resale</span>
                    </div>
                  </div>

                  <div class="cms-primary">
                    <div class="cms-stat">
                      <span class="cms-value cms-highlight">{(summary().topAvgArb * 100).toFixed(0)}%</span>
                      <span class="cms-label">avg arb score</span>
                    </div>
                    <div class="cms-stat">
                      <span class="cms-value">{summary().withEarning}<span class="cms-value-denom">/{summary().topSelectedCount}</span></span>
                      <span class="cms-label">with est. earning</span>
                    </div>
                    <div class="cms-stat">
                      <span class="cms-value">{summary().avgComps > 0 ? summary().avgComps.toFixed(1) : '\u2014'}</span>
                      <span class="cms-label">avg comparables</span>
                    </div>
                  </div>

                  <div class="cms-signals">
                    <Show when={summary().noBids > 0}>
                      <span class="cms-pill cms-pill-opportunity">{summary().noBids} no bids</span>
                    </Show>
                    <Show when={summary().belowMaxBid > 0}>
                      <span class="cms-pill cms-pill-opportunity">{summary().belowMaxBid} below max bid</span>
                    </Show>
                    <Show when={summary().endingSoon > 0}>
                      <span class="cms-pill cms-pill-urgent">{summary().endingSoon} ending &lt;24h</span>
                    </Show>
                    <Show when={summary().riskFlagged > 0}>
                      <span class="cms-pill cms-pill-warn">{summary().riskFlagged} risk-flagged</span>
                    </Show>
                  </div>
                </div>
              </Show>
            </div>
          )}
        </Show>
      </div>
    </div>
  );
};
