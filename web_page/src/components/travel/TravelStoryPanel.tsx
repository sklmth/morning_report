import type { CSSProperties } from 'react';
import { Headphones, MapPin } from 'lucide-react';
import type { TravelDestination } from '@/types/site';

type TravelStoryPanelProps = { destination: TravelDestination };

export function TravelStoryPanel({ destination }: TravelStoryPanelProps) {
  return (
    <article className="travel-story-panel" style={{ '--story-color': destination.color } as CSSProperties}>
      <div className="travel-story-heading">
        <span>{destination.date} / {destination.region}</span>
        <MapPin size={17} aria-hidden />
      </div>
      <h3 className="display">{destination.city}</h3>
      <p className="travel-story-location">{destination.country} · {destination.coordinates}</p>
      <p className="travel-story-copy">{destination.story}</p>
      <ul className="travel-highlights" aria-label={`${destination.city} 的旅行亮点`}>
        {destination.highlights.map((highlight) => <li key={highlight}>{highlight}</li>)}
      </ul>
      <p className="travel-soundtrack"><Headphones size={15} aria-hidden /> {destination.track}</p>
    </article>
  );
}
