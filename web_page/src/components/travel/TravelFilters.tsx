type TravelFiltersProps = {
  filters: string[];
  selected: string;
  onChange: (filter: string) => void;
};

export function TravelFilters({ filters, selected, onChange }: TravelFiltersProps) {
  return (
    <div className="travel-toolbar" aria-label="按区域筛选目的地">
      <span className="travel-toolbar-label">按区域探索</span>
      <div className="travel-filters">
        {filters.map((filter) => (
          <button
            className={`travel-filter ${selected === filter ? 'is-selected' : ''}`}
            type="button"
            key={filter}
            aria-pressed={selected === filter}
            onClick={() => onChange(filter)}
          >
            {filter}
          </button>
        ))}
      </div>
    </div>
  );
}
