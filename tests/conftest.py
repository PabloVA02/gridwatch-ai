import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

test_database = Path(tempfile.gettempdir()) / f"gridwatch-{uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{test_database}"
os.environ["MINIMUM_ANALYSIS_POINTS"] = "12"

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
