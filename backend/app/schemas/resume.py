from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ResumeCreate(BaseModel):
    raw_text: str


class ResumeOut(BaseModel):
    id: int
    user_id: int
    raw_text: str
    extracted_data: "ResumeExtraction | None"
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ExperienceEntry(BaseModel):
    company: str
    title: str
    start_date: str
    end_date: str | None
    bullet_points: list[str]


class ResumeExtraction(BaseModel):
    skills: list[str]
    experience: list[ExperienceEntry]
    education: list[str]


ResumeOut.model_rebuild()
