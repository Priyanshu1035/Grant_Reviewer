from pathlib import Path
from hashlib import sha256
from .document_parser import extract_text
from fastapi import APIRouter, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from .ai_service import extract_requirements, map_requirements_to_application

from .database import SessionLocal
from .models import Grant, Guideline, GuidelineVersion, Requirement, ApplicationVersion, Mapping, Evidence, Assessment
from .schemas import MappingReview


router = APIRouter(
    prefix="/guidelines",
    tags=["Guidelines"]
)


UPLOAD_DIR = Path("uploads/guidelines")
UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)


@router.post("/upload")
async def upload_guideline(
    grant_id: int,
    name: str,
    file: UploadFile = File(...)
):
    # Check file type
    allowed_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and DOCX files are supported."
        )

    db: Session = SessionLocal()

    try:
        # Check grant exists
        grant = db.get(Grant, grant_id)

        if not grant:
            raise HTTPException(
                status_code=404,
                detail="Grant not found."
            )

        # Find or create guideline
        guideline = (
            db.query(Guideline)
            .filter(
                Guideline.grant_id == grant_id,
                Guideline.name == name
            )
            .first()
        )

        if not guideline:
            guideline = Guideline(
                grant_id=grant_id,
                name=name
            )

            db.add(guideline)
            db.commit()
            db.refresh(guideline)

        # Read file
        content = await file.read()

        # Calculate SHA-256 hash
        file_hash = sha256(content).hexdigest()

        # Determine version
        latest_version = (
            db.query(GuidelineVersion)
            .filter(
                GuidelineVersion.guideline_id == guideline.id
            )
            .order_by(
                GuidelineVersion.version.desc()
            )
            .first()
        )

        new_version = (
            latest_version.version + 1
            if latest_version
            else 1
        )

        # Save file
        extension = Path(file.filename).suffix

        filename = (
            f"guideline_{guideline.id}"
            f"_v{new_version}"
            f"{extension}"
        )

        file_path = UPLOAD_DIR / filename

        file_path.write_bytes(content)
        
        try:
            extracted_text = extract_text(str(file_path))
        except Exception as e:
            file_path.unlink(missing_ok=True)
            
            raise HTTPException(
                status_code = 400,
                detail = f"Failed to extract document text: {str(e)}"
            )

        # Create version record
        guideline_version = GuidelineVersion(
            guideline_id=guideline.id,
            version=new_version,
            file_path=str(file_path),
            file_hash=file_hash,
            extracted_text=extracted_text
        )

        db.add(guideline_version)
        db.commit()
        db.refresh(guideline_version)

        return {
            "message": "Guideline uploaded successfully",
            "guideline_id": guideline.id,
            "version": new_version,
            "file": filename
        }

    finally:
        db.close()
        
        
@router.post("/{guideline_version_id}/extract-requirements")
def extract_guideline_requirements(guideline_version_id: int):

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

        if not guideline_version.extracted_text:
            raise HTTPException(
                status_code=400,
                detail="Guideline has no extracted text."
            )

        # Ask Gemini to extract requirements
        requirements = extract_requirements(
            guideline_version.extracted_text
        )
        
        # Remove old extraction results for this guideline version
        db.query(Requirement).filter(
            Requirement.guideline_version_id == guideline_version.id
        ).delete(
            synchronize_session=False
        )

        # Save requirements to database
        saved_requirements = []

        for requirement in requirements:

            db_requirement = Requirement(
                guideline_version_id=guideline_version.id,
                requirement=requirement.requirement,
                mandatory=requirement.mandatory,
                category=requirement.category,
                source_text=requirement.source_text
            )

            db.add(db_requirement)
            saved_requirements.append(db_requirement)

        db.commit()

        for requirement in saved_requirements:
            db.refresh(requirement)

        return {
            "message": "Requirements extracted successfully",
            "guideline_version_id": guideline_version.id,
            "count": len(saved_requirements),
            "requirements": [
                {
                    "id": requirement.id,
                    "requirement": requirement.requirement,
                    "mandatory": requirement.mandatory,
                    "category": requirement.category,
                    "source_text": requirement.source_text
                }
                for requirement in saved_requirements
            ]
        }

    finally:
        db.close()
        
        

