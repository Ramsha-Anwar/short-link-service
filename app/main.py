from fastapi import FastAPI
from app.schemas import LinkCreate


app = FastAPI()


@app.get("/")
def root():
    return {"message": "Short Link Service API"}

@app.post("/links/")
def create_link(link: LinkCreate):
    return {"url" : link.url}