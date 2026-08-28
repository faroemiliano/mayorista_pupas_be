import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.core.security import get_usuario_opcional
from app.models.usuario import Usuario


@pytest.fixture
def engine():
    test_engine = create_engine(
        "sqlite://",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    Base.metadata.create_all(test_engine)

    yield test_engine

    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


@pytest.fixture
def db(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(engine):
    def override_get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = (
        override_get_db
    )
    app.dependency_overrides[get_usuario_opcional] = lambda: Usuario(
        id=1,
        google_sub="test-admin",
        email="admin@test.local",
        nombre="Admin Test",
        rol="admin",
        activo=True,
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def public_client(engine):
    def override_get_db():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_usuario_opcional] = lambda: None
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
