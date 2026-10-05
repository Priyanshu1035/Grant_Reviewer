import os
import json
import shutil

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
    HTTPException
)

from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import (
    ApplicationVersion,
    SupportingDocument
)


router = APIRouter(
    prefix="/supporting-documents",
    tags=["Supporting Documents"]
)


UPLOAD_DIR = "uploads/supporting_documents"

os.makedirs(
    UPLOAD_DIR,
    exist_ok=True
)


@router.post("/upload")
async def upload_supporting_document(
    application_version_id: int = Form(...),
    document_type: str = Form(...),
    file: UploadFile = File(...)
):

    db: Session = SessionLocal()

    try:

        application_version = db.get(
            ApplicationVersion,
            application_version_id
        )

        if not application_version:
            raise HTTPException(
                status_code=404,
                detail="Application version not found."
            )

        allowed_types = {
            "application/pdf",
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        }

        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Only PDF and DOCX files "
                    "are supported."
                )
            )

        filename = file.filename or "document"

        file_path = os.path.join(
            UPLOAD_DIR,
            (
                f"application_"
                f"{application_version_id}_"
                f"{document_type}_"
                f"{filename}"
            )
        )

        with open(
            file_path,
            "wb"
        ) as buffer:

            shutil.copyfileobj(
                file.file,
                buffer
            )

        document = SupportingDocument(
            application_version_id=
                application_version_id,
            document_type=document_type,
            filename=filename,
            file_path=file_path,
            status="UPLOADED"
        )

        db.add(document)
        db.commit()
        db.refresh(document)

        return {
            "message":
                "Supporting document uploaded successfully.",
            "document": {
                "id": document.id,
                "application_version_id":
                    document.application_version_id,
                "document_type":
                    document.document_type,
                "filename":
                    document.filename,
                "status":
                    document.status,
                "created_at":
                    document.created_at
            }
        }

    finally:
        db.close()


@router.get(
    "/application-version/{application_version_id}"
)
def get_supporting_documents(
    application_version_id: int
):

    db: Session = SessionLocal()

    try:

        application_version = db.get(
            ApplicationVersion,
            application_version_id
        )

        if not application_version:
            raise HTTPException(
                status_code=404,
                detail="Application version not found."
            )

        documents = (
            db.query(SupportingDocument)
            .filter(
                SupportingDocument.application_version_id
                == application_version_id
            )
            .all()
        )

        return {
            "application_version_id":
                application_version_id,

            "count": len(documents),

            "documents": [
                {
                    "id": document.id,
                    "document_type":
                        document.document_type,
                    "filename":
                        document.filename,
                    "status":
                        document.status,
                    "created_at":
                        document.created_at
                }
                for document in documents
            ]
        }

    finally:
        db.close()