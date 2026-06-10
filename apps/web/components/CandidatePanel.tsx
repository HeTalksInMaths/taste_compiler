import type { SelectedCandidate } from "@/lib/types";
import PanelShell from "./PanelShell";

interface CandidatePanelProps {
  candidate: SelectedCandidate | null;
}

/**
 * Displays the selected candidate details.
 */
export default function CandidatePanel({ candidate }: CandidatePanelProps) {
  if (!candidate) {
    return (
      <div className="panel">
        <div className="panel-header">Selected Candidate</div>
        <p className="no-data">No candidate selected</p>
      </div>
    );
  }

  return (
    <PanelShell title="Selected Candidate" hasData={true}>
      <dl className="candidate-fields">
        <div className="candidate-row">
          <dt>Candidate ID</dt>
          <dd>{candidate.candidate_id}</dd>
        </div>
        <div className="candidate-row">
          <dt>Strategy</dt>
          <dd>{candidate.strategy}</dd>
        </div>
        <div className="candidate-row">
          <dt>Ensemble Score</dt>
          <dd>{candidate.ensemble_score.toFixed(4)}</dd>
        </div>
        <div className="candidate-row">
          <dt>Explanation</dt>
          <dd>{candidate.explanation}</dd>
        </div>
        {candidate.text && (
          <div className="candidate-row">
            <dt>Text</dt>
            <dd className="candidate-text">{candidate.text}</dd>
          </div>
        )}
      </dl>
    </PanelShell>
  );
}
