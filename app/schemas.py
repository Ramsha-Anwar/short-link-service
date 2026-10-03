from pydantic import BaseModel


class LinkCreate(BaseModel):
    url: str