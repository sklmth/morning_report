import { useEffect, useMemo, useState } from 'react';
import { tracks } from '@/content/siteContent';
import { Reveal } from '@/components/common/Reveal';
import { SectionHeader } from '@/components/common/SectionHeader';
import { ListeningNotes } from './ListeningNotes';
import { MusicFilters } from './MusicFilters';
import { MusicPlayerShell } from './MusicPlayerShell';
import { TrackList } from './TrackList';

const categories = ['全部', ...Array.from(new Set(tracks.map((track) => track.category)))];

export function MusicSection() {
  const [selectedCategory, setSelectedCategory] = useState('全部');
  const [activeTrackId, setActiveTrackId] = useState(tracks[0].id);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [volume, setVolume] = useState(0.7);
  const [muted, setMuted] = useState(false);

  const visibleTracks = useMemo(
    () => selectedCategory === '全部' ? tracks : tracks.filter((track) => track.category === selectedCategory),
    [selectedCategory],
  );
  const activeTrack = visibleTracks.find((track) => track.id === activeTrackId) ?? visibleTracks[0];

  useEffect(() => {
    if (!visibleTracks.some((track) => track.id === activeTrackId)) {
      setActiveTrackId(visibleTracks[0].id);
    }
  }, [activeTrackId, visibleTracks]);

  useEffect(() => {
    setCurrentTime(0);
  }, [activeTrackId]);

  useEffect(() => {
    if (!isPlaying) return undefined;
    const timer = window.setInterval(() => {
      setCurrentTime((time) => Math.min(time + 1, activeTrack.durationSeconds));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [activeTrack.durationSeconds, isPlaying]);

  useEffect(() => {
    if (!isPlaying || currentTime < activeTrack.durationSeconds) return;
    const index = visibleTracks.findIndex((track) => track.id === activeTrack.id);
    const nextIndex = (index + 1) % visibleTracks.length;
    setActiveTrackId(visibleTracks[nextIndex].id);
    setCurrentTime(0);
  }, [activeTrack.durationSeconds, activeTrack.id, currentTime, isPlaying, visibleTracks]);

  const selectTrack = (id: string) => {
    setActiveTrackId(id);
    setIsPlaying(false);
  };

  const changeTrack = (direction: 1 | -1) => {
    const index = visibleTracks.findIndex((track) => track.id === activeTrack.id);
    const nextIndex = (index + direction + visibleTracks.length) % visibleTracks.length;
    selectTrack(visibleTracks[nextIndex].id);
  };

  const handleTogglePlayback = () => setIsPlaying((playing) => !playing);
  const handleSeek = (time: number) => setCurrentTime(time);
  const handleVolumeChange = (nextVolume: number) => {
    setVolume(nextVolume);
    setMuted(nextVolume === 0);
  };
  const handleToggleMute = () => setMuted((current) => !current);

  return (
    <section className="section music-section" id="music">
      <div className="section-inner">
        <Reveal>
          <SectionHeader
            eyebrow="03 / 声音档案"
            title="让房间变成一段频率。"
            intro="音乐不是背景。它是旅途结束后，仍然留在身体里的场景。选择一段信号，让它陪你继续向前。"
          />
        </Reveal>
        <Reveal><div className="music-toolbar"><span>精选信号 / 本地演示播放</span><MusicFilters filters={categories} selected={selectedCategory} onChange={setSelectedCategory} /></div></Reveal>
        <Reveal><MusicPlayerShell track={activeTrack} isPlaying={isPlaying} currentTime={currentTime} volume={volume} muted={muted} onTogglePlayback={handleTogglePlayback} onPrevious={() => changeTrack(-1)} onNext={() => changeTrack(1)} onSeek={handleSeek} onVolumeChange={handleVolumeChange} onToggleMute={handleToggleMute} /></Reveal>
        <div className="music-details-grid">
          <Reveal><TrackList tracks={visibleTracks} activeTrackId={activeTrack.id} onSelect={selectTrack} /></Reveal>
          <Reveal><ListeningNotes track={activeTrack} /></Reveal>
        </div>
      </div>
    </section>
  );
}
