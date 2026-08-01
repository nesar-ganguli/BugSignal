from pydantic import BaseModel, Field, field_validator


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    slug: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Project name cannot be blank.")
        return normalized


class ProjectRead(BaseModel):
    id: int
    organization_id: int
    name: str
    slug: str
    role: str


class ProjectListResponse(BaseModel):
    items: list[ProjectRead]
