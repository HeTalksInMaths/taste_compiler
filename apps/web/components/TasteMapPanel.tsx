import type { TasteMap, TasteConcept } from "@/lib/types";
import PanelShell from "./PanelShell";

interface TasteMapPanelProps {
  tasteMap: TasteMap | null;
}

function ConceptList({ concepts, label }: { concepts: TasteConcept[]; label: string }) {
  if (concepts.length === 0) return null;
  return (
    <div className="taste-section">
      <h3 className="taste-section-label">{label}</h3>
      <ul className="taste-concept-list">
        {concepts.map((c) => (
          <li key={c.concept} className="taste-concept">
            <strong>{c.concept}</strong>: {c.description}
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Displays the taste map: rewards, punishes, preserves.
 */
export default function TasteMapPanel({ tasteMap }: TasteMapPanelProps) {
  return (
    <PanelShell title="Taste Map" hasData={tasteMap !== null}>
      {tasteMap && (
        <>
          <ConceptList concepts={tasteMap.rewards} label="Rewards" />
          <ConceptList concepts={tasteMap.punishes} label="Punishes" />
          <ConceptList concepts={tasteMap.preserves} label="Preserves" />
        </>
      )}
    </PanelShell>
  );
}
