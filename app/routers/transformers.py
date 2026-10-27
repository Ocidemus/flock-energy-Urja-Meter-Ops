from fastapi import APIRouter, Depends, HTTPException, status
from app.client import UrjaClient
from app.dependencies import get_urja_client
from app.models import TransformerDetail, TransformerListResponse
from app.repository import repository

router = APIRouter(prefix="/api/v1/transformers", tags=["Transformers"])


@router.get("", response_model=TransformerListResponse, summary="List distribution transformers")
async def list_transformers(client: UrjaClient = Depends(get_urja_client)):
    """Returns all 40 distribution transformers in the network with their feeding lines and capacities."""
    if not repository.is_warmed:
        await repository.warm_or_refresh(client)

    items = repository.list_transformers()
    return TransformerListResponse(data=items, total=len(items))


@router.get("/{code}", response_model=TransformerDetail, summary="Get transformer details and connected meters")
async def get_transformer(code: str, client: UrjaClient = Depends(get_urja_client)):
    """Retrieves detailed information for a transformer including all meters connected to it."""
    if not repository.is_warmed:
        await repository.warm_or_refresh(client)

    dt = repository.get_transformer(code)
    if not dt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Distribution transformer '{code}' not found",
        )
    return dt
