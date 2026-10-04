from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError 
from fastapi.responses import JSONResponse

from app.schemas import LinkCreate


app = FastAPI()


@app.get("/")
def root():
    return {"message": "Short Link Service API"}


@app.post("/links")
def create_link(link: LinkCreate):
    return {
        "url": link.url
    }


@app.get("/links/{code}")
def get_link(code: str):
    return {
        "code": code
    }


@app.get("/links")
def list_links(limit: int = 10):
    return {
        "limit": limit
    }

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    errors = []

    for err in exc.errors():
        loc = err["loc"]

        errors.append({
            "field": str(loc[-1]),
            "location": str(loc[0]),
            "message": err["msg"],
        })

    return JSONResponse(
        status_code=400,
        content={"detail": errors}
    )