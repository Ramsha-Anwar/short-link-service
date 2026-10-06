import secrets
import string
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from app.schemas import LinkCreate


app = FastAPI()
links = {}


@app.get("/")
def root():
    return {"message": "Short Link Service API"}


def generate_code(length: int = 6):
    characters = string.ascii_letters + string.digits
    return "".join(secrets.choice(characters) for _ in range(length))


@app.post("/links")
def create_link(link: LinkCreate):
    url = str(link.url)

    for code, link_data in links.items():
        if link_data["url"] == url:
            return {
                "code": code,
                "url": url
            }

    while True:
        code = generate_code()
        if code not in links:
            break

    links[code] = {
        "url": url,
        "clicks": 0
    }

    return {
        "code": code,
        "url": url
    }


@app.get("/links/{code}")
def get_link(code: str):
    if code not in links:
        raise HTTPException(
            status_code=404,
            detail="Short link not found"
        )

    links[code]["clicks"] += 1

    return RedirectResponse(
        url=links[code]["url"],
        status_code=302
    )

@app.get("/links/{code}/stats")
def get_link_stats(code: str):
    if code not in links:
        raise HTTPException(
            status_code=404,
            detail="Short link not found"
        )

    return {
        "code": code,
        "url": links[code]["url"],
        "clicks": links[code]["clicks"]
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