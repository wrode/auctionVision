import { Show } from 'solid-js';

interface ViewHeaderProps {
  title: string;
  lotCount?: number;
  lastRefreshed?: string;
  onRefresh?: () => void;
  loading?: boolean;
}

function formatLastRefreshed(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

export const ViewHeader = (props: ViewHeaderProps) => {
  return (
    <div class="content-header">
      <div>
        <h1 class="header-title">{props.title}</h1>
      </div>
      <div class="header-info">
        <Show when={props.lotCount !== undefined}>
          <span>{props.lotCount} lots</span>
        </Show>
        <Show when={props.lastRefreshed}>
          <span>Updated {formatLastRefreshed(props.lastRefreshed!)}</span>
        </Show>
        <Show when={props.onRefresh}>
          <button
            class="action-btn secondary"
            onclick={props.onRefresh}
            disabled={props.loading}
            title="Refresh this view"
          >
            <Show when={!props.loading} fallback={<span class="spinner"></span>}>
              🔄
            </Show>
          </button>
        </Show>
      </div>
    </div>
  );
};
