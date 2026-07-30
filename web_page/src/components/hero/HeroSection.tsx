import { ArrowDownRight, ArrowUpRight } from 'lucide-react';
import { useCurrentTime } from '@/hooks/useCurrentTime';
import { AtmosphereCanvas } from '@/components/visual/AtmosphereCanvas';

const experienceLinks = [
  { label: '旅行', caption: '地图与记忆', href: '#travel', accent: 'sky' },
  { label: '音乐', caption: '信号与节拍', href: '#music', accent: 'music' },
  { label: '项目', caption: '系统与故事', href: '#projects', accent: 'sky' },
  { label: '协作', caption: '两条路径，一次抵达', href: '#co-op', accent: 'game' },
];

export function HeroSection() {
  const time = useCurrentTime();

  return (
    <>
      <AtmosphereCanvas />
      <div className="hero-copy">
        <p className="eyebrow">个人图谱 / 信号档案 / 共同世界</p>
        <h1 className="display hero-title">与世界<br /><em>一起移动</em>。</h1>
        <p className="hero-intro">在城市间行走，在节拍里停留，在协作中抵达。收藏瞬间，也收藏方向。</p>
      </div>
      <div className="hero-bottom">
        <div className="hero-status" aria-label={`当前本地时间：${time}，上海，UTC+8`}>
          <span>当前信号</span>
          <strong>{time} · Shanghai / UTC+8</strong>
        </div>
        <div className="hero-rail" aria-label="浏览站点主题">
          {experienceLinks.map((link) => (
            <a className={`hero-rail-link ${link.accent}`} href={link.href} key={link.label}>
              <span>{link.label}</span>
              <small>{link.caption}</small>
              <ArrowUpRight size={15} aria-hidden />
            </a>
          ))}
        </div>
        <a className="scroll-cue" href="#about">
          <span /> 开始向下探索 <ArrowDownRight size={15} aria-hidden />
        </a>
      </div>
    </>
  );
}
