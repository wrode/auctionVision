import { createResource, Show, For } from 'solid-js';
import { apiClient } from '../api';
import { ViewHeader } from '../components/ViewHeader';
import { LotCard } from '../components/LotCard';

export const BestBuys = () => {
  const [viewData] = createResource(() =>
    apiClient.fetchView('best_buys', { limit: 100 }),
  );

  const handleRefresh = async () => {
    try {
      await apiClient.refreshView('best_buys');
    } catch (error) {
      console.error('Refresh failed:', error);
    }
  };

  return (
    <>
      <ViewHeader
        title="Best Buys"
        lotCount={viewData()?.lot_count}
        lastRefreshed={viewData()?.last_refreshed}
        onRefresh={handleRefresh}
        loading={viewData.loading}
      />
      <div class="content-scroll">
        <Show when={!viewData.loading} fallback={<div class="loading"><span class="spinner"></span>Loading best buys...</div>}>
          <Show when={viewData()?.lots && viewData()!.lots.length > 0} fallback={<div class="loading">No lots found</div>}>
            <div class="lot-grid">
              <For each={viewData()?.lots}>
                {(lot) => <LotCard lot={lot} />}
              </For>
            </div>
          </Show>
        </Show>
      </div>
    </>
  );
};
