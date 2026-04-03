import { createResource, Show } from 'solid-js';
import { useParams, useNavigate } from '@solidjs/router';
import { apiClient } from '../api';
import { LotDetail } from '../components/LotDetail';

export const LotDetailPage = () => {
  const params = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [lotDetail] = createResource(
    () => params.id,
    (id) => apiClient.fetchLotDetail(id),
  );

  const handleGoBack = () => {
    navigate(-1);
  };

  return (
    <div class="ld-page-wrap">
      <div class="ld-header-bar">
        <button class="ld-back-btn" onclick={handleGoBack}>
          &larr; Back
        </button>
        <Show when={lotDetail()}>
          <span class="ld-header-source">
            {lotDetail()!.source}
            <Show when={lotDetail()!.parsed_fields?.auction_house_name}>
              {' '}&middot; {lotDetail()!.parsed_fields!.auction_house_name}
            </Show>
          </span>
        </Show>
      </div>

      <div class="ld-body">
        <Show when={!lotDetail.loading} fallback={<div class="loading"><span class="spinner"></span>Loading...</div>}>
          <Show
            when={lotDetail()}
            fallback={
              <div class="loading">
                <div>Failed to load lot details</div>
                <button class="action-btn" onclick={handleGoBack} style="margin-top: var(--spacing-md);">
                  Go Back
                </button>
              </div>
            }
          >
            {(lot) => <LotDetail lot={lot()} />}
          </Show>
        </Show>
      </div>
    </div>
  );
};
