from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
import re
from datetime import datetime
from .database import SessionLocal
from .models import (
    Assessment,
    GuidelineVersion,
    ApplicationVersion,
    Requirement,
    Mapping,
    Evidence,
    ClarificationQuestion,
    UnsupportedClaim,
    SupportingDocument
)
from .ai_service import map_requirements_to_application, generate_clarification_questions, detect_unsupported_claims

router = APIRouter(
    prefix="/assessments",
    tags=["Assessments"]
)

def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


@router.post("/")
def create_assessment(
    guideline_version_id: int,
    application_version_id: int
):
    db: Session = SessionLocal()

    try:
        guideline_version = db.get(
            GuidelineVersion,
            guideline_version_id
        )

        if not guideline_version:
            raise HTTPException(
                status_code=404,
                detail="Guideline version not found."
            )

        application_version = db.get(
            ApplicationVersion,
            application_version_id
        )

        if not application_version:
            raise HTTPException(
                status_code=404,
                detail="Application version not found."
            )

        # Make sure the guideline and application
        # belong to the same grant.
        guideline = guideline_version.guideline_id
        application = application_version.application_id

        # Check that both parent records exist
        # and belong to the same grant.
        from .models import Guideline, Application

        guideline_record = db.get(Guideline, guideline)
        application_record = db.get(Application, application)

        if (
            not guideline_record
            or not application_record
        ):
            raise HTTPException(
                status_code=404,
                detail="Guideline or application not found."
            )

        if (
            guideline_record.grant_id
            != application_record.grant_id
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Guideline and application must "
                    "belong to the same grant."
                )
            )

        # Check whether this assessment already exists.
        existing = (
            db.query(Assessment)
            .filter(
                Assessment.guideline_version_id
                == guideline_version_id,
                Assessment.application_version_id
                == application_version_id
            )
            .first()
        )

        if existing:
            return {
                "message": "Assessment already exists.",
                "assessment": {
                    "id": existing.id,
                    "guideline_version_id":
                        existing.guideline_version_id,
                    "application_version_id":
                        existing.application_version_id,
                    "status": existing.status,
                    "completion_percentage":
                        existing.completion_percentage
                }
            }

        # Create assessment.
        assessment = Assessment(
            guideline_version_id=guideline_version_id,
            application_version_id=application_version_id,
            status="DRAFT",
            completion_percentage=0.0
        )

        db.add(assessment)
        db.commit()
        db.refresh(assessment)

        return {
            "message": "Assessment created successfully.",
            "assessment": {
                "id": assessment.id,
                "guideline_version_id":
                    assessment.guideline_version_id,
                "application_version_id":
                    assessment.application_version_id,
                "status": assessment.status,
                "completion_percentage":
                    assessment.completion_percentage,
                "created_at":
                    assessment.created_at
            }
        }

    finally:
        db.close()
        
        
        
