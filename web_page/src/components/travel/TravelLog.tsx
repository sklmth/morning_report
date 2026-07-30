import type { CSSProperties } from 'react';
import type { TravelDestination } from '@/types/site';

type TravelLogProps = {
  destinations: TravelDestination[];
  activeCity: string;
  onSelect: (city: string) => void;
};

export function TravelLog({ destinations, activeCity, onSelect }: TravelLogProps) {
  return (
    <div className="travel-log" aria-label="横向旅行记忆画廊">
      {destinations.flatMap((destination) => destination.gallery.map((frame, frameIndex) => (
        <button
          className={`travel-log-card tone-${frame.tone} ${activeCity === destination.city ? 'is-active' : ''}`}
          type="button"
          key={`${destination.city}-${frame.title}`}
          onClick={() => onSelect(destination.city)}
          style={{ '--frame-color': destination.color, '--frame-index': frameIndex } as CSSProperties}
          aria-label={`打开 ${destination.city}：${frame.title}`}
        >
          <span className="travel-log-art" aria-hidden="true"><i /><i /><i /></span>
          <span className="travel-log-city">{destination.city}</span>
          <strong>{frame.title}</strong>
          <small>{frame.caption}</small>
        </button>
      )))}
    </div>
  );
}
