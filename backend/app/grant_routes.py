from fastapi import APIRouter
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Grant


router = APIRouter(
    prefix="/grants",
    tags=["Grants"]
)


@router.post("/")
def create_grant(name: str):
    db: Session = SessionLocal()

    try:
        grant = Grant(name=name)

        db.add(grant)
        db.commit()
        db.refresh(grant)

        return {
            "id": grant.id,
            "name": grant.name,
            "created_at": grant.created_at
        }

    finally:
        db.close()