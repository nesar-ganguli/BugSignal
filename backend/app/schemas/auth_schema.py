from pydantic import BaseModel


class CurrentUserResponse(BaseModel):
    subject: str
    email: str | None
    display_name: str | None
    organization_external_id: str
    roles: list[str]
