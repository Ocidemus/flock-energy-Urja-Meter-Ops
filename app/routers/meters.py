from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.client import UrjaClient, UrjaNotFoundError, UrjaUpstreamError
from app.dependencies import get_urja_client
from app.models import (
    MeterDetail,
    MeterListResponse,
    ConsumptionResponse,
    DateRange,
)
from app.normalizer import normalize_consumption_reading
from app.repository import repository

router = APIRouter(prefix="/api/v1/meters", tags=["Meters"])


@router.get("", response_model=MeterListResponse, summary="List and search smart meters")
async def list_meters(
    q: Optional[str] = Query(None, description="Search term matching meter ID or serial number"),
    make: Optional[str] = Query(None, description="Filter by hardware manufacturer (e.g. Genus, HPL, L&T, Secure, Allied)"),
    phase: Optional[str] = Query(None, description="Filter by phase configuration ('single' or 'three')"),
    status: Optional[str] = Query(None, description="Filter by operational status ('Installed', 'Faulty', 'Decommissioned')"),
    dt_code: Optional[str] = Query(None, description="Filter by distribution transformer code (e.g. DT-001)"),
    install_type: Optional[str] = Query(None, description="Filter by installation type ('Whole Current', 'CT Operated')"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    client: UrjaClient = Depends(get_urja_client),
):
    """Returns a paginated list of meters supporting cross-attribute filtering and text search."""
    if not repository.is_warmed:
        await repository.warm_or_refresh(client)

    summaries, total, total_pages = repository.list_meters(
        q=q,
        make=make,
        phase=phase,
        status=status,
        dt_code=dt_code,
        install_type=install_type,
        page=page,
        page_size=page_size,
    )

    return MeterListResponse(
        data=summaries,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{meter_id}", response_model=MeterDetail, summary="Get meter profile and details")
async def get_meter(
    meter_id: str,
    client: UrjaClient = Depends(get_urja_client),
):
    """Retrieves full profile for a meter including nameplate specs, coordinates, and network hierarchy."""
    if not repository.is_warmed:
        await repository.warm_or_refresh(client)

    meter = repository.get_meter(meter_id)
    if not meter:
        # Check if meter exists upstream if cache might be out of date
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meter '{meter_id}' not found in registry",
        )
    return meter


@router.get("/{meter_id}/consumption", response_model=ConsumptionResponse, summary="Get interval energy consumption")
async def get_consumption(
    meter_id: str,
    from_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Start date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="End date (YYYY-MM-DD)"),
    client: UrjaClient = Depends(get_urja_client),
):
    """Fetches normalized 30-minute interval readings (kWh, kVAh, Voltage) for a given meter."""
    try:
        raw_readings = await client.get_meter_energy(
            meter_id=meter_id,
            from_date=from_date,
            to_date=to_date,
        )
    except UrjaNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meter '{meter_id}' not found upstream",
        )
    except UrjaUpstreamError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream portal failure: {exc}",
        )

    readings = [normalize_consumption_reading(r) for r in raw_readings]

    return ConsumptionResponse(
        meter_id=meter_id,
        total_readings=len(readings),
        filter=DateRange(start=from_date, end=to_date),
        data=readings,
    )


@router.post("/sync", summary="Trigger manual cache synchronization")
async def sync_cache(client: UrjaClient = Depends(get_urja_client)):
    """Forces an immediate synchronization with the upstream portal."""
    await repository.warm_or_refresh(client, force=True)
    return {
        "status": "synchronized",
        "meters_count": repository.meter_count,
        "transformers_count": repository.transformer_count,
        "synced_at": repository.last_synced_at,
    }
