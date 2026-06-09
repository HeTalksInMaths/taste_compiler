import Link from "next/link";

export default function Home() {
  return (
    <main className="landing">
      <header className="landing-header">
        <h1 className="landing-title">Taste Compiler</h1>
        <p className="landing-tagline">Agents that learn what &apos;good&apos; means</p>
        <p className="landing-pipeline">
          Research → Taste Map → Scorer Evolution → Pair Tests → Repair → Rewrite
        </p>
      </header>

      <section className="panel landing-form">
        <div className="form-group">
          <label className="form-label" htmlFor="goal-description">Goal description</label>
          <textarea
            id="goal-description"
            className="form-input"
            placeholder="Describe what 'good' means for your use case..."
            rows={3}
          />
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="goal-variable">Goal variable</label>
          <select id="goal-variable" className="form-input">
            <option value="concise">concise</option>
            <option value="persuasive">persuasive</option>
            <option value="technical_clarity">technical_clarity</option>
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Provider</label>
          <div className="provider-options">
            <label className="provider-option">
              <input type="radio" name="provider" value="mock" defaultChecked />
              <span className="badge-red">mock/static</span>
            </label>
            <label className="provider-option">
              <input type="radio" name="provider" value="bedrock-metadata" />
              <span className="badge-amber">bedrock metadata-only</span>
            </label>
            <label className="provider-option">
              <input type="radio" name="provider" value="bedrock-live" />
              <span className="badge-green">bedrock live research</span>
            </label>
          </div>
        </div>

        <div className="landing-actions">
          <Link href="/runs/demo" className="btn btn-primary">
            View demo run
          </Link>
          <button className="btn btn-disabled" disabled>
            Start run — Coming soon
          </button>
        </div>
      </section>
    </main>
  );
}
