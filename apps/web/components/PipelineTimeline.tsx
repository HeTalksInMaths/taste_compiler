/**
 * Static pipeline timeline showing the sequence of EvalWeaver stages.
 */
export default function PipelineTimeline() {
  const stages = [
    "Research",
    "Taste Map",
    "Scorer Evolution",
    "Pair Tests",
    "Repair",
    "Rewrite",
  ];

  return (
    <div className="panel pipeline-timeline">
      <div className="panel-header">Pipeline</div>
      <div className="timeline-stages">
        {stages.map((stage, i) => (
          <span key={stage} className="timeline-stage">
            {stage}
            {i < stages.length - 1 && <span className="timeline-arrow"> → </span>}
          </span>
        ))}
      </div>
    </div>
  );
}
