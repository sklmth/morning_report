import type { GamePlayerPath } from '@/types/site';

type CoopWorldPanelProps = {
  path: GamePlayerPath;
  selectedChoice: string | null;
  onSelect: (choiceId: string) => void;
};

export function CoopWorldPanel({ path, selectedChoice, onSelect }: CoopWorldPanelProps) {
  return (
    <article className={`player-world ${path.tone}`}>
      <p className="eyebrow" style={{ color: 'currentColor' }}>{path.label}</p>
      <h3 className="display">{path.title}</h3>
      <p>{path.copy}</p>
      <div className="path-choices" aria-label={`${path.label} 的路线选择`}>
        {path.choices.map((choice) => {
          const selected = selectedChoice === choice.id;
          return (
            <button
              className={`path-choice ${selected ? 'is-selected' : ''}`}
              type="button"
              key={choice.id}
              onClick={() => onSelect(choice.id)}
              aria-pressed={selected}
            >
              <strong>{choice.label}</strong>
              <span>{choice.detail}</span>
            </button>
          );
        })}
      </div>
    </article>
  );
}
