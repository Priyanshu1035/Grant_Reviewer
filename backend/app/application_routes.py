from fastapi import APIRouter
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Application

from pathlib import Path
from hashlib import sha256

from fastapi import UploadFile, File, HTTPException

from .models import Application, ApplicationVersion
from .document_parser import extract_text


router = APIRouter(
    prefix="/applications",
    tags=["Applications"]
)


@router.post("/")
def create_application(
    grant_id: int,
    name: str
):
    db: Session = SessionLocal()

    try:
        application = Application(
            grant_id=grant_id,
            name=name
        )

        db.add(application)
        db.commit()
        db.refresh(application)

        return {
            "id": application.id,
            "grant_id": application.grant_id,
            "name": application.name,
            "created_at": application.created_at
        }

    finally:
        db.close()
        
        
@router.post("/upload")
async def upload_application(
    application_id: int,
    file: UploadFile = File(...)
):
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
        # Check application exists
        application = db.get(
            Application,
            application_id
        )

        if not application:
            raise HTTPException(
                status_code=404,
                detail="Application not found."
            )

        # Read file
        content = await file.read()

        # Calculate SHA-256
        file_hash = sha256(content).hexdigest()

        # Find latest version
        latest_version = (
            db.query(ApplicationVersion)
            .filter(
                ApplicationVersion.application_id
                == application.id
            )
            .order_by(
                ApplicationVersion.version.desc()
            )
            .first()
        )

        new_version = (
            latest_version.version + 1
            if latest_version
            else 1
        )

        # Save file
        upload_dir = Path("uploads/applications")
        upload_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        extension = Path(file.filename).suffix

        filename = (
            f"application_{application.id}"
            f"_v{new_version}"
            f"{extension}"
        )

        file_path = upload_dir / filename

        file_path.write_bytes(content)

        # Extract text
        try:
            extracted_text = extract_text(
                str(file_path)
            )
        except Exception as e:
            file_path.unlink(
                missing_ok=True
            )

            raise HTTPException(
                status_code=400,
                detail=f"Failed to extract document text: {str(e)}"
            )

        # Create version
        application_version = ApplicationVersion(
            application_id=application.id,
            version=new_version,
            file_path=str(file_path),
            file_hash=file_hash,
            extracted_text=extracted_text
        )

        db.add(application_version)
        db.commit()
        db.refresh(application_version)

        return {
            "message": "Application uploaded successfully",
            "application_id": application.id,
            "version": new_version,
            "file": filename
        }

    finally:
        db.close()