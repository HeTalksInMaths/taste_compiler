import type { PairSummary } from "@/lib/types";
import PanelShell from "./PanelShell";

interface PairSuitePanelProps {
  pairSummary: PairSummary | null;
}

/**
 * Displays pair suite summary: counts and type distribution.
 */
export default function PairSuitePanel({ pairSummary }: PairSuitePanelProps) {
  return (
    <PanelShell title="Pair Suite" hasData={pairSummary !== null}>
      {pairSummary && (
        <div className="pair-summary">
          <div className="pair-stats">
            <div className="pair-stat">
              <span className="pair-stat-label">Total Pairs</span>
              <span className="pair-stat-value">{pairSummary.total_pairs}</span>
            </div>
            <div className="pair-stat">
              <span className="pair-stat-label">Train</span>
              <span className="pair-stat-value">{pairSummary.train_count}</span>
            </div>
            <div className="pair-stat">
              <span className="pair-stat-label">Test</span>
              <span className="pair-stat-value">{pairSummary.test_count}</span>
            </div>
          </div>
          <div className="pair-distribution">
            <h4 className="pair-dist-label">Type Distribution</h4>
            <ul className="pair-type-list">
              {Object.entries(pairSummary.type_distribution).map(([type, count]) => (
                <li key={type}>
                  <span className="pair-type-name">{type}</span>:{" "}
                  <span className="pair-type-count">{count}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </PanelShell>
  );
}