@router.post("/{assessment_id}/run")
def run_assessment(assessment_id: int):
    db: Session = SessionLocal()

    try:
        # -----------------------------------
        # 1. Get assessment
        # -----------------------------------

        assessment = db.get(
            Assessment,
            assessment_id
        )

        if not assessment:
            raise HTTPException(
                status_code=404,
                detail="Assessment not found."
            )

        # -----------------------------------
        # 2. Get guideline version
        # -----------------------------------

        guideline_version = db.get(
            GuidelineVersion,
            assessment.guideline_version_id
        )

        if not guideline_version:
            raise HTTPException(
                status_code=404,
                detail="Guideline version not found."
            )

        # -----------------------------------
        # 3. Get application version
        # -----------------------------------

        application_version = db.get(
            ApplicationVersion,
            assessment.application_version_id
        )

        if not application_version:
            raise HTTPException(
                status_code=404,
                detail="Application version not found."
            )

        # -----------------------------------
        # 4. Validate extracted text
        # -----------------------------------

        if not guideline_version.extracted_text:
            raise HTTPException(
                status_code=400,
                detail="Guideline has no extracted text."
            )

        if not application_version.extracted_text:
            raise HTTPException(
                status_code=400,
                detail="Application has no extracted text."
            )

        # -----------------------------------
        # 5. Get requirements
        # -----------------------------------

        requirements = (
            db.query(Requirement)
            .filter(
                Requirement.guideline_version_id
                == guideline_version.id
            )
            .all()
        )

        if not requirements:
            raise HTTPException(
                status_code=400,
                detail="No requirements found for this guideline."
            )

        # -----------------------------------
        # 6. Update assessment status
        # -----------------------------------

        assessment.status = "IN_PROGRESS"
        db.commit()

        # -----------------------------------
        # 7. Run AI mapping
        # -----------------------------------

        results = map_requirements_to_application(
            requirements,
            application_version.extracted_text
        )

        # -----------------------------------
        # 8. Remove old mappings
        # -----------------------------------

        old_mappings = (
            db.query(Mapping)
            .filter(
                Mapping.application_version_id
                == application_version.id
            )
            .all()
        )

        for old_mapping in old_mappings:

            db.query(Evidence).filter(
                Evidence.mapping_id
                == old_mapping.id
            ).delete(
                synchronize_session=False
            )

            db.delete(old_mapping)

        db.flush()

        # -----------------------------------
        # 9. Save new mappings
        # -----------------------------------

        saved_mappings = []

        for result in results:

            # Make sure the requirement actually exists.
            requirement = db.get(
                Requirement,
                result.requirement_id
            )

            if not requirement:
                continue

            mapping = Mapping(
                requirement_id=result.requirement_id,
                application_version_id=
                    application_version.id,
                status=result.status,
                confidence=result.confidence,
                reason=result.reason
            )

            db.add(mapping)
            db.flush()

            # -----------------------------------
            # 10. Save evidence
            # -----------------------------------

            for evidence in result.evidence:

                # Anti-hallucination validation:
                # evidence must actually exist
                # in the supplied application.
                application_text_normalized = normalize_text(
                    application_version.extracted_text
                )

                evidence_text_normalized = normalize_text(
                    evidence.source_text
                )

                if evidence_text_normalized not in application_text_normalized:
                    continue

                db_evidence = Evidence(
                    mapping_id=mapping.id,
                    source_text=evidence.source_text,
                    page_number=evidence.page_number
                )

                db.add(db_evidence)

            saved_mappings.append(mapping)

        db.commit()

        # -----------------------------------
        # 11. Calculate completion
        # -----------------------------------

        mandatory_requirements = [
            requirement
            for requirement in requirements
            if requirement.mandatory
        ]

        mapping_by_requirement = {
            mapping.requirement_id: mapping
            for mapping in saved_mappings
        }

        satisfied = 0

        for requirement in mandatory_requirements:

            mapping = mapping_by_requirement.get(
                requirement.id
            )

            if not mapping:
                continue

            if mapping.status == "SUPPORTED":
                satisfied += 1

        total_mandatory = len(
            mandatory_requirements
        )

        if total_mandatory == 0:
            completion_percentage = 100.0
        else:
            completion_percentage = round(
                (
                    satisfied
                    / total_mandatory
                ) * 100,
                2
            )

        # -----------------------------------
        # 12. Update assessment
        # -----------------------------------

        assessment.completion_percentage = (
            completion_percentage
        )

        assessment.status = "IN_PROGRESS"

        db.commit()
        db.refresh(assessment)

        return {
            "message": "Assessment completed successfully.",
            "assessment": {
                "id": assessment.id,
                "status": assessment.status,
                "guideline_version_id":
                    assessment.guideline_version_id,
                "application_version_id":
                    assessment.application_version_id,
                "completion_percentage":
                    assessment.completion_percentage
            },
            "mapping_count": len(saved_mappings),
            "mandatory_requirements":
                total_mandatory,
            "satisfied_requirements":
                satisfied
        }

    except Exception:

        # Don't leave assessment stuck
        # in IN_PROGRESS if something fails.
        db.rollback()

        assessment = db.get(
            Assessment,
            assessment_id
        )

        if assessment:
            assessment.status = "DRAFT"
            db.commit()

        raise

    finally:
        db.close()
        
        
