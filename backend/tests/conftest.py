"""Shared test fixtures for the backend test suite."""
from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Force SQLite for tests
os.environ["APP_DATABASE_URL"] = "sqlite:///./test_db.sqlite"
os.environ["APP_STORAGE_DIR"] = "./test_storage"
os.environ["APP_DATA_DIR"] = "./test_data"

from app.core.config import settings  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, User, ProductCategory, Task, Candidate  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def setup_dirs():
    """Ensure test directories exist."""
    import pathlib
    for d in ("./test_storage/uploads", "./test_storage/processed", "./test_storage/exports", "./test_data"):
        pathlib.Path(d).mkdir(parents=True, exist_ok=True)
    yield
    # Cleanup handled by CI or manual


@pytest.fixture()
def db_engine():
    engine = create_engine("sqlite:///./test_db.sqlite", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    SessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def client(db_session):
    """FastAPI TestClient with overridden DB dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def test_user(db_session) -> User:
    """Create a test user and return it."""
    user = User(
        username="testuser",
        password_hash=hash_password("testpass123"),
        role="admin",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def auth_token(test_user) -> str:
    """Create a valid JWT token for the test user."""
    return create_access_token({"id": test_user.id, "username": test_user.username})


@pytest.fixture()
def auth_headers(auth_token) -> dict[str, str]:
    """Authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture()
def seed_categories(db_session) -> list[ProductCategory]:
    """Seed basic product categories."""
    washbasin = ProductCategory(name="洗手盆", prompt_template="洗手盆场景", scene_keywords=["卫浴"], sort_order=1)
    bathtub = ProductCategory(name="浴缸", prompt_template="浴缸场景", scene_keywords=["浴室"], sort_order=2)
    db_session.add_all([washbasin, bathtub])
    db_session.commit()
    db_session.refresh(washbasin)
    db_session.refresh(bathtub)
    return [washbasin, bathtub]


@pytest.fixture()
def task_at_step(db_session, test_user, seed_categories):
    """Factory fixture: create a task at a specific step with optional candidates."""
    def _create(step: str = "input", entry_type: str = "white_bg_upload",
                with_candidates: int = 0, with_selected: bool = False,
                category_id: int | None = None) -> Task:
        task = Task(
            entry_type=entry_type,
            current_step=step,
            status="active",
            task_config_json={},
            product_category_id=category_id or (seed_categories[0].id if step != "input" else None),
        )
        db_session.add(task)
        db_session.flush()

        for i in range(with_candidates):
            c = Candidate(
                task_id=task.id,
                source_type="uploaded",
                file_path=f"uploads/test_{i}.png",
                is_selected=(i == 0 and with_selected),
                metadata_json={},
            )
            db_session.add(c)

        db_session.commit()
        db_session.refresh(task)
        return task
    return _create
