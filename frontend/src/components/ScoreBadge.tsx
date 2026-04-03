import { Show } from 'solid-js';

interface ScoreBadgeProps {
  score?: number;
  label: string;
  variant?: 'arbitrage' | 'taste' | 'wildcard' | 'resale' | 'demand';
  size?: 'sm' | 'md' | 'lg';
}

function getScoreClass(score: number | undefined): string {
  if (score === undefined) return 'score-badge-low';
  if (score > 0.6) return 'score-badge-high';
  if (score > 0.3) return 'score-badge-medium';
  return 'score-badge-low';
}

export const ScoreBadge = (props: ScoreBadgeProps) => {
  const scoreClass = () =>
    props.variant ? `score-badge ${props.variant}` : `score-badge ${getScoreClass(props.score)}`;

  return (
    <span class={scoreClass()} title={`${props.label}: ${props.score?.toFixed(2) ?? 'N/A'}`}>
      <Show when={props.score !== undefined} fallback={'N/A'}>
        {(props.score! * 100).toFixed(0)}%
      </Show>
      {' '}
      {props.label}
    </span>
  );
};