@router.get("/{assessment_id}")
def get_assessment(assessment_id: int):
    db: Session = SessionLocal()

    try:
        assessment = db.get(
            Assessment,
            assessment_id
        )

        if not assessment:
            raise HTTPException(
                status_code=404,
                detail="Assessment not found."
            )

        guideline_version = db.get(
            GuidelineVersion,
            assessment.guideline_version_id
        )

        application_version = db.get(
            ApplicationVersion,
            assessment.application_version_id
        )

        if not guideline_version:
            raise HTTPException(
                status_code=404,
                detail="Guideline version not found."
            )

        if not application_version:
            raise HTTPException(
                status_code=404,
                detail="Application version not found."
            )

        # Find the latest guideline version
        latest_guideline_version = (
            db.query(GuidelineVersion)
            .filter(
                GuidelineVersion.guideline_id
                == guideline_version.guideline_id
            )
            .order_by(
                GuidelineVersion.version.desc()
            )
            .first()
        )

        # Find the latest application version
        latest_application_version = (
            db.query(ApplicationVersion)
            .filter(
                ApplicationVersion.application_id
                == application_version.application_id
            )
            .order_by(
                ApplicationVersion.version.desc()
            )
            .first()
        )

        guideline_changed = (
            latest_guideline_version.id
            != assessment.guideline_version_id
        )

        application_changed = (
            latest_application_version.id
            != assessment.application_version_id
        )

        is_stale = (
            guideline_changed
            or application_changed
        )

        if is_stale:
            assessment.status = "STALE"
            db.commit()
            db.refresh(assessment)

        return {
            "id": assessment.id,
            "status": assessment.status,
            "guideline_version_id":
                assessment.guideline_version_id,
            "application_version_id":
                assessment.application_version_id,
            "latest_guideline_version_id":
                latest_guideline_version.id,
            "latest_application_version_id":
                latest_application_version.id,
            "guideline_changed":
                guideline_changed,
            "application_changed":
                application_changed,
            "is_stale":
                is_stale,
            "completion_percentage":
                assessment.completion_percentage
        }

    finally:
        db.close()
        
        
@router.post("/{assessment_id}/generate-questions")
def generate_questions(assessment_id: int):
    db: Session = SessionLocal()

    try:
        assessment = db.get(Assessment, assessment_id)

        if not assessment:
            raise HTTPException(
                status_code=404,
                detail="Assessment not found."
            )

        application_version = db.get(
            ApplicationVersion,
            assessment.application_version_id
        )

        if not application_version:
            raise HTTPException(
                status_code=404,
                detail="Application version not found."
            )

        requirements = db.query(Requirement).filter(
            Requirement.guideline_version_id ==
            assessment.guideline_version_id
        ).all()

        mappings = db.query(Mapping).filter(
            Mapping.application_version_id ==
            assessment.application_version_id
        ).all()

        if not mappings:
            raise HTTPException(
                status_code=400,
                detail="Run the assessment before generating questions."
            )

        # Remove previously generated open questions
        db.query(ClarificationQuestion).filter(
            ClarificationQuestion.assessment_id == assessment_id,
            ClarificationQuestion.status == "OPEN"
        ).delete(synchronize_session=False)

        questions = generate_clarification_questions(
            requirements,
            mappings,
            application_version.extracted_text
        )

        saved_questions = []

        for question in questions:

            db_question = ClarificationQuestion(
                assessment_id=assessment_id,
                requirement_id=question["requirement_id"],
                question=question["question"],
                reason=question["reason"],
                status="OPEN"
            )

            db.add(db_question)
            saved_questions.append(db_question)

        db.commit()

        for question in saved_questions:
            db.refresh(question)

        return {
            "message": "Clarification questions generated successfully.",
            "assessment_id": assessment_id,
            "count": len(saved_questions),
            "questions": [
                {
                    "id": question.id,
                    "requirement_id": question.requirement_id,
                    "question": question.question,
                    "reason": question.reason,
                    "status": question.status
                }
                for question in saved_questions
            ]
        }

    finally:
        db.close()
        
        
