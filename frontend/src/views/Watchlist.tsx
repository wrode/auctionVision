import { createResource, Show, For } from 'solid-js';
import { apiClient } from '../api';
import { ViewHeader } from '../components/ViewHeader';
import { LotCard } from '../components/LotCard';

export const Watchlist = () => {
  const [viewData] = createResource(() =>
    apiClient.fetchView('watchlist', { limit: 100 }),
  );

  const handleRefresh = async () => {
    try {
      await apiClient.refreshView('watchlist');
    } catch (error) {
      console.error('Refresh failed:', error);
    }
  };

  return (
    <>
      <ViewHeader
        title="Watchlist"
        lotCount={viewData()?.total}
        lastRefreshed={viewData()?.filters?.last_refreshed}
        onRefresh={handleRefresh}
        loading={viewData.loading}
      />
      <div class="content-scroll">
        <Show when={!viewData.loading} fallback={<div class="loading"><span class="spinner"></span>Loading watchlist...</div>}>
          <Show when={viewData()?.lots && viewData()!.lots.length > 0} fallback={<div class="loading">Your watchlist is empty</div>}>
            <div class="lot-grid">
              <For each={viewData()?.lots}>
                {(lot) => (
                  <div>
                    <LotCard lot={lot} />
                    <Show when={lot.user_actions?.includes('watch')}>
                      <div style="padding: var(--spacing-sm); background-color: rgba(56, 142, 60, 0.1); border: 1px solid var(--score-green); border-top: none; border-radius: 0 0 var(--radius-md) var(--radius-md); text-align: center;">
                        <span style="font-size: 0.75rem; color: var(--score-green); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
                          ✓ Watching
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
