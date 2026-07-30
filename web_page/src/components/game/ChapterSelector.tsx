import { Check } from 'lucide-react';
import type { GameChapter } from '@/types/site';

type ChapterSelectorProps = {
  chapters: GameChapter[];
  activeChapterId: string;
  completedChapterIds: string[];
  onSelect: (id: string) => void;
};

export function ChapterSelector({ chapters, activeChapterId, completedChapterIds, onSelect }: ChapterSelectorProps) {
  return (
    <nav className="chapter-list" aria-label="协作章节">
      {chapters.map((chapter) => {
        const isActive = chapter.id === activeChapterId;
        const isComplete = completedChapterIds.includes(chapter.id);
        return (
          <button
            className={`chapter ${isActive ? 'is-active' : ''} ${isComplete ? 'is-complete' : ''}`}
            type="button"
            key={chapter.id}
            onClick={() => onSelect(chapter.id)}
            aria-current={isActive ? 'step' : undefined}
          >
            <span>{chapter.index} / {chapter.realm}</span>
            <strong>{chapter.title}</strong>
            <p>{chapter.objective}</p>
            {isComplete && <small><Check size={14} aria-hidden="true" /> 已修复</small>}
          </button>
        );
      })}
    </nav>
  );
}
