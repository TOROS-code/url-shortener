import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base, get_session
from app.main import app


@pytest.fixture()
def client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session():
        async with session_factory() as session:
            yield session

    async def create_tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(create_tables())
    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


def test_create_and_redirect_counts_clicks(client):
    response = client.post("/api/links", json={"url": "https://example.com"})
    assert response.status_code == 201
    data = response.json()
    assert data["clicks"] == 0
    assert data["short_url"].endswith(data["code"])

    redirect = client.get(f"/{data['code']}", follow_redirects=False)
    assert redirect.status_code == 307
    assert redirect.headers["location"] == "https://example.com/"

    stats = client.get(f"/api/links/{data['code']}")
    assert stats.json()["clicks"] == 1


def test_custom_code_conflict(client):
    first = client.post("/api/links", json={"url": "https://a.com", "code": "promo"})
    second = client.post("/api/links", json={"url": "https://b.com", "code": "promo"})
    assert first.status_code == 201
    assert second.status_code == 409


def test_invalid_url_rejected(client):
    response = client.post("/api/links", json={"url": "не ссылка"})
    assert response.status_code == 422


def test_delete_link(client):
    code = client.post("/api/links", json={"url": "https://example.org"}).json()["code"]

    assert client.delete(f"/api/links/{code}").status_code == 204
    assert client.get(f"/api/links/{code}").status_code == 404


def test_unknown_code_returns_404(client):
    assert client.get("/api/links/nope").status_code == 404
    assert client.get("/nope", follow_redirects=False).status_code == 404


def test_list_links(client):
    client.post("/api/links", json={"url": "https://one.com"})
    client.post("/api/links", json={"url": "https://two.com"})

    response = client.get("/api/links")
    assert response.status_code == 200
    assert len(response.json()) == 2
