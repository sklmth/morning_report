import { Link2, Sparkles } from 'lucide-react';
import type { GameChapter } from '@/types/site';

type CoopPuzzleBoardProps = {
  chapter: GameChapter;
  sparkChoice: string | null;
  echoChoice: string | null;
  isSolved: boolean;
  sync: number;
};

export function CoopPuzzleBoard({ chapter, sparkChoice, echoChoice, isSolved, sync }: CoopPuzzleBoardProps) {
  const ready = Boolean(sparkChoice && echoChoice);
  const status = isSolved
    ? `桥梁已修复，已解锁「${chapter.relic.name}」。`
    : ready
      ? '两段信号已经靠近，但桥还没有稳定下来。'
      : '请在两个世界各选择一条路线，启动共同信号。';

  return (
    <section className={`puzzle-board ${isSolved ? 'is-solved' : ''}`} aria-label="共同谜题面板">
      <div className="puzzle-heading"><Link2 size={17} aria-hidden="true" /><span>共用桥梁谜题</span><strong>同步 {sync}%</strong></div>
      <p>{chapter.intro}</p>
      <div className="sync-meter" aria-label={`同步进度 ${sync}%`}><span style={{ width: `${sync}%` }} /></div>
      <div className="puzzle-status" aria-live="polite">
        {isSolved && <Sparkles size={17} aria-hidden="true" />}
        <span>{status}</span>
      </div>
    </section>
  );
}
