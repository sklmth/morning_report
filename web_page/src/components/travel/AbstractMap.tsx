import type { CSSProperties } from 'react';
import type { TravelDestination } from '@/types/site';

type AbstractMapProps = {
  destinations: TravelDestination[];
  activeCity: string;
  onSelect: (city: string) => void;
};

export function AbstractMap({ destinations, activeCity, onSelect }: AbstractMapProps) {
  const routePoints = destinations.map((destination) => `${destination.mapPosition.x},${destination.mapPosition.y}`).join(' ');

  return (
    <div className="map-frame" aria-label="连接筛选后旅行目的地的抽象路线地图">
      <svg className="map-route-svg" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <polyline className="map-route-path" points={routePoints} />
      </svg>
      {destinations.map((destination) => (
        <button
          className={`map-node-button ${activeCity === destination.city ? 'is-active' : ''}`}
          type="button"
          key={destination.city}
          onClick={() => onSelect(destination.city)}
          style={{ left: `${destination.mapPosition.x}%`, top: `${destination.mapPosition.y}%`, '--node-color': destination.color } as CSSProperties}
          aria-pressed={activeCity === destination.city}
          aria-label={`查看 ${destination.city}，${destination.country}`}
        >
          <span className="map-node-dot" />
          <span className="map-node-label">{destination.city}</span>
        </button>
      ))}
      <span className="map-caption">路线片段 / 2019—2026</span>
    </div>
  );
}
