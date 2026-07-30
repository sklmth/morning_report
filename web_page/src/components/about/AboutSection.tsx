import { stats } from '@/content/siteContent';
import { Reveal } from '@/components/common/Reveal';
import { SectionHeader } from '@/components/common/SectionHeader';

const tags = ['视觉叙事', '体验设计', '夜行观察', '声音采集', '协作仪式'];

export function AboutSection() {
  return <section className="section" id="about"><div className="section-inner about-grid"><Reveal><div className="portrait-placeholder" role="img" aria-label="未来个人肖像的抽象占位图"><span /></div></Reveal><Reveal><SectionHeader eyebrow="01 / 关于 About" title="地图从这里开始。" intro="每次出发，都是重新校准：感受城市节奏，听见音乐余温，也记住与同伴一起解开问题的时刻。" /><div className="tag-list">{tags.map((tag) => <span className="tag" key={tag}>{tag}</span>)}</div><div className="rule" /><p className="eyebrow">个人笔记 / Personal note</p><p style={{ maxWidth: '34rem', color: 'var(--muted)', lineHeight: 1.7 }}>我收集列车到站前的停顿、午夜后的第一段副歌，以及让协作成为故事的小小误解。</p></Reveal><Reveal className="stat-stack">{stats.map((stat) => <div className="stat" key={stat.label}><strong>{stat.value}</strong><span>{stat.label}</span></div>)}</Reveal></div></section>;
}
