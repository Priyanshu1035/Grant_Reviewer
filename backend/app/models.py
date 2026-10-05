from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Grant(Base):
    __tablename__ = "grants"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )


class Guideline(Base):
    __tablename__ = "guidelines"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    grant_id: Mapped[int] = mapped_column(
        ForeignKey("grants.id"),
        nullable=False
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )


class GuidelineVersion(Base):
    __tablename__ = "guideline_versions"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    guideline_id: Mapped[int] = mapped_column(
        ForeignKey("guidelines.id"),
        nullable=False
    )

    version: Mapped[int] = mapped_column(
        nullable=False
    )

    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )

    file_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )
    
    extracted_text: Mapped[str | None] = mapped_column(
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    grant_id: Mapped[int] = mapped_column(
        ForeignKey("grants.id"),
        nullable=False
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )


class ApplicationVersion(Base):
    __tablename__ = "application_versions"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id"),
        nullable=False
    )

    version: Mapped[int] = mapped_column(
        nullable=False
    )

    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )

    file_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )
    
    extracted_text: Mapped[str | None] = mapped_column(
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
    
class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(primary_key=True)

    guideline_version_id: Mapped[int] = mapped_column(
        ForeignKey("guideline_versions.id"),
        nullable=False
    )

    requirement: Mapped[str] = mapped_column(nullable=False)

    mandatory: Mapped[bool] = mapped_column(nullable=False)

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    source_text: Mapped[str] = mapped_column(nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
    
    
class Mapping(Base):
    __tablename__ = "mappings"

    id: Mapped[int] = mapped_column(primary_key=True)

    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("requirements.id"),
        nullable=False
    )

    application_version_id: Mapped[int] = mapped_column(
        ForeignKey("application_versions.id"),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    confidence: Mapped[float | None] = mapped_column(
        nullable=True
    )

    reason: Mapped[str | None] = mapped_column(
        nullable=True
    )
    
    review_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    review_reason: Mapped[str | None] = mapped_column(
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
    
    corrected_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    corrected_reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)

    mapping_id: Mapped[int] = mapped_column(
        ForeignKey("mappings.id"),
        nullable=False
    )

    source_text: Mapped[str] = mapped_column(
        nullable=False
    )

    page_number: Mapped[int | None] = mapped_column(
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
    
    
class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True)

    guideline_version_id: Mapped[int] = mapped_column(
        ForeignKey("guideline_versions.id"),
        nullable=False
    )

    application_version_id: Mapped[int] = mapped_column(
        ForeignKey("application_versions.id"),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="DRAFT"
    )

    completion_percentage: Mapped[float] = mapped_column(
        default=0.0
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    

class SupportingDocument(Base):
    __tablename__ = "supporting_documents"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    application_version_id: Mapped[int] = mapped_column(
        ForeignKey("application_versions.id"),
        nullable=False
    )

    document_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="UPLOADED"
    )

    metadata_json: Mapped[str | None] = mapped_column(
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
    
    
class ClarificationQuestion(Base):
    __tablename__ = "clarification_questions"

    id: Mapped[int] = mapped_column(primary_key=True)

    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessments.id"),
        nullable=False
    )

    requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("requirements.id"),
        nullable=True
    )

    question: Mapped[str] = mapped_column(nullable=False)

    reason: Mapped[str] = mapped_column(nullable=False)

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="OPEN"
    )

    answer: Mapped[str | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
    
    
class UnsupportedClaim(Base):
    __tablename__ = "unsupported_claims"

    id: Mapped[int] = mapped_column(primary_key=True)

    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessments.id"),
        nullable=False
    )

    claim_text: Mapped[str] = mapped_column(nullable=False)

    reason: Mapped[str] = mapped_column(nullable=False)

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="OPEN"
    )

    review_reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )