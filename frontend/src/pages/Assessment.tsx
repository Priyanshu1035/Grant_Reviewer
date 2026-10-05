import { useEffect, useState } from "react";
import {
  getAssessmentSummary,
  reviewMapping,
  completeAssessment
} from "../services/api";
import type { AssessmentSummary } from "../services/api";

function Assessment() {
  const [summary, setSummary] =
    useState<AssessmentSummary | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const assessmentId = 1;

  const handleReview = async (
    mappingId: number,
    reviewStatus: "CONFIRMED" | "CORRECTED" | "REJECTED",
    correctedStatus?:
      | "SUPPORTED"
      | "MISSING"
      | "WEAK"
      | "AMBIGUOUS"
  ) => {
    try {
      await reviewMapping(
        mappingId,
        reviewStatus,
        correctedStatus
      );

      const updatedSummary =
        await getAssessmentSummary(assessmentId);

      setSummary(updatedSummary);
    } catch (err) {
      console.error(err);
      setError("Unable to update review.");
    }
  };

  const handleCompleteReview = async () => {
    try {
        await completeAssessment(assessmentId);

        const updatedSummary = await getAssessmentSummary(assessmentId);
        setSummary(updatedSummary);
    } catch (err) {
        console.error(err);
        setError("Unable to complete review.");
    }
    };

  useEffect(() => {
    async function loadAssessment() {
      try {
        const data =
          await getAssessmentSummary(assessmentId);

        setSummary(data);
      } catch (err) {
        console.error(err);
        setError("Unable to load assessment.");
      } finally {
        setLoading(false);
      }
    }

    loadAssessment();
  }, []);

  if (loading) {
    return (
      <div className="page">
        Loading assessment...
      </div>
    );
  }

  if (error) {
    return (
      <div className="page error">
        {error}
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="page error">
        No assessment found.
      </div>
    );
  }

  return (
    <div className="page">

      {/* Header */}
      <header className="page-header">
        <div>
          <h1>Assessment Review</h1>

          <p>
            Assessment #{summary.assessment_id}
          </p>
        </div>

        <span
          className={`status ${summary.status.toLowerCase()}`}
        >
          {summary.status}
        </span>
      </header>


      {/* Completion */}
      <section className="completion-card">
        <div>
          <p>
            Mandatory requirement completion
          </p>

          <h2>
            {summary.completion.percentage}%
          </h2>
        </div>

        <div className="progress-container">
          <div
            className="progress-bar"
            style={{
              width: `${summary.completion.percentage}%`,
            }}
          />
        </div>

        {summary.status === "REVIEWED" && (
            <div className="reviewed-banner">
            <strong>✓ Review Completed</strong>
            <p>
                All mandatory requirements have been reviewed. This assessment is now
                finalized.
            </p>
            </div>
        )}
      </section>

        {/* Final Review Summary */}
        {summary.status === "REVIEWED" && (
            <section className="final-summary-card">
            <h2>Final Review Summary</h2>

            <div className="final-summary-grid">
                <div>
                <span>Mandatory Requirements</span>
                <strong>
                    {summary.completion.satisfied_requirements} /{" "}
                    {summary.completion.mandatory_requirements}
                </strong>
                </div>

                <div>
                <span>Completion</span>
                <strong>{summary.completion.percentage}%</strong>
                </div>

                <div>
                <span>Missing Documents</span>
                <strong>{summary.supporting_documents.missing}</strong>
                </div>

                <div>
                <span>Clarification Questions</span>
                <strong>{summary.clarification_questions}</strong>
                </div>

                <div>
                <span>Unsupported Claims</span>
                <strong>{summary.unsupported_claims}</strong>
                </div>
            </div>

            <p className="final-summary-disclaimer">
                This is a completeness review based on the supplied grant guideline,
                application, and supporting documents. It does not constitute an
                authoritative funding or legal eligibility decision.
            </p>
            </section>
        )}


      {/* Statistics */}
      <section className="stats">

        <div className="stat-card">
          <span>Mandatory</span>

          <strong>
            {summary.completion.mandatory_requirements}
          </strong>
        </div>

        <div className="stat-card">
          <span>Satisfied</span>

          <strong>
            {summary.completion.satisfied_requirements}
          </strong>
        </div>

        <div className="stat-card">
          <span>Missing</span>

          <strong>
            {summary.mapping_summary.missing}
          </strong>
        </div>

        <div className="stat-card">
          <span>Weak</span>

          <strong>
            {summary.mapping_summary.weak}
          </strong>
        </div>

        <div className="stat-card">
          <span>Ambiguous</span>

          <strong>
            {summary.mapping_summary.ambiguous}
          </strong>
        </div>

      </section>


      {/* Requirements */}
      <section className="requirements-card">

        <h2>Requirements</h2>

        <p>
          The assessment identifies whether the
          application provides evidence for each
          grant requirement.
        </p>

        <div className="requirements-table">

          {/* Table Header */}
          <div className="requirement-header">

            <span>Requirement</span>

            <span>Type</span>

            <span>Status</span>

            <span>Confidence</span>

            <span>Reason & Evidence</span>

            <span>Review</span>

          </div>


          {/* Requirement Rows */}
          {summary.requirements.map(
            (requirement) => (

              <div
                className="requirement-row"
                key={requirement.requirement_id}
              >

                {/* Requirement */}
                <div>
                  <strong>
                    {requirement.requirement}
                  </strong>

                  <small>
                    {requirement.category}
                  </small>
                </div>


                {/* Type */}
                <span>
                  {requirement.mandatory
                    ? "Mandatory"
                    : "Recommended"}
                </span>


                {/* Status */}
                <span
                  className={`requirement-status ${requirement.status.toLowerCase()}`}
                >
                  {requirement.status}
                </span>


                {/* Confidence */}
                <span>
                  {Math.round(
                    requirement.confidence * 100
                  )}
                  %
                </span>


                {/* Reason + Evidence */}
                <div>

                  <strong>
                    {requirement.reason}
                  </strong>


                  {requirement.evidence.length > 0 && (
                    <div className="evidence">

                      <small>
                        Evidence:
                      </small>


                      {requirement.evidence.map(
                        (evidence, index) => (

                          <div
                            className="evidence-item"
                            key={index}
                          >

                            <p>
                              "{evidence.source_text}"
                            </p>


                            {evidence.page_number !== null && (
                              <small>
                                Page{" "}
                                {evidence.page_number}
                              </small>
                            )}

                          </div>

                        )
                      )}

                    </div>
                  )}


                  {requirement.evidence.length === 0 && (
                    <small>
                      No supporting evidence found.
                    </small>
                  )}

                </div>


                {/* Review Actions */}
                <div className="review-actions">

                  {requirement.mapping_id !== null && (
                    <>

                      <button
                        className="review-button confirm"
                        onClick={() =>
                          handleReview(
                            requirement.mapping_id!,
                            "CONFIRMED"
                          )
                        }
                      >
                        Confirm
                      </button>


                      <button
                        className="review-button correct"
                        onClick={() =>
                          handleReview(
                            requirement.mapping_id!,
                            "CORRECTED",
                            "SUPPORTED"
                          )
                        }
                      >
                        Correct → Supported
                      </button>


                      <button
                        className="review-button reject"
                        onClick={() =>
                          handleReview(
                            requirement.mapping_id!,
                            "REJECTED"
                          )
                        }
                      >
                        Reject
                      </button>

                    </>
                  )}

                </div>

              </div>

            )
          )}

        </div>

      </section>

      <div className="complete-review-section">
        <button
            className="primary-button"
            onClick={handleCompleteReview}
            disabled={summary.status === "REVIEWED"}
        >
            {summary.status === "REVIEWED"
            ? "Review Completed"
            : "Complete Review"}
        </button>
       </div>


      {/* Supporting Documents */}
      <section className="requirements-card">

        <h2>Supporting Documents</h2>

        <p>
          Documents identified as required by
          the grant guideline.
        </p>


        <div className="requirement-row">

          <span>
            Provided documents
          </span>

          <strong>
            {summary.supporting_documents.provided}
          </strong>

        </div>


        <div className="requirement-row">

          <span>
            Missing documents
          </span>

          <strong>
            {summary.supporting_documents.missing}
          </strong>

        </div>


        {summary.supporting_documents
          .missing_documents.length > 0 && (

          <div style={{ marginTop: "16px" }}>

            <strong>
              Missing:
            </strong>

            <ul>

              {summary.supporting_documents
                .missing_documents
                .map((document) => (

                  <li
                    key={document.requirement_id}
                  >
                    {document.requirement}
                  </li>

                ))}

            </ul>

          </div>

        )}

      </section>


      {/* Clarification Questions */}
      <section className="requirements-card">

        <h2>
          Clarification Questions
        </h2>

        <p>
          Questions generated from missing,
          weak, or ambiguous evidence.
        </p>

        <strong>
          {summary.clarification_questions} question(s)
        </strong>

      </section>


      {/* Unsupported Claims */}
      <section className="requirements-card">

        <h2>
          Unsupported Claims
        </h2>

        <p>
          Claims in the application that could
          not be supported by the supplied
          evidence.
        </p>

        <strong>
          {summary.unsupported_claims}
          {" "}
          unsupported claim(s)
        </strong>

      </section>


      {/* Disclaimer */}
      <div className="disclaimer">

        <strong>
          Important:
        </strong>{" "}

        {summary.disclaimer}

      </div>

    </div>
  );
}

export default Assessment;