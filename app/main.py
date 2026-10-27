from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.client import UrjaAuthError, UrjaNotFoundError, UrjaUpstreamError
from app.dependencies import get_urja_client
from app.repository import repository
from app.routers import health, meters, transformers, network, ui

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("urja_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm in-memory cache on startup so initial user queries are instant
    client = get_urja_client()
    try:
        await repository.warm_or_refresh(client)
        logger.info(
            f"Cache warmed: {repository.meter_count} meters, "
            f"{repository.transformer_count} transformers indexed."
        )
    except Exception as exc:
        # If upstream is temporarily unreachable at boot, log warning and let routes lazy-sync
        logger.warning(f"Startup sync deferred ({exc}). Will retry on first request.")
    yield
    await client.close()


app = FastAPI(
    title="Urja Meter Ops API",
    description=(
        "Programmatic REST API over the legacy Urja Meter Ops utility portal, "
        "providing meter search, interval consumption, transformer records, and grid hierarchy."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(UrjaNotFoundError)
async def not_found_handler(request: Request, exc: UrjaNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


@app.exception_handler(UrjaAuthError)
async def auth_error_handler(request: Request, exc: UrjaAuthError):
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": f"Upstream authentication failed: {exc}"},
    )


@app.exception_handler(UrjaUpstreamError)
async def upstream_error_handler(request: Request, exc: UrjaUpstreamError):
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": f"Upstream gateway error: {exc}"},
    )


app.include_router(ui.router)
app.include_router(health.router)
app.include_router(meters.router)
app.include_router(transformers.router)
app.include_router(network.router)
