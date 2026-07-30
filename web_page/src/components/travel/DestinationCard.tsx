import type { CSSProperties } from 'react';
import { ChevronDown, ChevronUp, MapPin } from 'lucide-react';
import type { TravelDestination } from '@/types/site';

type DestinationCardProps = {
  destination: TravelDestination;
  index: number;
  isActive: boolean;
  isExpanded: boolean;
  onSelect: (city: string) => void;
  onToggleExpand: (city: string) => void;
};

export function DestinationCard({ destination, index, isActive, isExpanded, onSelect, onToggleExpand }: DestinationCardProps) {
  return (
    <article className={`destination-card ${isActive ? 'is-active' : ''} ${isExpanded ? 'is-expanded' : ''}`} style={{ '--card-color': destination.color } as CSSProperties}>
      <button className="destination-select" type="button" onClick={() => onSelect(destination.city)} aria-pressed={isActive}>
        <span className="destination-index">{String(index + 1).padStart(2, '0')} / {destination.date}</span>
        <h3 className="display destination-name">{destination.city}</h3>
        <span className="destination-meta"><MapPin size={14} aria-hidden /> {destination.country} · {destination.coordinates}</span>
        <p className="destination-note">{destination.note}</p>
        <p className="destination-track">配乐：{destination.track}</p>
      </button>
      <button className="destination-expand" type="button" onClick={() => onToggleExpand(destination.city)} aria-expanded={isExpanded} aria-label={`${isExpanded ? '收起' : '展开'} ${destination.city} 的故事`}>
        {isExpanded ? <ChevronUp size={17} /> : <ChevronDown size={17} />}
      </button>
      <div className="destination-details" aria-hidden={!isExpanded}>
        <p>{destination.story}</p>
        <ul>{destination.highlights.map((highlight) => <li key={highlight}>{highlight}</li>)}</ul>
      </div>
    </article>
  );
}
