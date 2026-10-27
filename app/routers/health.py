from fastapi import APIRouter, Depends
from app.client import UrjaClient
from app.config import settings
from app.models import HealthResponse
from app.repository import repository

router = APIRouter(prefix="/api/v1", tags=["Health"])


def get_client() -> UrjaClient:
    from app.dependencies import get_urja_client
    return get_urja_client()


@router.get("/health", response_model=HealthResponse, summary="Service & upstream health status")
async def get_health(client: UrjaClient = Depends(get_client)):
    """Reports health status of the API service, cache warmth, and upstream session state."""
    is_authed = client.is_authenticated
    status = "healthy" if is_authed and repository.is_warmed else "degraded"
    
    return HealthResponse(
        status=status,
        upstream_portal=settings.portal_url,
        upstream_authenticated=is_authed,
        cached_meters=repository.meter_count,
        cached_transformers=repository.transformer_count,
        cache_last_updated=repository.last_synced_at,
    )
