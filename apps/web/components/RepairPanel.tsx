import type { RepairSummary } from "@/lib/types";
import PanelShell from "./PanelShell";

interface RepairPanelProps {
  repairSummary: RepairSummary | null;
}

/**
 * Displays repair summary and claim supported status.
 */
export default function RepairPanel({ repairSummary }: RepairPanelProps) {
  if (!repairSummary) {
    return (
      <div className="panel">
        <div className="panel-header">Repair</div>
        <p className="no-data">Repair data not available</p>
      </div>
    );
  }

  return (
    <PanelShell title="Repair" hasData={true}>
      <div className="repair-content">
        <p className="repair-summary-text">{repairSummary.honest_repair_summary}</p>
        <p className="repair-claim">
          Repair claim supported:{" "}
          <strong>
            {repairSummary.overall_improvement_claim_supported ? "true" : "false"}
          </strong>
        </p>
      </div>
    </PanelShell>
  );
}