@router.get("/{assessment_id}/questions")
def get_clarification_questions(assessment_id: int):
    db: Session = SessionLocal()

    try:
        assessment = db.get(Assessment, assessment_id)

        if not assessment:
            raise HTTPException(
                status_code=404,
                detail="Assessment not found."
            )

        questions = db.query(ClarificationQuestion).filter(
            ClarificationQuestion.assessment_id == assessment_id
        ).order_by(
            ClarificationQuestion.created_at.asc()
        ).all()

        return {
            "assessment_id": assessment_id,
            "count": len(questions),
            "questions": [
                {
                    "id": question.id,
                    "requirement_id": question.requirement_id,
                    "question": question.question,
                    "reason": question.reason,
                    "status": question.status,
                    "answer": question.answer,
                    "created_at": question.created_at
                }
                for question in questions
            ]
        }

    finally:
        db.close()
        
        
@router.patch("/{assessment_id}/questions/{question_id}")
def answer_clarification_question(
    assessment_id: int,
    question_id: int,
    answer: str
):
    db: Session = SessionLocal()

    try:
        assessment = db.get(Assessment, assessment_id)

        if not assessment:
            raise HTTPException(
                status_code=404,
                detail="Assessment not found."
            )

        question = (
            db.query(ClarificationQuestion)
            .filter(
                ClarificationQuestion.id == question_id,
                ClarificationQuestion.assessment_id == assessment_id
            )
            .first()
        )

        if not question:
            raise HTTPException(
                status_code=404,
                detail="Clarification question not found."
            )

        if not answer.strip():
            raise HTTPException(
                status_code=400,
                detail="Answer cannot be empty."
            )

        question.answer = answer.strip()
        question.status = "ANSWERED"
        question.answered_at = datetime.utcnow()

        db.commit()
        db.refresh(question)

        return {
            "message": "Clarification question answered successfully.",
            "question": {
                "id": question.id,
                "assessment_id": question.assessment_id,
                "requirement_id": question.requirement_id,
                "question": question.question,
                "reason": question.reason,
                "status": question.status,
                "answer": question.answer,
                "answered_at": question.answered_at
            }
        }

    finally:
        db.close()
        
        
@router.post("/{assessment_id}/detect-unsupported-claims")
def detect_claims(assessment_id: int):
    db: Session = SessionLocal()

    try:
        assessment = db.get(Assessment, assessment_id)

        if not assessment:
            raise HTTPException(
                status_code=404,
                detail="Assessment not found."
            )

        application_version = db.get(
            ApplicationVersion,
            assessment.application_version_id
        )

        if not application_version:
            raise HTTPException(
                status_code=404,
                detail="Application version not found."
            )

        if not application_version.extracted_text:
            raise HTTPException(
                status_code=400,
                detail="Application has no extracted text."
            )

        # Remove previously generated open claims
        db.query(UnsupportedClaim).filter(
            UnsupportedClaim.assessment_id == assessment_id,
            UnsupportedClaim.status == "OPEN"
        ).delete(synchronize_session=False)

        claims = detect_unsupported_claims(
            application_version.extracted_text
        )

        saved_claims = []

        for claim in claims:
            db_claim = UnsupportedClaim(
                assessment_id=assessment_id,
                claim_text=claim["claim_text"],
                reason=claim["reason"],
                status="OPEN"
            )

            db.add(db_claim)
            saved_claims.append(db_claim)

        db.commit()

        for claim in saved_claims:
            db.refresh(claim)

        return {
            "message": "Unsupported claims detected successfully.",
            "assessment_id": assessment_id,
            "count": len(saved_claims),
            "claims": [
                {
                    "id": claim.id,
                    "claim_text": claim.claim_text,
                    "reason": claim.reason,
                    "status": claim.status
                }
                for claim in saved_claims
            ]
        }

    finally:
        db.close()
        

