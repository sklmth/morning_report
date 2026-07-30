import { useEffect, useMemo, useState } from 'react';
import { RotateCcw } from 'lucide-react';
import { chapters } from '@/content/siteContent';
import { Button } from '@/components/common/Button';
import { Reveal } from '@/components/common/Reveal';
import { SectionHeader } from '@/components/common/SectionHeader';
import { ChapterSelector } from './ChapterSelector';
import { CoopPuzzleBoard } from './CoopPuzzleBoard';
import { CoopWorldPanel } from './CoopWorldPanel';
import { RelicShelf } from './RelicShelf';

export function GameSection() {
  const [activeChapterId, setActiveChapterId] = useState(chapters[0].id);
  const [sparkChoice, setSparkChoice] = useState<string | null>(null);
  const [echoChoice, setEchoChoice] = useState<string | null>(null);
  const [completedChapterIds, setCompletedChapterIds] = useState<string[]>([]);
  const [unlockedRelicIds, setUnlockedRelicIds] = useState<string[]>([]);

  const activeChapter = useMemo(
    () => chapters.find((chapter) => chapter.id === activeChapterId) ?? chapters[0],
    [activeChapterId],
  );
  const isSolved = sparkChoice === activeChapter.solution.spark && echoChoice === activeChapter.solution.echo;
  const selectedCount = Number(Boolean(sparkChoice)) + Number(Boolean(echoChoice));
  const sync = isSolved ? 100 : selectedCount * 35;

  useEffect(() => {
    setSparkChoice(null);
    setEchoChoice(null);
  }, [activeChapterId]);

  useEffect(() => {
    if (!isSolved) return;
    setCompletedChapterIds((current) => current.includes(activeChapter.id) ? current : [...current, activeChapter.id]);
    setUnlockedRelicIds((current) => current.includes(activeChapter.relic.id) ? current : [...current, activeChapter.relic.id]);
  }, [activeChapter.id, activeChapter.relic.id, isSolved]);

  const resetRun = () => {
    setSparkChoice(null);
    setEchoChoice(null);
    setCompletedChapterIds([]);
    setUnlockedRelicIds([]);
    setActiveChapterId(chapters[0].id);
  };

  return (
    <section className="section game-section" id="co-op">
      <div className="section-inner">
        <Reveal>
          <SectionHeader
            eyebrow="05 / 双人世界"
            title="两条路径，一次抵达。"
            intro="一个原创的双人奇幻冒险：分开的视角不是阻碍，而是通往同一目标的两种感知方式。"
          />
        </Reveal>
        <Reveal className="game-world" style={{ marginTop: '4rem' }}>
          <div className="game-header">
            <div><span>共同目标 / {activeChapter.realm}</span><strong>{activeChapter.title}</strong></div>
            <Button variant="ghost" onClick={resetRun}><RotateCcw size={15} aria-hidden="true" /> 重新开始</Button>
          </div>
          <ChapterSelector chapters={chapters} activeChapterId={activeChapter.id} completedChapterIds={completedChapterIds} onSelect={setActiveChapterId} />
          <div className="coop-grid">
            <CoopWorldPanel path={activeChapter.paths[0]} selectedChoice={sparkChoice} onSelect={setSparkChoice} />
            <CoopWorldPanel path={activeChapter.paths[1]} selectedChoice={echoChoice} onSelect={setEchoChoice} />
            <div className="merge-line" aria-hidden="true">在此<br />同步</div>
          </div>
          <CoopPuzzleBoard chapter={activeChapter} sparkChoice={sparkChoice} echoChoice={echoChoice} isSolved={isSolved} sync={sync} />
          <RelicShelf chapters={chapters} unlockedRelicIds={unlockedRelicIds} />
        </Reveal>
      </div>
    </section>
  );
}
