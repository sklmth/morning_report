type SectionHeaderProps = { eyebrow: string; title: string; intro?: string; className?: string };

export function SectionHeader({ eyebrow, title, intro, className }: SectionHeaderProps) {
  return <div className={className}>
    <p className="eyebrow">{eyebrow}</p>
    <h2 className="display section-title">{title}</h2>
    {intro && <p className="section-intro">{intro}</p>}
  </div>;
}