@router.get("/{assessment_id}/unsupported-claims")
def get_unsupported_claims(assessment_id: int):
    db: Session = SessionLocal()

    try:
        assessment = db.get(Assessment, assessment_id)

        if not assessment:
            raise HTTPException(
                status_code=404,
                detail="Assessment not found."
            )

        claims = db.query(UnsupportedClaim).filter(
            UnsupportedClaim.assessment_id == assessment_id
        ).order_by(
            UnsupportedClaim.created_at.asc()
        ).all()

        return {
            "assessment_id": assessment_id,
            "count": len(claims),
            "claims": [
                {
                    "id": claim.id,
                    "claim_text": claim.claim_text,
                    "reason": claim.reason,
                    "status": claim.status,
                    "review_reason": claim.review_reason,
                    "created_at": claim.created_at
                }
                for claim in claims
            ]
        }

    finally:
        db.close()
        
        
@router.get("/{assessment_id}/missing-documents")
def get_missing_documents(assessment_id: int):
    db: Session = SessionLocal()

    try:
        assessment = db.get(Assessment, assessment_id)

        if not assessment:
            raise HTTPException(
                status_code=404,
                detail="Assessment not found."
            )

        requirements = db.query(Requirement).filter(
            Requirement.guideline_version_id ==
            assessment.guideline_version_id,
            Requirement.category == "supporting_document",
            Requirement.mandatory == True
        ).all()

        documents = db.query(SupportingDocument).filter(
            SupportingDocument.application_version_id ==
            assessment.application_version_id
        ).all()

        uploaded_types = {
            document.document_type.lower()
            for document in documents
        }

        results = []

        for requirement in requirements:

            requirement_text = requirement.requirement.lower()

            if "non-profit registration" in requirement_text:
                expected_type = "registration"

            elif "annual report" in requirement_text:
                expected_type = "annual_report"

            else:
                expected_type = requirement.category

            provided = expected_type.lower() in uploaded_types

            results.append({
                "requirement_id": requirement.id,
                "requirement": requirement.requirement,
                "document_type": expected_type,
                "status": "PROVIDED" if provided else "MISSING"
            })

        missing_count = sum(
            1
            for result in results
            if result["status"] == "MISSING"
        )

        return {
            "assessment_id": assessment_id,
            "count": len(results),
            "missing_count": missing_count,
            "documents": results
        }

    finally:
        db.close()
        
        
