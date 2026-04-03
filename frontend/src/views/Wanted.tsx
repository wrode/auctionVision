import { createResource, Show, For } from 'solid-js';
import { apiClient } from '../api';
import { ViewHeader } from '../components/ViewHeader';
import type { WantedListingCard } from '../types';

function WantedCard(props: { listing: WantedListingCard }) {
  const l = props.listing;

  const matchLabel = () => {
    const reason = l.match_reason || '';
    if (reason.startsWith('brand:')) return reason.replace('brand:', '');
    if (reason.startsWith('designer:')) return reason.replace('designer:', '');
    if (reason.startsWith('price:')) return reason.replace('price:', '');
    return reason;
  };

  const matchType = () => {
    const reason = l.match_reason || '';
    if (reason.startsWith('brand:')) return 'brand';
    if (reason.startsWith('designer:')) return 'designer';
    return 'price';
  };

  return (
    <a href={l.url} target="_blank" rel="noopener" class="wanted-card">
      <div class="wanted-card-header">
        <span class={`wanted-tag wanted-tag--${matchType()}`}>
          {matchLabel()}
        </span>
        <Show when={l.offered_price}>
          <span class="wanted-price">{l.offered_price?.toLocaleString('nb-NO')} kr</span>
        </Show>
      </div>
      <h3 class="wanted-title">{l.title}</h3>
      <div class="wanted-meta">
        <Show when={l.category}>
          <span class="wanted-category">{l.category}</span>
        </Show>
        <Show when={l.buyer_location}>
          <span class="wanted-location">{l.buyer_location}</span>
        </Show>
        <Show when={l.published_text}>
          <span class="wanted-time">{l.published_text}</span>
        </Show>
      </div>
    </a>
  );
}

export const Wanted = () => {
  const [viewData] = createResource(() => apiClient.fetchWanted(200));

  return (
    <>
      <ViewHeader
        title="Wanted"
        lotCount={viewData()?.total}
        loading={viewData.loading}
      />
      <div class="content-scroll">
        <Show
          when={!viewData.loading}
          fallback={<div class="loading"><span class="spinner"></span>Loading wanted listings...</div>}
        >
          <Show
            when={viewData()?.listings && viewData()!.listings.length > 0}
            fallback={<div class="loading">No wanted listings yet. Run: python scripts/run_fetch_wanted.py</div>}
          >
            <div class="wanted-grid">
              <For each={viewData()?.listings}>
                {(listing) => <WantedCard listing={listing} />}
              </For>
            </div>
          </Show>
        </Show>
      </div>
    </>
  );
};
