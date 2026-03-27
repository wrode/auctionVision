import { createResource, Show, For } from 'solid-js';
import { apiClient } from '../api';
import { ViewHeader } from '../components/ViewHeader';
import { LotCard } from '../components/LotCard';

export const YourTaste = () => {
  const [viewData] = createResource(() =>
    apiClient.fetchView('your_taste', { limit: 100 }),
  );

  const handleRefresh = async () => {
    try {
      await apiClient.refreshView('your_taste');
    } catch (error) {
      console.error('Refresh failed:', error);
    }
  };

  const groupedByCategory = () => {
    const lots = viewData()?.lots || [];
    const grouped: Record<string, typeof lots> = {
      core: [],
      adjacent: [],
      exploratory: [],
    };

    lots.forEach((lot) => {
      const category = lot.taste_category || 'exploratory';
      grouped[category].push(lot);
    });

    return grouped;
  };

  return (
    <>
      <ViewHeader
        title="Your Taste"
        lotCount={viewData()?.lot_count}
        lastRefreshed={viewData()?.last_refreshed}
        onRefresh={handleRefresh}
        loading={viewData.loading}
      />
      <div class="content-scroll">
        <Show when={!viewData.loading} fallback={<div class="loading"><span class="spinner"></span>Loading your taste...</div>}>
          <Show when={viewData()?.lots && viewData()!.lots.length > 0} fallback={<div class="loading">No lots found</div>}>
            <Show when={groupedByCategory().core.length > 0}>
              <div style="margin-bottom: var(--spacing-xl);">
                <h3 style="font-size: 1.1rem; font-weight: 600; color: var(--accent-gold); margin-bottom: var(--spacing-lg); text-transform: uppercase; letter-spacing: 1px;">
                  Core Collection
                </h3>
                <div class="lot-grid">
                  <For each={groupedByCategory().core}>
                    {(lot) => <LotCard lot={lot} />}
                  </For>
                </div>
              </div>
            </Show>

            <Show when={groupedByCategory().adjacent.length > 0}>
              <div style="margin-bottom: var(--spacing-xl);">
                <h3 style="font-size: 1.1rem; font-weight: 600; color: var(--accent-gold); margin-bottom: var(--spacing-lg); text-transform: uppercase; letter-spacing: 1px;">
                  Adjacent
                </h3>
                <div class="lot-grid">
                  <For each={groupedByCategory().adjacent}>
                    {(lot) => <LotCard lot={lot} />}
                  </For>
                </div>
              </div>
            </Show>

            <Show when={groupedByCategory().exploratory.length > 0}>
              <div>
                <h3 style="font-size: 1.1rem; font-weight: 600; color: var(--accent-gold); margin-bottom: var(--spacing-lg); text-transform: uppercase; letter-spacing: 1px;">
                  Exploratory
                </h3>
                <div class="lot-grid">
                  <For each={groupedByCategory().exploratory}>
                    {(lot) => <LotCard lot={lot} />}
                  </For>
                </div>
              </div>
            </Show>
          </Show>
        </Show>
      </div>
    </>
  );
};