@router.post("/{guideline_version_id}/map-application/{application_version_id}")
def map_application_to_guideline(
    guideline_version_id: int,
    application_version_id: int
):
    db: Session = SessionLocal()

    try:
        # 1. Get guideline version
        guideline_version = db.get(
            GuidelineVersion,
            guideline_version_id
        )

        if not guideline_version:
            raise HTTPException(
                status_code=404,
                detail="Guideline version not found."
            )

        # 2. Get application version
        application_version = db.get(
            ApplicationVersion,
            application_version_id
        )

        if not application_version:
            raise HTTPException(
                status_code=404,
                detail="Application version not found."
            )

        # 3. Get requirements
        requirements = (
            db.query(Requirement)
            .filter(
                Requirement.guideline_version_id
                == guideline_version_id
            )
            .all()
        )

        if not requirements:
            raise HTTPException(
                status_code=400,
                detail="No requirements found for this guideline version."
            )

        # 4. Make sure application has extracted text
        if not application_version.extracted_text:
            raise HTTPException(
                status_code=400,
                detail="Application has no extracted text."
            )

        # 5. Ask AI to map requirements
        mappings = map_requirements_to_application(
            requirements,
            application_version.extracted_text
        )

        saved_mappings = []

        # 6. Save mappings + evidence
        for result in mappings:

            mapping = Mapping(
                requirement_id=result.requirement_id,
                application_version_id=application_version_id,
                status=result.status,
                confidence=result.confidence,
                reason=result.reason
            )

            db.add(mapping)
            db.flush()

            for evidence in result.evidence:

                db_evidence = Evidence(
                    mapping_id=mapping.id,
                    source_text=evidence.source_text,
                    page_number=evidence.page_number
                )

                db.add(db_evidence)

            saved_mappings.append(mapping)

        db.commit()

        return {
            "message": "Application mapped successfully",
            "guideline_version_id": guideline_version_id,
            "application_version_id": application_version_id,
            "count": len(saved_mappings),
            "mappings": [
                {
                    "id": mapping.id,
                    "requirement_id": mapping.requirement_id,
                    "status": mapping.status,
                    "confidence": mapping.confidence,
                    "reason": mapping.reason
                }
                for mapping in saved_mappings
            ]
        }

    finally:
        db.close()
        
        
        
@router.patch("/mappings/{mapping_id}/review")
def review_mapping(
    mapping_id: int,
    review: MappingReview
):
    db: Session = SessionLocal()

    try:
        mapping = db.get(Mapping, mapping_id)

        if not mapping:
            raise HTTPException(
                status_code=404,
                detail="Mapping not found."
            )

        # CORRECTED requires a corrected status.
        if (
            review.review_status == "CORRECTED"
            and review.corrected_status is None
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "corrected_status is required "
                    "when review_status is CORRECTED."
                )
            )

        # CONFIRMED should not have a corrected status.
        if review.review_status == "CONFIRMED":
            mapping.corrected_status = None
            mapping.corrected_reason = None

        # REJECTED should not have a corrected status.
        elif review.review_status == "REJECTED":
            mapping.corrected_status = None
            mapping.corrected_reason = None

        # CORRECTED stores the human's new classification.
        elif review.review_status == "CORRECTED":
            mapping.corrected_status = review.corrected_status
            mapping.corrected_reason = review.corrected_reason

        mapping.review_status = review.review_status
        mapping.review_reason = review.review_reason

        db.commit()
        db.refresh(mapping)

        return {
            "message": "Mapping review updated successfully.",
            "mapping": {
                "id": mapping.id,
                "requirement_id": mapping.requirement_id,

                "ai_status": mapping.status,
                "confidence": mapping.confidence,
                "reason": mapping.reason,

                "review_status": mapping.review_status,
                "review_reason": mapping.review_reason,

                "corrected_status":
                    mapping.corrected_status,

                "corrected_reason":
                    mapping.corrected_reason
            }
        }

    finally:
        db.close()
        
        
@router.get(
    "/{guideline_version_id}/applications/{application_version_id}/completion"
)
def calculate_completion(
    guideline_version_id: int,
    application_version_id: int
):
    db: Session = SessionLocal()

    try:
        # Get all requirements for this guideline version
        requirements = (
            db.query(Requirement)
            .filter(
                Requirement.guideline_version_id
                == guideline_version_id
            )
            .all()
        )

        if not requirements:
            raise HTTPException(
                status_code=404,
                detail="No requirements found."
            )

        # Get mappings for this application version
        mappings = (
            db.query(Mapping)
            .filter(
                Mapping.application_version_id
                == application_version_id
            )
            .all()
        )

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

        details = []

        for requirement in mandatory_requirements:

            mapping = mapping_by_requirement.get(
                requirement.id
            )

            if not mapping:
                status = "MISSING"
                is_complete = False

            else:
                # Human review takes precedence
                if mapping.review_status == "CONFIRMED":
                    status = mapping.status
                    is_complete = (
                        mapping.status == "SUPPORTED"
                    )

                elif mapping.review_status == "CORRECTED":
                    status = mapping.corrected_status
                    is_complete = (
                        mapping.corrected_status == "SUPPORTED"
                    )

                elif mapping.review_status == "REJECTED":
                    status = "REJECTED"
                    is_complete = False

                else:
                    status = mapping.status
                    is_complete = (
                        mapping.status == "SUPPORTED"
                    )

            if is_complete:
                satisfied += 1

            details.append({
                "requirement_id": requirement.id,
                "requirement": requirement.requirement,
                "status": status,
                "complete": is_complete
            })

        total_mandatory = len(mandatory_requirements)

        if total_mandatory == 0:
            completion_percentage = 100.0
        else:
            completion_percentage = round(
                (satisfied / total_mandatory) * 100,
                2
            )

        return {
            "guideline_version_id": guideline_version_id,
            "application_version_id": application_version_id,
            "mandatory_requirements": total_mandatory,
            "satisfied_requirements": satisfied,
            "completion_percentage": completion_percentage,
            "details": details
        }

    finally:
        db.close()