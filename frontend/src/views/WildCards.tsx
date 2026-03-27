import { createResource, Show, For } from 'solid-js';
import { apiClient } from '../api';
import { ViewHeader } from '../components/ViewHeader';
import { LotCard } from '../components/LotCard';

export const WildCards = () => {
  const [viewData] = createResource(() =>
    apiClient.fetchView('wild_cards', { limit: 50 }),
  );

  const handleRefresh = async () => {
    try {
      await apiClient.refreshView('wild_cards');
    } catch (error) {
      console.error('Refresh failed:', error);
    }
  };

  return (
    <>
      <ViewHeader
        title="Wild Cards"
        lotCount={viewData()?.lot_count}
        lastRefreshed={viewData()?.last_refreshed}
        onRefresh={handleRefresh}
        loading={viewData.loading}
      />
      <div class="content-scroll">
        <Show when={!viewData.loading} fallback={<div class="loading"><span class="spinner"></span>Loading wild cards...</div>}>
          <Show when={viewData()?.lots && viewData()!.lots.length > 0} fallback={<div class="loading">No lots found</div>}>
            <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: var(--spacing-lg);">
              <For each={viewData()?.lots}>
                {(lot) => (
                  <div style="border: 1px solid var(--border-color); border-radius: var(--radius-md); overflow: hidden; background-color: var(--bg-card); transition: all var(--transition);" class="lot-card">
                    <Show when={lot.image_url}>
                      <img
                        src={lot.image_url}
                        alt={lot.title}
                        style="width: 100%; height: 280px; object-fit: cover; display: block;"
                      />
                    </Show>
                    <div style="padding: var(--spacing-lg);">
                      <h3 style="font-weight: 600; margin-bottom: var(--spacing-md);">{lot.title}</h3>
                      <Show when={lot.rationale}>
                        <p style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: var(--spacing-lg); line-height: 1.5;">
                          {lot.rationale}
                        </p>
                      </Show>
                      <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 600; color: var(--accent-gold);">
                          {(lot.wildcard_score! * 100).toFixed(0)}% Wild
                        </span>
                        <Show when={lot.current_bid}>
                          <span style="color: var(--text-secondary);">
                            ${lot.current_bid?.toLocaleString()}
                          </span>
                        </Show>
                      </div>
                    </div>
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
