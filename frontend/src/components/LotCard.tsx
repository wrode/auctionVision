import { Show } from 'solid-js';
import { useNavigate } from '@solidjs/router';
import { LotCard as LotCardType } from '../types';
import { ScoreBadge } from './ScoreBadge';

interface LotCardProps {
  lot: LotCardType;
  onAction?: (action: string) => void;
}

export const LotCard = (props: LotCardProps) => {
  const navigate = useNavigate();
  const handleCardClick = () => navigate(`/lots/${props.lot.id}`);
  const scores = () => props.lot.scores || {};

  return (
    <div class="lot-card" onclick={handleCardClick}>
      <Show when={props.lot.image_url} fallback={
        <div class="lot-card-image" style="display: flex; align-items: center; justify-content: center; color: var(--text-secondary); background: var(--bg-secondary); min-height: 180px;">
          No image
        </div>
      }>
        <img src={props.lot.image_url!} alt={props.lot.title} class="lot-card-image" loading="lazy" />
      </Show>

      <div class="lot-card-content">
        <h3 class="lot-card-title">{props.lot.title}</h3>

        <div class="lot-card-prices">
          <div class="price-row">
            <span class="price-label">Auc. Est.</span>
            <span class="price-value">
              {props.lot.estimate_low ? `${props.lot.estimate_low.toLocaleString()} ${props.lot.currency || 'EUR'}` : '\u2014'}
            </span>
          </div>
          <Show when={props.lot.current_bid}>
            <div class="price-row">
              <span class="price-label">Current Bid</span>
              <span class="price-value bid-active">
                {props.lot.current_bid!.toLocaleString()} {props.lot.currency || 'EUR'}
              </span>
            </div>
          </Show>
          <Show when={props.lot.ai_value_low}>
            <div class="price-row">
              <span class="price-label">AI Value Est.</span>
              <span class="price-value ai-value">
                {`${props.lot.ai_value_low?.toLocaleString()}–${props.lot.ai_value_high?.toLocaleString()} ${props.lot.currency || 'EUR'}`}
              </span>
            </div>
          </Show>
        </div>

        <div class="lot-card-scores">
          <Show when={scores().arbitrage != null}>
            <ScoreBadge score={scores().arbitrage ?? undefined} label="Arb" variant="arbitrage" />
          </Show>
          <Show when={scores().taste != null}>
            <ScoreBadge score={scores().taste ?? undefined} label="Taste" variant="taste" />
          </Show>
          <Show when={scores().wildcard != null}>
            <ScoreBadge score={scores().wildcard ?? undefined} label="Wild" variant="wildcard" />
          </Show>
          <Show when={scores().demand != null && (scores().demand ?? 0) > 0}>
            <ScoreBadge score={scores().demand ?? undefined} label="Wanted" variant="demand" />
          </Show>
        </div>

        <Show when={props.lot.lot_url}>
          <a
            href={props.lot.lot_url!}
            target="_blank"
            rel="noopener noreferrer"
            class="lot-card-link"
            onclick={(e: MouseEvent) => e.stopPropagation()}
          >
            View on {props.lot.source} &rarr;
          </a>
        </Show>
      </div>
    </div>
  );
};