@router.get("/{assessment_id}/summary")
def get_assessment_summary(assessment_id: int):
    db: Session = SessionLocal()

    try:
        assessment = db.get(Assessment, assessment_id)

        if not assessment:
            raise HTTPException(
                status_code=404,
                detail="Assessment not found."
            )

        requirements = db.query(Requirement).filter(
            Requirement.guideline_version_id ==
            assessment.guideline_version_id
        ).all()

        mappings = db.query(Mapping).filter(
            Mapping.application_version_id ==
            assessment.application_version_id
        ).all()

        mapping_by_requirement = {
            mapping.requirement_id: mapping
            for mapping in mappings
        }

        mandatory_requirements = [
            requirement
            for requirement in requirements
            if requirement.mandatory
        ]

        satisfied = 0
        supported = 0
        weak = 0
        missing = 0
        ambiguous = 0

        requirement_details = []

        for requirement in requirements:

            mapping = mapping_by_requirement.get(requirement.id)

            if not mapping:
                status = "MISSING"

            elif mapping.review_status == "CONFIRMED":
                status = mapping.status

            elif mapping.review_status == "CORRECTED":
                status = mapping.corrected_status

            elif mapping.review_status == "REJECTED":
                status = "REJECTED"

            else:
                status = mapping.status

            is_satisfied = status == "SUPPORTED"

            if mapping:
                if mapping.status == "SUPPORTED":
                    supported += 1
                elif mapping.status == "WEAK":
                    weak += 1
                elif mapping.status == "MISSING":
                    missing += 1
                elif mapping.status == "AMBIGUOUS":
                    ambiguous += 1
            else:
                missing += 1
                
            
            evidence_items = []
            
            if mapping:
                evidence_records = (
                    db.query(Evidence)
                    .filter(Evidence.mapping_id == mapping.id)
                    .all()
                )
            
                for evidence in evidence_records:
                    evidence_items.append({
                        "source_text": evidence.source_text,
                        "page_number": evidence.page_number
                    })

            if requirement.mandatory and is_satisfied:
                satisfied += 1

            requirement_details.append({
                "requirement_id": requirement.id,
                "requirement": requirement.requirement,
                "mandatory": requirement.mandatory,
                "category": requirement.category,
                "status": status,
                "confidence": (
                    mapping.confidence
                    if mapping
                    else None
                ),
                "reason": (
                    mapping.reason
                    if mapping
                    else "No mapping found."
                ),
                "mapping_id": mapping.id if mapping else None,
                "evidence": evidence_items
            })

        total_mandatory = len(mandatory_requirements)

        completion_percentage = (
            round(
                (satisfied / total_mandatory) * 100,
                2
            )
            if total_mandatory > 0
            else 100.0
        )

        supporting_documents = db.query(
            SupportingDocument
        ).filter(
            SupportingDocument.application_version_id ==
            assessment.application_version_id
        ).all()

        supporting_requirements = [
            requirement
            for requirement in mandatory_requirements
            if requirement.category == "supporting_document"
        ]

        provided_documents = len(supporting_documents)

        missing_documents = []

        for requirement in supporting_requirements:

            requirement_text = requirement.requirement.lower()

            if "non-profit registration" in requirement_text:
                expected_type = "registration"
            elif "annual report" in requirement_text:
                expected_type = "annual_report"
            else:
                expected_type = requirement.category

            provided = any(
                document.document_type.lower()
                == expected_type.lower()
                for document in supporting_documents
            )

            if not provided:
                missing_documents.append({
                    "requirement_id": requirement.id,
                    "requirement": requirement.requirement,
                    "document_type": expected_type
                })

        questions_count = db.query(
            ClarificationQuestion
        ).filter(
            ClarificationQuestion.assessment_id ==
            assessment_id,
            ClarificationQuestion.status == "OPEN"
        ).count()

        unsupported_claims_count = db.query(
            UnsupportedClaim
        ).filter(
            UnsupportedClaim.assessment_id ==
            assessment_id,
            UnsupportedClaim.status == "OPEN"
        ).count()

        assessment.completion_percentage = completion_percentage
        db.commit()

        return {
            "assessment_id": assessment.id,
            "status": assessment.status,

            "guideline_version_id":
                assessment.guideline_version_id,

            "application_version_id":
                assessment.application_version_id,

            "completion": {
                "percentage": completion_percentage,
                "mandatory_requirements":
                    total_mandatory,
                "satisfied_requirements":
                    satisfied
            },

            "mapping_summary": {
                "supported": supported,
                "weak": weak,
                "missing": missing,
                "ambiguous": ambiguous
            },

            "supporting_documents": {
                "provided": provided_documents,
                "missing": len(missing_documents),
                "missing_documents": missing_documents
            },

            "clarification_questions": questions_count,

            "unsupported_claims": unsupported_claims_count,

            "requirements": requirement_details,

            "disclaimer": (
                "This assessment is a completeness review based "
                "only on the supplied guideline, application, and "
                "supporting documents. It does not constitute an "
                "authoritative legal or funding-eligibility decision."
            )
        }

    finally:
        db.close()
        
        
