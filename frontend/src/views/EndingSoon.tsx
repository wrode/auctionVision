import { createResource, Show, For } from 'solid-js';
import { apiClient } from '../api';
import { ViewHeader } from '../components/ViewHeader';
import { LotCard } from '../components/LotCard';
import { TimeRemaining } from '../components/TimeRemaining';

export const EndingSoon = () => {
  const [viewData] = createResource(() =>
    apiClient.fetchView('ending_soon', { limit: 100, sort_by: 'auction_end_time' }),
  );

  const handleRefresh = async () => {
    try {
      await apiClient.refreshView('ending_soon');
    } catch (error) {
      console.error('Refresh failed:', error);
    }
  };

  return (
    <>
      <ViewHeader
        title="Ending Soon"
        lotCount={viewData()?.lot_count}
        lastRefreshed={viewData()?.last_refreshed}
        onRefresh={handleRefresh}
        loading={viewData.loading}
      />
      <div class="content-scroll">
        <Show when={!viewData.loading} fallback={<div class="loading"><span class="spinner"></span>Loading auctions ending soon...</div>}>
          <Show when={viewData()?.lots && viewData()!.lots.length > 0} fallback={<div class="loading">No lots found</div>}>
            <div class="lot-list">
              <For each={viewData()?.lots}>
                {(lot) => (
                  <div class="lot-list-item">
                    <Show when={lot.image_url}>
                      <img
                        src={lot.image_url}
                        alt={lot.title}
                        style="width: 120px; height: 120px; object-fit: cover; border-radius: var(--radius-md); flex-shrink: 0;"
                      />
                    </Show>

                    <div style="flex: 1; display: flex; flex-direction: column; gap: var(--spacing-sm);">
                      <h3 style="font-weight: 600; font-size: 1rem;">{lot.title}</h3>
                      <div style="display: flex; gap: var(--spacing-lg); font-size: 0.9rem;">
                        <div>
                          <span style="color: var(--text-secondary); font-size: 0.8rem; text-transform: uppercase;">Current Bid</span>
                          <div style="font-weight: 600; color: var(--accent-gold);">
                            <Show when={lot.current_bid} fallback="—">
                              ${lot.current_bid?.toLocaleString()}
                            </Show>
                          </div>
                        </div>
                        <Show when={lot.estimate_min || lot.estimate_max}>
                          <div>
                            <span style="color: var(--text-secondary); font-size: 0.8rem; text-transform: uppercase;">Estimate</span>
                            <div style="color: var(--text-primary);">
                              ${lot.estimate_min?.toLocaleString()} - $
                              {lot.estimate_max?.toLocaleString()}
                            </div>
                          </div>
                        </Show>
                      </div>
                      <Show when={lot.rationale}>
                        <p style="font-size: 0.85rem; color: var(--text-secondary); font-style: italic;">
                          "{lot.rationale}"
                        </p>
                      </Show>
                    </div>

                    <div style="display: flex; flex-direction: column; align-items: flex-end; justify-content: center; gap: var(--spacing-md); min-width: 150px;">
                      <div style="text-align: center;">
                        <TimeRemaining endTime={lot.auction_end_time} showText={true} />
                      </div>
                      <Show when={lot.source}>
                        <span style="font-size: 0.75rem; background-color: var(--bg-secondary); color: var(--text-secondary); padding: 0.25rem 0.5rem; border-radius: var(--radius-sm); text-transform: uppercase; letter-spacing: 0.5px;">
                          {lot.source}
                        </span>
                      </Show>
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
