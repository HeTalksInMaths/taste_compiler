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
