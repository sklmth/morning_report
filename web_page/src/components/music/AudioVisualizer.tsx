import { useMemo } from 'react';
import { useReducedMotion } from '@/hooks/useReducedMotion';

type AudioVisualizerProps = {
  active: boolean;
  currentTime: number;
  bars: number[];
};

export function AudioVisualizer({ active, currentTime, bars }: AudioVisualizerProps) {
  const reducedMotion = useReducedMotion();
  const spectrum = useMemo(
    () => bars.map((height, index) => {
      if (!active || reducedMotion) return height;
      const pulse = Math.sin(currentTime * 3.2 + index * 0.83) * 10;
      return Math.max(16, Math.min(100, height + pulse));
    }),
    [active, bars, currentTime, reducedMotion],
  );

  return (
    <div className="visualizer" aria-label={active ? '动态音频频谱，正在播放' : '静态音频频谱，播放暂停'} role="img">
      {spectrum.map((height, index) => (
        <span
          key={index}
          style={{
            height: `${height}%`,
            opacity: active ? 1 : 0.38,
            transition: reducedMotion ? 'none' : `height ${280 + (index % 5) * 70}ms var(--ease-out), opacity 220ms ease`,
          }}
        />
      ))}
    </div>
  );
}
