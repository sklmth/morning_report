type MusicFiltersProps = {
  filters: string[];
  selected: string;
  onChange: (filter: string) => void;
};

export function MusicFilters({ filters, selected, onChange }: MusicFiltersProps) {
  return (
    <div className="music-filters" aria-label="音乐分类">
      {filters.map((filter) => (
        <button
          className={`music-filter ${selected === filter ? 'is-active' : ''}`}
          type="button"
          key={filter}
          onClick={() => onChange(filter)}
          aria-pressed={selected === filter}
        >
          {filter}
        </button>
      ))}
    </div>
  );
}
