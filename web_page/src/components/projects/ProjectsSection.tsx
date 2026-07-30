import { useEffect, useMemo, useState, type CSSProperties } from 'react';
import { ArrowUpRight, ChevronDown, ChevronUp, Layers3 } from 'lucide-react';
import { projects } from '@/content/siteContent';
import { Reveal } from '@/components/common/Reveal';
import { SectionHeader } from '@/components/common/SectionHeader';
import type { Project } from '@/types/site';

const filters = ['全部', ...Array.from(new Set(projects.map((project) => project.category)))];

function ProjectCard({ project, isActive, isExpanded, onSelect, onToggleExpand }: {
  project: Project;
  isActive: boolean;
  isExpanded: boolean;
  onSelect: (id: string) => void;
  onToggleExpand: (id: string) => void;
}) {
  return (
    <article className={`project-card ${isActive ? 'is-active' : ''} ${isExpanded ? 'is-expanded' : ''}`} style={{ '--project-accent': project.accent } as CSSProperties}>
      <button className="project-select" type="button" onClick={() => onSelect(project.id)} aria-pressed={isActive}>
        <span>{project.year} / {project.category}</span>
        <strong>{project.title}</strong>
        <small>{project.role}</small>
      </button>
      <button className="project-expand" type="button" onClick={() => onToggleExpand(project.id)} aria-expanded={isExpanded} aria-label={`${isExpanded ? '收起' : '展开'}《${project.title}》详情`}>
        {isExpanded ? <ChevronUp size={17} /> : <ChevronDown size={17} />}
      </button>
      <div className="project-details" aria-hidden={!isExpanded}><p>{project.outcome}</p><ul>{project.tags.map((tag) => <li key={tag}>{tag}</li>)}</ul></div>
    </article>
  );
}

export function ProjectsSection() {
  const [selectedFilter, setSelectedFilter] = useState('全部');
  const [activeProjectId, setActiveProjectId] = useState(projects[0].id);
  const [expandedProjectId, setExpandedProjectId] = useState<string | null>(null);
  const visibleProjects = useMemo(() => selectedFilter === '全部' ? projects : projects.filter((project) => project.category === selectedFilter), [selectedFilter]);
  const activeProject = visibleProjects.find((project) => project.id === activeProjectId) ?? visibleProjects[0];

  useEffect(() => {
    if (!visibleProjects.some((project) => project.id === activeProjectId)) setActiveProjectId(visibleProjects[0].id);
  }, [activeProjectId, visibleProjects]);

  return (
    <section className="section projects-section" id="projects">
      <div className="section-inner">
        <Reveal><SectionHeader eyebrow="04 / 项目精选" title="有观点的系统。" intro="每个项目都从一个真实的使用场景出发，再把信息、节奏和互动整理成能够反复使用的体验。" /></Reveal>
        <Reveal><div className="projects-toolbar"><span><Layers3 size={15} aria-hidden="true" /> 精选档案 / {String(visibleProjects.length).padStart(2, '0')} 项</span><div className="project-filters" aria-label="项目分类">{filters.map((filter) => <button className={`project-filter ${selectedFilter === filter ? 'is-active' : ''}`} type="button" key={filter} onClick={() => setSelectedFilter(filter)} aria-pressed={selectedFilter === filter}>{filter}</button>)}</div></div></Reveal>
        <Reveal><article className="project-feature" style={{ '--project-accent': activeProject.accent } as CSSProperties}><div className="project-feature-art" aria-hidden="true"><span /><span /><span /></div><div className="project-feature-copy"><span>{activeProject.status} / {activeProject.year}</span><h3 className="display">{activeProject.title}</h3><p>{activeProject.summary}</p><div className="project-meta"><strong>{activeProject.role}</strong><ul>{activeProject.tags.map((tag) => <li key={tag}>{tag}</li>)}</ul></div><span className="project-link-state"><ArrowUpRight size={15} aria-hidden="true" /> 本站案例档案</span></div></article></Reveal>
        <div className="project-grid">{visibleProjects.map((project) => <Reveal key={project.id}><ProjectCard project={project} isActive={activeProject.id === project.id} isExpanded={expandedProjectId === project.id} onSelect={setActiveProjectId} onToggleExpand={(id) => setExpandedProjectId((current) => current === id ? null : id)} /></Reveal>)}</div>
      </div>
    </section>
  );
}
