import { Radio } from 'lucide-react';
import type { Track } from '@/types/site';

type ListeningNotesProps = { track: Track };

export function ListeningNotes({ track }: ListeningNotesProps) {
  return (
    <aside className="listening-notes">
      <div className="listening-notes-heading"><Radio size={15} aria-hidden="true" /> <span>聆听笔记</span></div>
      <p>{track.story}</p>
      <ul aria-label={`${track.title} 的标签`}>
        {track.tags.map((tag) => <li key={tag}>{tag}</li>)}
      </ul>
    </aside>
  );
}
