import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .db import Base, engine, get_session
from .models import Link
from .schemas import LinkCreate, LinkRead


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="URL Shortener", version="1.0.0", lifespan=lifespan)


def generate_code() -> str:
    return secrets.token_urlsafe(6)


def to_read(link: Link, request: Request) -> LinkRead:
    base = str(request.base_url).rstrip("/")
    return LinkRead(
        code=link.code,
        original_url=link.original_url,
        short_url=f"{base}/{link.code}",
        clicks=link.clicks,
        created_at=link.created_at,
    )


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "url-shortener", "docs": "/docs"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/api/links", response_model=LinkRead, status_code=status.HTTP_201_CREATED
)
async def create_link(
    payload: LinkCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> LinkRead:
    if payload.code and await session.scalar(
        select(Link.id).where(Link.code == payload.code)
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "Код уже занят")
    link = Link(code=payload.code or generate_code(), original_url=str(payload.url))
    session.add(link)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Код уже занят") from None
    await session.refresh(link)
    return to_read(link, request)


@app.get("/api/links", response_model=list[LinkRead])
async def list_links(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[LinkRead]:
    links = (
        await session.scalars(
            select(Link).order_by(Link.id.desc()).limit(limit).offset(offset)
        )
    ).all()
    return [to_read(link, request) for link in links]


@app.get("/api/links/{code}", response_model=LinkRead)
async def get_link(
    code: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> LinkRead:
    link = await session.scalar(select(Link).where(Link.code == code))
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ссылка не найдена")
    return to_read(link, request)


@app.delete("/api/links/{code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(
    code: str, session: AsyncSession = Depends(get_session)
) -> Response:
    link = await session.scalar(select(Link).where(Link.code == code))
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ссылка не найдена")
    await session.delete(link)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/{code}")
async def redirect(
    code: str, session: AsyncSession = Depends(get_session)
) -> RedirectResponse:
    link = await session.scalar(select(Link).where(Link.code == code))
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ссылка не найдена")
    link.clicks += 1
    await session.commit()
    return RedirectResponse(link.original_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
