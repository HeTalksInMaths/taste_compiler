import Link from "next/link";

export default function Home() {
  return (
    <main className="landing">
      <header className="landing-header">
        <h1 className="landing-title">Taste Compiler</h1>
        <p className="landing-tagline">
          Define quality. Generate scorers. Evaluate at scale.
        </p>
        <div className="landing-pipeline" aria-label="Pipeline stages">
          {[
            "Research",
            "Taste Map",
            "Scorer Evolution",
            "Pair Tests",
            "Repair",
            "Rewrite",
          ].map((stage, i, arr) => (
            <span key={stage}>
              <span className="timeline-stage">{stage}</span>
              {i < arr.length - 1 && (
                <span className="timeline-arrow" aria-hidden="true">
                  {" "}
                  →{" "}
                </span>
              )}
            </span>
          ))}
        </div>
      </header>

      <section className="panel landing-form">
        <div className="form-group">
          <label className="form-label" htmlFor="goal-description">
            Goal description
          </label>
          <textarea
            id="goal-description"
            className="form-input"
            placeholder="Describe what &apos;good&apos; means for your use case..."
            rows={3}
          />
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="goal-variable">
            Quality dimension
          </label>
          <select id="goal-variable" className="form-input">
            <option value="concise">Concise</option>
            <option value="persuasive">Persuasive</option>
            <option value="technical_clarity">Technical clarity</option>
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Data mode</label>
          <div className="provider-options">
            <label className="provider-option">
              <input type="radio" name="provider" value="mock" defaultChecked />
              <span className="badge-gray" title="Uses pre-built static data — no API calls">
                Demo mode
              </span>
            </label>
            <label className="provider-option">
              <input type="radio" name="provider" value="bedrock-metadata" />
              <span className="badge-amber" title="Fetches metadata from Bedrock, no live research">
                Metadata mode
              </span>
            </label>
            <label className="provider-option">
              <input type="radio" name="provider" value="bedrock-live" />
              <span className="badge-green" title="Full live research via Bedrock">
                Live research
              </span>
            </label>
          </div>
        </div>

        <div className="landing-actions">
          <Link href="/runs/demo" className="btn btn-primary">
            View demo run
          </Link>
          <Link href="/create" className="btn btn-primary">
            Try it live
          </Link>
        </div>
      </section>
    </main>
  );
}
