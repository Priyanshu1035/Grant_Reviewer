import { useState } from "react";
import "./App.css";
import Assessment from "./pages/Assessment";

function App() {
  const [showAssessment, setShowAssessment] = useState(false);

  if (showAssessment) {
    return (
      <div>
        <button
          className="back-button"
          onClick={() => setShowAssessment(false)}
        >
          ← Back to Dashboard
        </button>

        <Assessment />
      </div>
    );
  }

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>Grant Application Reviewer</h1>
          <p>
            Review your funding application against grant requirements.
          </p>
        </div>
      </header>

      <main className="dashboard">
        <section className="welcome-card">
          <h2>Grant Completeness Review</h2>

          <p>
            Upload a grant guideline and draft application to identify
            requirements, missing evidence, and supporting documents.
          </p>

          <button
            className="primary-button"
            onClick={() => setShowAssessment(true)}
          >
            View Assessment
          </button>
        </section>

        <section className="stats">
          <div className="stat-card">
            <span>Assessments</span>
            <strong>1</strong>
          </div>

          <div className="stat-card">
            <span>In Progress</span>
            <strong>1</strong>
          </div>

          <div className="stat-card">
            <span>Completed</span>
            <strong>0</strong>
          </div>
        </section>

        <section className="recent-section">
          <h2>Recent Assessments</h2>

          <div className="assessment-item">
            <div>
              <strong>Grant Assessment #1</strong>
              <p>Assessment ID: 1</p>
            </div>

            <button
              className="secondary-button"
              onClick={() => setShowAssessment(true)}
            >
              Open
            </button>
          </div>
        </section>

        <p className="disclaimer">
          This assessment is a completeness review and does not constitute an
          authoritative funding or legal eligibility decision.
        </p>
      </main>
    </div>
  );
}

export default App;