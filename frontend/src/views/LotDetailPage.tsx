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
    <div>
      <div style="padding: var(--spacing-lg); border-bottom: 1px solid var(--border-color); background-color: var(--bg-secondary); display: flex; align-items: center; justify-content: space-between;">
        <h1 class="header-title">Lot Details</h1>
        <button class="action-btn secondary" onclick={handleGoBack}>
          ← Back
        </button>
      </div>

      <div class="content-scroll">
        <Show when={!lotDetail.loading} fallback={<div class="loading"><span class="spinner"></span>Loading lot details...</div>}>
          <Show
            when={lotDetail()}
            fallback={
              <div class="loading">
                <div>Failed to load lot details</div>
                <button class="action-btn" onclick={handleGoBack} style="margin-top: var(--spacing-lg);">
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
