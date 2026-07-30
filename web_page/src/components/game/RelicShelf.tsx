import { LockKeyhole, Sparkles } from 'lucide-react';
import type { GameChapter } from '@/types/site';

type RelicShelfProps = {
  chapters: GameChapter[];
  unlockedRelicIds: string[];
};

export function RelicShelf({ chapters, unlockedRelicIds }: RelicShelfProps) {
  return (
    <section className="relic-shelf" aria-label="遗物陈列架">
      <div className="relic-shelf-heading"><span>共同遗物架</span><span>{unlockedRelicIds.length} / {chapters.length}</span></div>
      <div className="relic-list">
        {chapters.map((chapter) => {
          const unlocked = unlockedRelicIds.includes(chapter.relic.id);
          return (
            <article className={`relic-card ${unlocked ? 'is-unlocked' : ''}`} key={chapter.relic.id}>
              {unlocked ? <Sparkles size={17} aria-hidden="true" /> : <LockKeyhole size={17} aria-hidden="true" />}
              <div><strong>{unlocked ? chapter.relic.name : '未显现的遗物'}</strong><p>{unlocked ? chapter.relic.description : '一起完成本章节，才能揭开这段记忆。'}</p></div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
