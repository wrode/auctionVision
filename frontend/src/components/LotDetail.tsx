import { Show, For, createSignal } from 'solid-js';
import { LotDetail as LotDetailType } from '../types';
import { ScoreBadge } from './ScoreBadge';
import { TimeRemaining } from './TimeRemaining';
import { ActionBar } from './ActionBar';

interface LotDetailProps {
  lot: LotDetailType;
  onAction?: (action: string) => void;
}

export const LotDetail = (props: LotDetailProps) => {
  const [selectedImage, setSelectedImage] = createSignal(
    props.lot.image_url || '',
  );
  const [expandedSections, setExpandedSections] = createSignal<Set<string>>(
    new Set(),
  );

  const toggleSection = (section: string) => {
    const expanded = new Set(expandedSections());
    if (expanded.has(section)) {
      expanded.delete(section);
    } else {
      expanded.add(section);
    }
    setExpandedSections(expanded);
  };

  const images = () => {
    const all = [props.lot.image_url, ...(props.lot.gallery_images || [])]
      .filter((img) => img);
    return all;
  };

  return (
    <div class="lot-detail-container">
      <div class="lot-detail-gallery">
        <Show when={selectedImage()}>
          <img
            src={selectedImage()}
            alt={props.lot.title}
            class="lot-detail-main-image"
          />
        </Show>

        <Show when={images().length > 1}>
          <div class="lot-detail-thumbnails">
            <For each={images()}>
              {(img) => (
                <img
                  src={img}
                  alt="Lot thumbnail"
                  class={`thumbnail ${selectedImage() === img ? 'active' : ''}`}
                  onclick={() => setSelectedImage(img)}
                />
              )}
            </For>
          </div>
        </Show>
      </div>

      <div class="lot-detail-content">
        <div class="detail-section">
          <h2 class="detail-section-title">{props.lot.title}</h2>

          <div class="detail-field">
            <span class="detail-label">Source</span>
            <span class="detail-value">
              <Show when={props.lot.source_url}>
                <a href={props.lot.source_url} target="_blank" rel="noopener noreferrer">
                  {props.lot.source}
                </a>
              </Show>
              <Show when={!props.lot.source_url}>{props.lot.source}</Show>
            </span>
          </div>

          <Show when={props.lot.lot_number}>
            <div class="detail-field">
              <span class="detail-label">Lot #</span>
              <span class="detail-value">{props.lot.lot_number}</span>
            </div>
          </Show>

          <div class="detail-field">
            <span class="detail-label">Current Bid</span>
            <span class="detail-value">
              <Show when={props.lot.current_bid} fallback="—">
                ${props.lot.current_bid?.toLocaleString()}
              </Show>
            </span>
          </div>

          <Show when={props.lot.estimate_min || props.lot.estimate_max}>
            <div class="detail-field">
              <span class="detail-label">Estimate</span>
              <span class="detail-value">
                ${props.lot.estimate_min?.toLocaleString()} - $
                {props.lot.estimate_max?.toLocaleString()}
              </span>
            </div>
          </Show>

          <div class="detail-field">
            <span class="detail-label">Time Remaining</span>
            <span class="detail-value">
              <TimeRemaining endTime={props.lot.auction_end_time} showText={true} />
            </span>
          </div>
        </div>

        <div class="detail-section">
          <h3 class="detail-section-title">Pricing</h3>

          <Show when={props.lot.hammer_price}>
            <div class="detail-field">
              <span class="detail-label">Hammer Price</span>
              <span class="detail-value">
                ${props.lot.hammer_price?.toLocaleString()}
              </span>
            </div>
          </Show>

          <Show when={props.lot.buyer_premium}>
            <div class="detail-field">
              <span class="detail-label">Buyer Premium</span>
              <span class="detail-value">
                ${props.lot.buyer_premium?.toLocaleString()}
              </span>
            </div>
          </Show>

          <Show when={props.lot.shipping_cost}>
            <div class="detail-field">
              <span class="detail-label">Shipping</span>
              <span class="detail-value">
                ${props.lot.shipping_cost?.toLocaleString()}
              </span>
            </div>
          </Show>

          <Show when={props.lot.total_cost}>
            <div class="detail-field">
              <span class="detail-label">Total Cost</span>
              <span class="detail-value" style="font-weight: 600; color: var(--accent-gold);">
                ${props.lot.total_cost?.toLocaleString()}
              </span>
            </div>
          </Show>
        </div>

        <Show when={props.lot.score_breakdown}>
          <div class="detail-section">
            <h3 class="detail-section-title">Scores</h3>
            <div class="score-breakdown">
              <Show when={props.lot.score_breakdown?.arbitrage_score}>
                <div class="score-item">
                  <div class="score-bar">
                    <div class="score-bar-track">
                      <div
                        class="score-bar-fill"
                        style={{
                          '--score-percent': `${(props.lot.score_breakdown?.arbitrage_score?.value || 0) * 100}%`,
                        }}
                      ></div>
                    </div>
                  </div>
                  <div class="score-value">
                    {(props.lot.score_breakdown?.arbitrage_score?.value || 0).toFixed(2)}
                  </div>
                </div>
                <Show when={props.lot.score_breakdown?.arbitrage_score?.rationale}>
                  <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: var(--spacing-md);">
                    {props.lot.score_breakdown?.arbitrage_score?.rationale}
                  </p>
                </Show>
              </Show>

              <Show when={props.lot.score_breakdown?.norway_gap_score}>
                <div class="score-item">
                  <div class="score-bar">
                    <div class="score-bar-track">
                      <div
                        class="score-bar-fill"
                        style={{
                          '--score-percent': `${(props.lot.score_breakdown?.norway_gap_score?.value || 0) * 100}%`,
                        }}
                      ></div>
                    </div>
                  </div>
                  <div class="score-value">
                    {(props.lot.score_breakdown?.norway_gap_score?.value || 0).toFixed(2)}
                  </div>
                </div>
                <Show when={props.lot.score_breakdown?.norway_gap_score?.rationale}>
                  <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: var(--spacing-md);">
                    {props.lot.score_breakdown?.norway_gap_score?.rationale}
                  </p>
                </Show>
              </Show>

              <Show when={props.lot.score_breakdown?.taste_score}>
                <div class="score-item">
                  <div class="score-bar">
                    <div class="score-bar-track">
                      <div
                        class="score-bar-fill"
                        style={{
                          '--score-percent': `${(props.lot.score_breakdown?.taste_score?.value || 0) * 100}%`,
                        }}
                      ></div>
                    </div>
                  </div>
                  <div class="score-value">
                    {(props.lot.score_breakdown?.taste_score?.value || 0).toFixed(2)}
                  </div>
                </div>
                <Show when={props.lot.score_breakdown?.taste_score?.rationale}>
                  <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: var(--spacing-md);">
                    {props.lot.score_breakdown?.taste_score?.rationale}
                  </p>
                </Show>
              </Show>

              <Show when={props.lot.score_breakdown?.wildcard_score}>
                <div class="score-item">
                  <div class="score-bar">
                    <div class="score-bar-track">
                      <div
                        class="score-bar-fill"
                        style={{
                          '--score-percent': `${(props.lot.score_breakdown?.wildcard_score?.value || 0) * 100}%`,
                        }}
                      ></div>
                    </div>
                  </div>
                  <div class="score-value">
                    {(props.lot.score_breakdown?.wildcard_score?.value || 0).toFixed(2)}
                  </div>
                </div>
                <Show when={props.lot.score_breakdown?.wildcard_score?.rationale}>
                  <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: var(--spacing-md);">
                    {props.lot.score_breakdown?.wildcard_score?.rationale}
                  </p>
                </Show>
              </Show>
            </div>
          </div>
        </Show>

        <Show when={props.lot.description || props.lot.condition}>
          <div class="detail-section">
            <h3 class="detail-section-title">Details</h3>

            <Show when={props.lot.description}>
              <div class="detail-field">
                <span class="detail-label">Description</span>
                <span class="detail-value" style="white-space: pre-wrap;">
                  {props.lot.description}
                </span>
              </div>
            </Show>

            <Show when={props.lot.condition}>
              <div class="detail-field">
                <span class="detail-label">Condition</span>
                <span class="detail-value">{props.lot.condition}</span>
              </div>
            </Show>

            <Show when={props.lot.material}>
              <div class="detail-field">
                <span class="detail-label">Material</span>
                <span class="detail-value">{props.lot.material}</span>
              </div>
            </Show>

            <Show when={props.lot.artist}>
              <div class="detail-field">
                <span class="detail-label">Artist</span>
                <span class="detail-value">{props.lot.artist}</span>
              </div>
            </Show>

            <Show when={props.lot.dimensions}>
              <div class="detail-field">
                <span class="detail-label">Dimensions</span>
                <span class="detail-value">
                  <Show when={props.lot.dimensions?.height}>
                    {props.lot.dimensions?.height}
                  </Show>
                  <Show when={props.lot.dimensions?.height && props.lot.dimensions?.width}>
                    {' × '}
                  </Show>
                  <Show when={props.lot.dimensions?.width}>
                    {props.lot.dimensions?.width}
                  </Show>
                  <Show when={props.lot.dimensions?.depth && (props.lot.dimensions?.height || props.lot.dimensions?.width)}>
                    {' × '}
                  </Show>
                  <Show when={props.lot.dimensions?.depth}>
                    {props.lot.dimensions?.depth}
                  </Show>
                  <Show when={props.lot.dimensions?.unit}>
                    {' '}
                    {props.lot.dimensions?.unit}
                  </Show>
                </span>
              </div>
            </Show>

            <Show when={props.lot.provenance}>
              <div class="detail-field">
                <span class="detail-label">Provenance</span>
                <span class="detail-value">{props.lot.provenance}</span>
              </div>
            </Show>

            <Show when={props.lot.authenticity}>
              <div class="detail-field">
                <span class="detail-label">Authenticity</span>
                <span class="detail-value">{props.lot.authenticity}</span>
              </div>
            </Show>
          </div>
        </Show>

        <Show when={props.lot.agent_enrichment && props.lot.agent_enrichment!.length > 0}>
          <div class="detail-section">
            <h3 class="detail-section-title">Agent Insights</h3>
            <For each={props.lot.agent_enrichment}>
              {(enrichment) => (
                <div
                  style={{
                    'margin-bottom': 'var(--spacing-md)',
                    'padding-bottom': 'var(--spacing-md)',
                    'border-bottom': '1px solid var(--border-color)',
                  }}
                >
                  <div class="collapsible-header" onclick={() => toggleSection(enrichment.agent)}>
                    <span style="font-weight: 600; color: var(--accent-gold);">
                      {enrichment.agent}
                    </span>
                    <span
                      class={`collapsible-toggle ${expandedSections().has(enrichment.agent) ? 'open' : ''}`}
                    >
                      ▼
                    </span>
                  </div>
                  <Show when={expandedSections().has(enrichment.agent)}>
                    <div class="collapsible-content open">
                      <p style="color: var(--text-secondary); white-space: pre-wrap; margin-top: var(--spacing-md);">
                        {enrichment.output}
                      </p>
                      <Show when={enrichment.timestamp}>
                        <p style="font-size: 0.8rem; color: var(--text-muted); margin-top: var(--spacing-sm);">
                          {new Date(enrichment.timestamp!).toLocaleString()}
                        </p>
                      </Show>
                    </div>
                  </Show>
                </div>
              )}
            </For>
          </div>
        </Show>

        <Show when={props.lot.fetch_history && props.lot.fetch_history!.length > 0}>
          <div class="detail-section">
            <h3 class="detail-section-title">History</h3>
            <div class="timeline">
              <For each={props.lot.fetch_history}>
                {(record) => (
                  <div class="timeline-item">
                    <div class="timeline-time">
                      {new Date(record.timestamp).toLocaleString()}
                    </div>
                    <div class="timeline-content">
                      <strong>{record.action}</strong>
                      <Show when={record.details}>
                        <p style="color: var(--text-secondary); margin-top: 4px;">
                          {record.details}
                        </p>
                      </Show>
                    </div>
                  </div>
                )}
              </For>
            </div>
          </div>
        </Show>

        <div onclick={(e) => e.stopPropagation()}>
          <ActionBar lot={props.lot} onAction={props.onAction} />
        </div>
      </div>
    </div>
  );
};