@router.post("/{assessment_id}/complete-review")
def complete_review(assessment_id: int):
    db: Session = SessionLocal()

    try:
        assessment = db.get(Assessment, assessment_id)

        if not assessment:
            raise HTTPException(
                status_code=404,
                detail="Assessment not found."
            )

        # -----------------------------------
        # 1. Check whether assessment is stale
        # -----------------------------------

        guideline_version = db.get(
            GuidelineVersion,
            assessment.guideline_version_id
        )

        application_version = db.get(
            ApplicationVersion,
            assessment.application_version_id
        )

        latest_guideline_version = (
            db.query(GuidelineVersion)
            .filter(
                GuidelineVersion.guideline_id
                == guideline_version.guideline_id
            )
            .order_by(
                GuidelineVersion.version.desc()
            )
            .first()
        )

        latest_application_version = (
            db.query(ApplicationVersion)
            .filter(
                ApplicationVersion.application_id
                == application_version.application_id
            )
            .order_by(
                ApplicationVersion.version.desc()
            )
            .first()
        )

        if (
            latest_guideline_version.id
            != assessment.guideline_version_id
            or
            latest_application_version.id
            != assessment.application_version_id
        ):
            assessment.status = "STALE"
            db.commit()

            raise HTTPException(
                status_code=409,
                detail=(
                    "Assessment is stale because the "
                    "guideline or application has changed."
                )
            )

        # -----------------------------------
        # 2. Get mandatory requirements
        # -----------------------------------

        requirements = (
            db.query(Requirement)
            .filter(
                Requirement.guideline_version_id
                == assessment.guideline_version_id
            )
            .all()
        )

        mandatory_requirements = [
            requirement
            for requirement in requirements
            if requirement.mandatory
        ]

        # -----------------------------------
        # 3. Get mappings
        # -----------------------------------

        mappings = (
            db.query(Mapping)
            .filter(
                Mapping.application_version_id
                == assessment.application_version_id
            )
            .all()
        )

        mapping_by_requirement = {
            mapping.requirement_id: mapping
            for mapping in mappings
        }

        # -----------------------------------
        # 4. Make sure every mandatory
        #    requirement has been reviewed
        # -----------------------------------

        for requirement in mandatory_requirements:

            mapping = mapping_by_requirement.get(
                requirement.id
            )

            if not mapping:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Mandatory requirement "
                        f"{requirement.id} has no mapping."
                    )
                )

            if not mapping.review_status:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Mandatory requirement "
                        f"{requirement.id} has not been reviewed."
                    )
                )

            if (
                mapping.review_status == "CORRECTED"
                and not mapping.corrected_status
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Mandatory requirement "
                        f"{requirement.id} is marked CORRECTED "
                        f"but has no corrected status."
                    )
                )

        # -----------------------------------
        # 5. Calculate final completion
        # -----------------------------------

        satisfied = 0

        for requirement in mandatory_requirements:

            mapping = mapping_by_requirement.get(
                requirement.id
            )

            if mapping.review_status == "CONFIRMED":

                if mapping.status == "SUPPORTED":
                    satisfied += 1

            elif mapping.review_status == "CORRECTED":

                if mapping.corrected_status == "SUPPORTED":
                    satisfied += 1

            elif mapping.review_status == "REJECTED":

                # Rejected mappings do not satisfy
                # the requirement.
                continue

        total_mandatory = len(
            mandatory_requirements
        )

        if total_mandatory == 0:

            completion_percentage = 100.0

        else:

            completion_percentage = round(
                (
                    satisfied
                    / total_mandatory
                ) * 100,
                2
            )

        # -----------------------------------
        # 6. Mark assessment as reviewed
        # -----------------------------------

        assessment.completion_percentage = (
            completion_percentage
        )

        assessment.status = "REVIEWED"

        db.commit()
        db.refresh(assessment)

        return {
            "message": "Assessment review completed successfully.",
            "assessment": {
                "id": assessment.id,
                "status": assessment.status,
                "guideline_version_id":
                    assessment.guideline_version_id,
                "application_version_id":
                    assessment.application_version_id,
                "completion_percentage":
                    assessment.completion_percentage
            },
            "mandatory_requirements":
                total_mandatory,
            "satisfied_requirements":
                satisfied
        }

    finally:
        db.close()