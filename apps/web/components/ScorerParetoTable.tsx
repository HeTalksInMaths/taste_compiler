import type { ScorerEntry } from "@/lib/types";
import PanelShell from "./PanelShell";

interface ScorerParetoTableProps {
  scorers: ScorerEntry[];
}

/**
 * Table of scorer entries with Pareto frontier membership.
 */
export default function ScorerParetoTable({ scorers }: ScorerParetoTableProps) {
  return (
    <PanelShell title="Scorer Pareto Frontier" hasData={scorers.length > 0}>
      <div className="table-wrapper">
        <table className="scorer-table">
          <thead>
            <tr>
              <th>Scorer ID</th>
              <th>Test Accuracy</th>
              <th>Test Margin</th>
              <th>Pareto Member</th>
              <th>Survived Because</th>
            </tr>
          </thead>
          <tbody>
            {scorers.map((s) => (
              <tr key={s.scorer_id}>
                <td>{s.scorer_id}</td>
                <td>{s.test_accuracy.toFixed(3)}</td>
                <td>{s.test_margin.toFixed(3)}</td>
                <td>
                  {s.pareto_member ? (
                    <span className="badge-green">yes</span>
                  ) : (
                    <span className="badge-gray">no</span>
                  )}
                </td>
                <td>{s.survived_because || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </PanelShell>
  );
}
