import pytest
from app.normalizer import (
    parse_legacy_timestamp,
    normalize_meter_summary,
    normalize_meter_detail,
    normalize_consumption_reading,
    normalize_transformer,
)


def test_parse_legacy_timestamp():
    raw_ts = "25/06/2026 14:30"
    iso_ts = parse_legacy_timestamp(raw_ts)
    assert iso_ts == "2026-06-25T14:30:00Z"


def test_parse_legacy_timestamp_invalid_fallback():
    raw_ts = "not-a-timestamp"
    assert parse_legacy_timestamp(raw_ts) == "not-a-timestamp"


def test_normalize_meter_summary():
    raw = {
        "meterId": "J100000",
        "serialNo": "SE33962",
        "make": "HPL",
        "phaseType": "single",
        "installStatus": "Decommissioned",
        "dtCode": "DT-001",
    }
    summary = normalize_meter_summary(raw)
    assert summary.meter_id == "J100000"
    assert summary.serial_number == "SE33962"
    assert summary.make == "HPL"
    assert summary.phase_type == "single"
    assert summary.install_status == "Decommissioned"
    assert summary.dt_code == "DT-001"


def test_normalize_meter_detail_full():
    raw = {
        "meterId": "J100000",
        "serialNo": "SE33962",
        "make": "HPL",
        "phaseType": "single",
        "installStatus": "Decommissioned",
        "installType": "Whole Current",
        "build": "legacy",
        "dtCode": "DT-001",
        "hierarchy": {
            "zone": {"name": "Jaipur Zone 1", "code": "Z-01"},
            "circle": {"name": "Circle 1", "code": "C-01"},
            "division": {"name": "Division 1", "code": "D-01"},
            "subdivision": {"name": "Subdivision 1", "code": "SD-01"},
            "substation": {"name": "Substation 1", "code": "SS-01"},
            "feeder": {"name": "Feeder 1", "code": "F-001"},
            "dt": {"name": "Malviya Nagar DT 1", "code": "DT-001"},
        },
        "geo": {
            "lat": 26.9389,
            "lng": 75.8309,
        },
    }
    detail = normalize_meter_detail(raw)
    assert detail.meter_id == "J100000"
    assert detail.install_type == "Whole Current"
    assert detail.build_type == "legacy"
    assert detail.geo is not None
    assert detail.geo.latitude == 26.9389
    assert detail.geo.longitude == 75.8309
    assert detail.hierarchy is not None
    assert detail.hierarchy.zone.code == "Z-01"
    assert detail.hierarchy.dt.code == "DT-001"


def test_normalize_consumption_reading():
    raw = {
        "timestamp": "25/06/2026 00:30",
        "kwh": "48459.87",
        "kvah": "52336.66",
        "voltR": "222",
    }
    reading = normalize_consumption_reading(raw)
    assert reading.timestamp == "2026-06-25T00:30:00Z"
    assert reading.kwh == 48459.87
    assert reading.kvah == 52336.66
    assert reading.voltage_r == 222.0


def test_normalize_consumption_reading_handles_missing_or_dash():
    raw = {
        "timestamp": "25/06/2026 01:00",
        "kwh": "—",
        "kvah": None,
        "voltR": "",
    }
    reading = normalize_consumption_reading(raw)
    assert reading.kwh == 0.0
    assert reading.kvah == 0.0
    assert reading.voltage_r == 0.0


def test_normalize_transformer():
    raw = {
        "code": "DT-001",
        "name": "Malviya Nagar DT 1",
        "feederCode": "F-001",
        "capacityKva": "100",
    }
    dt = normalize_transformer(raw)
    assert dt.code == "DT-001"
    assert dt.name == "Malviya Nagar DT 1"
    assert dt.feeder_code == "F-001"
    assert dt.capacity_kva == 100
