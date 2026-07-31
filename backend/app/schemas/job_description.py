from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobDescriptionCreate(BaseModel):
    raw_text: str
    company_id: int
    role_title: str


class JobDescriptionOut(BaseModel):
    id: int
    user_id: int
    company_id: int
    role_title: str
    raw_text: str
    extracted_data: "JDExtraction | None"
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class JDExtraction(BaseModel):
    required_skills: list[str]
    responsibilities: list[str]
    seniority_level: str | None


JobDescriptionOut.model_rebuild()
