"use client";

import { useViewMode } from "@/providers/ViewModeProvider";

interface ArtifactDebugPanelProps {
  artifacts: Record<string, unknown>;
}

/**
 * Collapsible JSON viewer for raw artifact data.
 * Client Component for interactivity (expand/collapse).
 * Only visible in dev mode.
 */
export default function ArtifactDebugPanel({ artifacts }: ArtifactDebugPanelProps) {
  const { mode } = useViewMode();

  if (mode !== "dev") {
    return null;
  }

  const keys = Object.keys(artifacts);

  if (keys.length === 0) {
    return (
      <div className="panel">
        <div className="panel-header">Artifact Debug</div>
        <p className="no-data">No artifacts available</p>
      </div>
    );
  }

  return (
    <div className="panel artifact-debug">
      <div className="panel-header">Artifact Debug</div>
      <div className="artifact-sections">
        {keys.map((key) => (
          <details key={key} className="artifact-detail">
            <summary className="artifact-summary">{key}</summary>
            <pre className="artifact-json">
              {JSON.stringify(artifacts[key], null, 2)}
            </pre>
          </details>
        ))}
      </div>
    </div>
  );
}
