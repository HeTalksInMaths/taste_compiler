import type { TasteCompilerRun } from "@/lib/types";
import { classifyProvider } from "@/lib/providerStatus";

interface RunHeaderProps {
  run: TasteCompilerRun;
}

/**
 * Displays run_id, goal, raw_text, and ProviderStatus badge.
 */
export default function RunHeader({ run }: RunHeaderProps) {
  const status = classifyProvider(run.run_metadata);

  // Map badge value to CSS class
  const badgeClass =
    status.badge === "green"
      ? "badge-green"
      : status.badge === "amber"
        ? "badge-amber"
        : status.badge === "red"
          ? "badge-red"
          : "badge-red"; // red-amber falls back to red styling

  return (
    <header className="run-header">
      <div className="run-header-top">
        <h1 className="run-id">{run.run_id}</h1>
        <span className={badgeClass}>{status.label}</span>
      </div>
      <p className="run-goal">{run.goal}</p>
      {run.raw_text && <p className="run-raw-text">{run.raw_text}</p>}
    </header>
  );
}
