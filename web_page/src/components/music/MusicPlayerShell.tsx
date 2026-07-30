import type { CSSProperties } from 'react';
import { Pause, Play, SkipBack, SkipForward, Volume2, VolumeX } from 'lucide-react';
import { Button } from '@/components/common/Button';
import type { Track } from '@/types/site';
import { AudioVisualizer } from './AudioVisualizer';

type MusicPlayerShellProps = {
  track: Track;
  isPlaying: boolean;
  currentTime: number;
  volume: number;
  muted: boolean;
  onTogglePlayback: () => void;
  onPrevious: () => void;
  onNext: () => void;
  onSeek: (time: number) => void;
  onVolumeChange: (volume: number) => void;
  onToggleMute: () => void;
};

function formatTime(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.floor(seconds % 60).toString().padStart(2, '0');
  return `${minutes}:${remainder}`;
}

export function MusicPlayerShell({
  track,
  isPlaying,
  currentTime,
  volume,
  muted,
  onTogglePlayback,
  onPrevious,
  onNext,
  onSeek,
  onVolumeChange,
  onToggleMute,
}: MusicPlayerShellProps) {
  const progress = (currentTime / track.durationSeconds) * 100;

  return (
    <div className="music-stage" style={{ '--track-accent': track.accent } as CSSProperties}>
      <div className="music-grid">
        <div className="album-art" aria-hidden="true"><div className="album-disc" /></div>
        <div className="player-shell">
          <span className="track-kicker">正在环绕 · {track.mood}</span>
          <h3 className="display track-title">{track.title}</h3>
          <p className="track-artist">{track.artist}</p>
          <div className="player-controls">
            <Button variant="icon" aria-label="上一首" onClick={onPrevious}><SkipBack size={16} /></Button>
            <Button variant="primary" aria-label={isPlaying ? `暂停《${track.title}》` : `播放《${track.title}》`} aria-pressed={isPlaying} onClick={onTogglePlayback}>
              {isPlaying ? <Pause size={17} fill="currentColor" /> : <Play size={17} fill="currentColor" />}
            </Button>
            <Button variant="icon" aria-label="下一首" onClick={onNext}><SkipForward size={16} /></Button>
          </div>
          <div className="progress-control">
            <input
              className="progress-range"
              type="range"
              min="0"
              max={track.durationSeconds}
              step="1"
              value={Math.min(currentTime, track.durationSeconds)}
              onChange={(event) => onSeek(Number(event.target.value))}
              aria-label={`《${track.title}》播放进度`}
              style={{ '--progress': `${progress}%` } as CSSProperties}
            />
            <div className="track-times"><span>{formatTime(currentTime)}</span><span>{track.duration}</span></div>
          </div>
          <div className="volume-control">
            <Button variant="ghost" aria-label={muted ? '取消静音' : '静音'} aria-pressed={muted} onClick={onToggleMute}>
              {muted || volume === 0 ? <VolumeX size={17} /> : <Volume2 size={17} />}
            </Button>
            <input
              className="volume-range"
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={muted ? 0 : volume}
              onChange={(event) => onVolumeChange(Number(event.target.value))}
              aria-label="播放音量"
            />
            <span>{Math.round((muted ? 0 : volume) * 100)}%</span>
          </div>
          <AudioVisualizer active={isPlaying} currentTime={currentTime} bars={track.visualizer} />
        </div>
      </div>
    </div>
  );
}
