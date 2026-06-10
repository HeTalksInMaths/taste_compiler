import Link from "next/link";
import { loadRun } from "@/lib/dataLoader";
import RunHeader from "@/components/RunHeader";
import HonestyCard from "@/components/HonestyCard";
import PipelineTimeline from "@/components/PipelineTimeline";
import TasteMapPanel from "@/components/TasteMapPanel";
import ScorerParetoTable from "@/components/ScorerParetoTable";
import PairSuitePanel from "@/components/PairSuitePanel";
import RepairPanel from "@/components/RepairPanel";
import CandidatePanel from "@/components/CandidatePanel";
import AgentBatteryPanel from "@/components/AgentBatteryPanel";
import ArtifactDebugPanel from "@/components/ArtifactDebugPanel";
import ModeToggle from "@/components/ModeToggle";

interface RunPageProps {
  params: { runId: string };
}

export default async function RunPage({ params }: RunPageProps) {
  try {
    const run = await loadRun(params.runId);

    return (
      <main className="run-page">
        <div className="run-page-toolbar">
          <ModeToggle />
        </div>
        <RunHeader run={run} />
        <HonestyCard metadata={run.run_metadata} />
        <PipelineTimeline />
        <TasteMapPanel tasteMap={run.taste_map} />
        <ScorerParetoTable scorers={run.scorers} />
        <PairSuitePanel pairSummary={run.pair_summary} />
        <RepairPanel repairSummary={run.repair_summary} />
        <CandidatePanel candidate={run.selected_candidate} />
        <AgentBatteryPanel />
        <ArtifactDebugPanel artifacts={run.raw_artifacts} />

        {/* Cross-link: market-test this scorer */}
        <div style={{ margin: "16px 0", padding: "14px 16px", borderRadius: "6px", border: "1px solid rgba(92,124,250,0.25)", backgroundColor: "rgba(92,124,250,0.06)", display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px" }}>
          <div>
            <div style={{ fontSize: "13px", fontWeight: 600, color: "#e0e0e0" }}>Market-test this scorer</div>
            <div style={{ fontSize: "12px", color: "#888", marginTop: "2px" }}>See how Nemotron personas respond to it in the live market simulation.</div>
          </div>
          <Link href="/market-dynamics/simulations" style={{ fontSize: "12px", fontWeight: 500, padding: "6px 12px", borderRadius: "4px", backgroundColor: "rgba(92,124,250,0.12)", color: "rgb(145,167,255)", textDecoration: "none", whiteSpace: "nowrap" }}>
            View Simulations →
          </Link>
        </div>
      </main>
    );
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";

    return (
      <main className="run-page">
        <div className="panel error-panel">
          <div className="panel-header">Error Loading Run</div>
          <p className="error-message">{message}</p>
          <p className="error-hint">
            Check that the data source is available and the run ID is valid.
          </p>
        </div>
      </main>
    );
  }
}
