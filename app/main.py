import secrets
import string

from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Link
from app.schemas import LinkCreate


app = FastAPI()


@app.get("/")
def root():
    return {"message": "Short Link Service API"}


def generate_code(length: int = 6):
    characters = string.ascii_letters + string.digits
    return "".join(secrets.choice(characters) for _ in range(length))


@app.post("/links")
def create_link(link: LinkCreate, db: Session = Depends(get_db)):
    url = str(link.url)

    existing = db.scalar(select(Link).where(Link.original_url == url))
    if existing:
        return {"code": existing.code, "url": existing.original_url}

    for _ in range(5):
        code = generate_code()
        db.add(Link(code=code, original_url=url))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # Either this code is taken, or the same URL was inserted
            # by a concurrent request. Check the second case first.
            existing = db.scalar(select(Link).where(Link.original_url == url))
            if existing:
                return {"code": existing.code, "url": existing.original_url}
            continue
        return {"code": code, "url": url}

    raise HTTPException(status_code=500, detail="Could not generate a unique code")


@app.get("/links/{code}")
def get_link(code: str, db: Session = Depends(get_db)):
    url = db.scalar(
        update(Link)
        .where(Link.code == code)
        .values(clicks=Link.clicks + 1)
        .returning(Link.original_url)
    )
    db.commit()

    if url is None:
        raise HTTPException(status_code=404, detail="Short link not found")

    return RedirectResponse(url=url, status_code=302)


@app.get("/links/{code}/stats")
def get_link_stats(code: str, db: Session = Depends(get_db)):
    link = db.scalar(select(Link).where(Link.code == code))

    if link is None:
        raise HTTPException(status_code=404, detail="Short link not found")

    return {
        "code": link.code,
        "url": link.original_url,
        "clicks": link.clicks,
    }


@app.get("/links")
def list_links(limit: int = 10):
    return {"limit": limit}


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

    return JSONResponse(status_code=400, content={"detail": errors})