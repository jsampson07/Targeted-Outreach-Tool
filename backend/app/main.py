from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.routers import auth as auth_router
from app.routers import company_resolution as company_resolution_router
from app.routers import contact_discovery as contact_discovery_router
from app.routers import generated_emails as generated_emails_router
from app.routers import job_description as job_description_router
from app.routers import resume as resume_router

settings = get_settings()

app = FastAPI()
register_exception_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router.router, prefix="/auth")
app.include_router(resume_router.router, prefix="/resumes")
app.include_router(job_description_router.router, prefix="/job-descriptions")
app.include_router(contact_discovery_router.router, prefix="/contacts")
app.include_router(company_resolution_router.router, prefix="/companies")
app.include_router(generated_emails_router.router, prefix="/generated-emails")

