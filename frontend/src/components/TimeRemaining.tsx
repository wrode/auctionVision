import { createSignal, createEffect, Show } from 'solid-js';

interface TimeRemainingProps {
  endTime?: string;
  showText?: boolean;
}

function formatTimeRemaining(ms: number): string {
  if (ms <= 0) return 'Ended';

  const totalSeconds = Math.floor(ms / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }
  return `${seconds}s`;
}

function getTimeRemainingMs(endTime: string): number {
  return new Date(endTime).getTime() - new Date().getTime();
}

function getTimeClass(ms: number): string {
  if (ms <= 0) return 'time-remaining';
  const hours = ms / (1000 * 3600);
  if (hours < 2) return 'time-remaining critical';
  if (hours < 12) return 'time-remaining warning';
  return 'time-remaining normal';
}

export const TimeRemaining = (props: TimeRemainingProps) => {
  const [timeRemaining, setTimeRemaining] = createSignal('');
  const [cssClass, setCssClass] = createSignal('time-remaining');

  createEffect(() => {
    if (!props.endTime) {
      setTimeRemaining('Unknown');
      return;
    }

    const updateTime = () => {
      const ms = getTimeRemainingMs(props.endTime!);
      setTimeRemaining(formatTimeRemaining(ms));
      setCssClass(getTimeClass(ms));
    };

    updateTime();
    const interval = setInterval(updateTime, 1000);

    return () => clearInterval(interval);
  });

  return (
    <Show when={props.endTime} fallback={<span class="time-remaining">—</span>}>
      <div class={cssClass()}>
        <span>⏱</span>
        <Show when={props.showText !== false}>{timeRemaining()}</Show>
      </div>
    </Show>
  );
};
