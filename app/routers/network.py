from typing import List
from fastapi import APIRouter, Depends
from app.client import UrjaClient
from app.dependencies import get_urja_client
from app.models import NetworkTreeNode, MeterDetail
from app.repository import repository

router = APIRouter(prefix="/api/v1", tags=["Network & Bulk Data"])


@router.get(
    "/network/hierarchy",
    response_model=List[NetworkTreeNode],
    summary="Get full 7-level distribution network hierarchy",
)
async def get_network_hierarchy(client: UrjaClient = Depends(get_urja_client)):
    """Reconstructs and returns the full utility grid tree: Zone -> Circle -> Division -> Subdivision -> Substation -> Feeder -> DT."""
    if not repository.is_warmed:
        await repository.warm_or_refresh(client)

    return repository.reconstruct_network_hierarchy()


@router.get(
    "/export/meters",
    response_model=List[MeterDetail],
    summary="Direct bulk export of all meters with full attributes",
)
async def export_all_meters(client: UrjaClient = Depends(get_urja_client)):
    """Retrieves all 403 meters in a single operation via authenticated HMAC bulk export."""
    if not repository.is_warmed:
        await repository.warm_or_refresh(client)

    return list(repository._meters.values())
