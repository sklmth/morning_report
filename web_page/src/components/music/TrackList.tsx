import { Headphones } from 'lucide-react';
import type { Track } from '@/types/site';

type TrackListProps = {
  tracks: Track[];
  activeTrackId: string;
  onSelect: (id: string) => void;
};

export function TrackList({ tracks, activeTrackId, onSelect }: TrackListProps) {
  return (
    <aside className="playlist-panel" aria-label="曲目列表">
      <div className="playlist-heading">
        <span>信号队列</span>
        <span>{String(tracks.length).padStart(2, '0')} 首</span>
      </div>
      <div className="track-list">
        {tracks.map((track, index) => {
          const isActive = track.id === activeTrackId;
          return (
            <button
              className={`track-row ${isActive ? 'is-active' : ''}`}
              type="button"
              key={track.id}
              onClick={() => onSelect(track.id)}
              aria-current={isActive ? 'true' : undefined}
            >
              <span className="track-number">{String(index + 1).padStart(2, '0')}</span>
              <span className="track-row-copy">
                <strong>{track.title}</strong>
                <small>{track.artist}</small>
              </span>
              <span className="track-row-meta">
                {isActive && <Headphones size={14} aria-hidden="true" />}
                <span>{track.duration}</span>
              </span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
