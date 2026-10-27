import os
import pytest
from app.client import UrjaClient
from app.config import settings
from app.normalizer import (
    normalize_meter_detail,
    normalize_consumption_reading,
    normalize_transformer,
)


@pytest.mark.asyncio
async def test_live_upstream_portal_connection():
    """Live smoke test verifying authentication, bulk export, and energy readings against Urja portal."""
    client = UrjaClient(
        base_url=settings.portal_url,
        username=settings.portal_username,
        password=settings.portal_password,
    )
    try:
        # 1. Test Login
        token = await client.login()
        assert token is not None
        assert len(token) > 20
        assert client.is_authenticated

        # 2. Test Transformers retrieval
        dts = await client.get_all_dts()
        assert len(dts) == 40
        sample_dt = normalize_transformer(dts[0])
        assert sample_dt.code.startswith("DT-")

        # 3. Test Bulk Export via HMAC
        export_meters = await client.get_bulk_export()
        assert len(export_meters) == 403
        sample_m = normalize_meter_detail(export_meters[0])
        assert sample_m.meter_id.startswith("J")
        assert sample_m.hierarchy is not None
        assert sample_m.geo is not None

        # 4. Test Energy Readings
        readings = await client.get_meter_energy("J100000", from_date="2026-06-25", to_date="2026-06-26")
        assert len(readings) == 96  # 48 intervals/day * 2 days
        norm_reading = normalize_consumption_reading(readings[0])
        assert norm_reading.kwh > 0
        assert norm_reading.voltage_r > 0
        assert norm_reading.timestamp.startswith("2026-06-25")

    finally:
        await client.close()
