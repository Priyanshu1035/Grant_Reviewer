from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

from .application_routes import router as application_router
from .database import engine, Base
from .models import Grant
from .guideline_routes import router as guideline_router
from .grant_routes import router as grant_router
from .assessment_routes import router as assessment_router
from .document_routes import router as document_router
from fastapi.middleware.cors import CORSMiddleware


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Grant Application Completeness API"
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://grant-reviewer-omega.vercel.app",
        "https://grant-reviewer-orl1q8y20-priyanshu-03d1.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(grant_router)
app.include_router(guideline_router)
app.include_router(application_router)
app.include_router(assessment_router)
app.include_router(document_router)

@app.get("/")
def root():
    return {
        "message": "Grant Reviewer API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }