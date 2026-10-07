import os

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401  (registers the Link table)
from app.database import Base, get_db
from app.main import app

load_dotenv()

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

# Safety checks: these tests drop and truncate tables, so they must
# never run against the real database.
if not TEST_DATABASE_URL:
    raise RuntimeError("TEST_DATABASE_URL is not set in .env")
if TEST_DATABASE_URL == os.getenv("DATABASE_URL"):
    raise RuntimeError("TEST_DATABASE_URL must differ from DATABASE_URL")
if not make_url(TEST_DATABASE_URL).database.endswith("_test"):
    raise RuntimeError("Test database name must end with '_test'")


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_table(engine):
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE links RESTART IDENTITY"))
    yield


@pytest.fixture
def client(engine):
    TestingSession = sessionmaker(bind=engine, autoflush=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()