import { createResource, Show, For } from 'solid-js';
import { apiClient } from '../api';
import { ViewHeader } from '../components/ViewHeader';
import { LotCard } from '../components/LotCard';

export const NorwayArbitrage = () => {
  const [viewData] = createResource(() =>
    apiClient.fetchView('norway_arbitrage', { limit: 100 }),
  );

  const handleRefresh = async () => {
    try {
      await apiClient.refreshView('norway_arbitrage');
    } catch (error) {
      console.error('Refresh failed:', error);
    }
  };

  return (
    <>
      <ViewHeader
        title="Norway Arbitrage"
        lotCount={viewData()?.lot_count}
        lastRefreshed={viewData()?.last_refreshed}
        onRefresh={handleRefresh}
        loading={viewData.loading}
      />
      <div class="content-scroll">
        <Show when={!viewData.loading} fallback={<div class="loading"><span class="spinner"></span>Loading Norway arbitrage lots...</div>}>
          <Show when={viewData()?.lots && viewData()!.lots.length > 0} fallback={<div class="loading">No lots found</div>}>
            <div class="lot-grid">
              <For each={viewData()?.lots}>
                {(lot) => (
                  <div>
                    <LotCard lot={lot} />
                    <Show when={lot.norway_gap_score !== undefined}>
                      <div style="padding: var(--spacing-sm); background-color: var(--bg-card); border: 1px solid var(--border-color); border-top: none; text-align: center;">
                        <span style="font-size: 0.8rem; color: var(--accent-gold); font-weight: 600;">
                          Norway Gap: {((lot.norway_gap_score || 0) * 100).toFixed(0)}%
                        </span>
                      </div>
                    </Show>
                  </div>
                )}
              </For>
            </div>
          </Show>
        </Show>
      </div>
    </>
  );
};
