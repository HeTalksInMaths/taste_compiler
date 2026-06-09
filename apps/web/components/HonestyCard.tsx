import type { RunMetadata } from "@/lib/types";
import { classifyProvider, getGenerationSource } from "@/lib/providerStatus";

interface HonestyCardProps {
  metadata: RunMetadata;
}

/**
 * First-screen required component. Summarizes what is live vs deterministic.
 */
export default function HonestyCard({ metadata }: HonestyCardProps) {
  const status = classifyProvider(metadata);
  const scorerSource = getGenerationSource(metadata, "scorer");
  const pairSource = getGenerationSource(metadata, "pairs");

  const badgeClass =
    status.badge === "green"
      ? "badge-green"
      : status.badge === "amber"
        ? "badge-amber"
        : status.badge === "red"
          ? "badge-red"
          : "badge-red";

  return (
    <div className="panel honesty-card">
      <div className="panel-header">Honesty Card</div>
      <dl className="honesty-fields">
        <div className="honesty-row">
          <dt>Provider Status</dt>
          <dd><span className={badgeClass}>{status.label}</span></dd>
        </div>
        <div className="honesty-row">
          <dt>Model ID</dt>
          <dd>{metadata.model_id}</dd>
        </div>
        <div className="honesty-row">
          <dt>Generated Steps</dt>
          <dd>
            {metadata.generated_steps.length > 0
              ? metadata.generated_steps.join(", ")
              : "none"}
          </dd>
        </div>
        <div className="honesty-row">
          <dt>Bedrock Calls Made</dt>
          <dd>{metadata.bedrock_calls_made}</dd>
        </div>
        <div className="honesty-row">
          <dt>Evaluator</dt>
          <dd>deterministic</dd>
        </div>
        <div className="honesty-row">
          <dt>Scorer Generation</dt>
          <dd>{scorerSource}</dd>
        </div>
        <div className="honesty-row">
          <dt>Pair Generation</dt>
          <dd>{pairSource}</dd>
        </div>
      </dl>
    </div>
  );
}
