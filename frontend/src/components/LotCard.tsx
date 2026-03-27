import { Show, For } from 'solid-js';
import { useNavigate } from '@solidjs/router';
import { LotCard as LotCardType } from '../types';
import { ScoreBadge } from './ScoreBadge';
import { TimeRemaining } from './TimeRemaining';
import { ActionBar } from './ActionBar';

interface LotCardProps {
  lot: LotCardType;
  onAction?: (action: string) => void;
}

export const LotCard = (props: LotCardProps) => {
  const navigate = useNavigate();

  const handleCardClick = () => {
    navigate(`/lots/${props.lot.id}`);
  };

  const handleActionClick = (e: MouseEvent) => {
    e.stopPropagation();
  };

  return (
    <div class="lot-card" onclick={handleCardClick}>
      <Show when={props.lot.image_url} fallback={<div class="lot-card-image" style="display: flex; align-items: center; justify-content: center; color: var(--text-secondary);">No image</div>}>
        <img
          src={props.lot.image_url}
          alt={props.lot.title}
          class="lot-card-image"
          loading="lazy"
        />
      </Show>

      <div class="lot-card-content">
        <h3 class="lot-card-title">{props.lot.title}</h3>

        <div class="lot-card-source">{props.lot.source}</div>

        <div class="lot-card-bid-info">
          <div class="current-bid">
            <span class="bid-label">Current Bid</span>
            <Show when={props.lot.current_bid} fallback={<span class="bid-value">—</span>}>
              <span class="bid-value">
                ${props.lot.current_bid?.toLocaleString()}
              </span>
            </Show>
          </div>
          <Show when={props.lot.estimate_min && props.lot.estimate_max}>
            <div class="estimate">
              Est: ${props.lot.estimate_min?.toLocaleString()} - $
              {props.lot.estimate_max?.toLocaleString()}
            </div>
          </Show>
        </div>

        <TimeRemaining endTime={props.lot.auction_end_time} />

        <div class="lot-card-scores">
          <Show when={props.lot.arbitrage_score !== undefined}>
            <ScoreBadge
              score={props.lot.arbitrage_score}
              label="Arb"
              variant="arbitrage"
            />
          </Show>
          <Show when={props.lot.norway_gap_score !== undefined}>
            <ScoreBadge
              score={props.lot.norway_gap_score}
              label="Norway"
              variant="norway"
            />
          </Show>
          <Show when={props.lot.taste_score !== undefined}>
            <ScoreBadge
              score={props.lot.taste_score}
              label="Taste"
              variant="taste"
            />
          </Show>
          <Show when={props.lot.wildcard_score !== undefined}>
            <ScoreBadge
              score={props.lot.wildcard_score}
              label="Wild"
              variant="wildcard"
            />
          </Show>
        </div>

        <Show when={props.lot.rationale}>
          <p class="lot-card-rationale">"{props.lot.rationale}"</p>
        </Show>

        <Show when={props.lot.risk_flags && props.lot.risk_flags!.length > 0}>
          <div class="lot-card-risks">
            <For each={props.lot.risk_flags}>
              {(flag) => <span class="risk-flag">⚠ {flag}</span>}
            </For>
          </div>
        </Show>

        <div onclick={handleActionClick}>
          <ActionBar lot={props.lot} onAction={props.onAction} />
        </div>
      </div>
    </div>
  );
};
