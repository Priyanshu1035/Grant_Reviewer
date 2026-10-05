import axios from "axios";

const api = axios.create({
  baseURL: "http://127.0.0.1:8000",
  headers: {
    "Content-Type": "application/json",
  },
});

export interface RequirementResult {
  requirement_id: number;
  mapping_id: number | null;
  requirement: string;
  mandatory: boolean;
  category: string;
  status: string;
  confidence: number;
  reason: string;

  evidence: {
    source_text: string;
    page_number: number | null;
  }[];
}

export interface AssessmentSummary {
  assessment_id: number;
  status: string;
  guideline_version_id: number;
  application_version_id: number;

  completion: {
    percentage: number;
    mandatory_requirements: number;
    satisfied_requirements: number;
  };

  mapping_summary: {
    supported: number;
    weak: number;
    missing: number;
    ambiguous: number;
  };

  supporting_documents: {
    provided: number;
    missing: number;
    missing_documents: {
      requirement_id: number;
      requirement: string;
      document_type: string;
    }[];
  };

  clarification_questions: number;
  unsupported_claims: number;

  requirements: RequirementResult[];

  disclaimer: string;
}

export async function getAssessmentSummary(
  assessmentId: number
): Promise<AssessmentSummary> {
  const response = await api.get(
    `/assessments/${assessmentId}/summary`
  );

  return response.data;
}

export async function getAssessment(
  assessmentId: number
) {
  const response = await api.get(
    `/assessments/${assessmentId}`
  );

  return response.data;
}

export async function reviewMapping(
  mappingId: number,
  reviewStatus: "CONFIRMED" | "CORRECTED" | "REJECTED",
  correctedStatus?: "SUPPORTED" | "MISSING" | "WEAK" | "AMBIGUOUS",
  correctedReason?: string,
  reviewReason?: string
) {
  const response = await api.patch(
    `/guidelines/mappings/${mappingId}/review`,
    {
      review_status: reviewStatus,
      corrected_status: correctedStatus,
      corrected_reason: correctedReason,
      review_reason: reviewReason,
    }
  );

  return response.data;
}

export async function completeAssessment(assessmentId: number) {
  const response = await api.post(
    `/assessments/${assessmentId}/complete-review`
  );

  return response.data;
}

export default api;