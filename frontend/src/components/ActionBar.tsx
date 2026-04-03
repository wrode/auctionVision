import { createSignal, Show } from 'solid-js';
import { apiClient } from '../api';
import { LotCard } from '../types';

interface ActionBarProps {
  lot: LotCard;
  onAction?: (action: string) => void;
}

export const ActionBar = (props: ActionBarProps) => {
  const [loading, setLoading] = createSignal(false);
  const [watched, setWatched] = createSignal(props.lot.user_actions?.includes('watch') ?? false);
  const [archived, setArchived] = createSignal(props.lot.user_actions?.includes('archive') ?? false);

  const handleAction = async (action: 'star' | 'skip' | 'watch' | 'archive') => {
    setLoading(true);
    try {
      await apiClient.postAction(String(props.lot.id), { action });

      switch (action) {
        case 'watch':
          setWatched(!watched());
          break;
        case 'archive':
          setArchived(!archived());
          break;
      }

      props.onAction?.(action);
    } catch (error) {
      console.error(`Action failed: ${action}`, error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div class="action-bar">
      <button
        class="action-btn secondary"
        onclick={() => handleAction('star')}
        disabled={loading()}
        title="Add to favorites"
      >
        ⭐
      </button>
      <button
        class="action-btn secondary"
        onclick={() => handleAction('skip')}
        disabled={loading()}
        title="Skip this lot"
      >
        ⏭
      </button>
      <button
        class={`action-btn secondary ${watched() ? 'success' : ''}`}
        onclick={() => handleAction('watch')}
        disabled={loading()}
        title={watched() ? 'Remove from watchlist' : 'Add to watchlist'}
      >
        👁
      </button>
      <button
        class={`action-btn secondary ${archived() ? 'danger' : ''}`}
        onclick={() => handleAction('archive')}
        disabled={loading()}
        title={archived() ? 'Unarchive' : 'Archive this lot'}
      >
        📦
      </button>
    </div>
  );
};
