from pydantic import BaseModel,HttpUrl


class LinkCreate(BaseModel):
    url: HttpUrl