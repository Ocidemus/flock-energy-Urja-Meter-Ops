from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.models import (
    MeterSummary,
    MeterDetail,
    GeoCoordinates,
    NetworkHierarchy,
    HierarchyNode,
    ConsumptionReading,
    TransformerSummary,
)


def parse_legacy_timestamp(ts_str: str) -> str:
    """Converts the portal's Indian format timestamp ('DD/MM/YYYY HH:mm') to ISO-8601 UTC."""
    try:
        dt = datetime.strptime(ts_str.strip(), "%d/%m/%Y %H:%M")
        return dt.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        # If upstream ever sends an already-formatted or unexpected string, pass it through
        return ts_str


def normalize_meter_summary(raw: Dict[str, Any]) -> MeterSummary:
    """Normalizes raw meter search or export records into a consistent MeterSummary."""
    return MeterSummary(
        meter_id=raw.get("meterId") or raw.get("meter_id", ""),
        serial_number=raw.get("serialNo") or raw.get("serial_number", ""),
        make=raw.get("make", "Unknown"),
        phase_type=raw.get("phaseType") or raw.get("phase_type", "single"),
        install_status=raw.get("installStatus") or raw.get("install_status", "Installed"),
        dt_code=raw.get("dtCode") or raw.get("dt_code", ""),
    )


def normalize_meter_detail(raw: Dict[str, Any]) -> MeterDetail:
    """Normalizes a full meter record including geo coordinates and network hierarchy.

    Handles the schema divergence observed across the 403 meters:
    - 238 meters ('legacy' build) use a parameter key-value array in raw data.
    - 165 meters ('v2' build) store specs as an embedded JSON string in classData.
    The bulk export endpoint already normalizes most fields, but we validate and cast
    coordinates and hierarchy nodes defensively.
    """
    summary = normalize_meter_summary(raw)
    
    # Coordinates in the portal are sometimes floats and sometimes string floats
    geo_data = raw.get("geo")
    geo: Optional[GeoCoordinates] = None
    if geo_data:
        lat = geo_data.get("lat") or geo_data.get("latitude")
        lng = geo_data.get("lng") or geo_data.get("longitude")
        if lat is not None and lng is not None:
            try:
                geo = GeoCoordinates(latitude=float(lat), longitude=float(lng))
            except (ValueError, TypeError):
                geo = None

    # Reconstruct the 7-level electrical hierarchy
    hier_data = raw.get("hierarchy")
    hierarchy: Optional[NetworkHierarchy] = None
    if hier_data and isinstance(hier_data, dict):
        try:
            hierarchy = NetworkHierarchy(
                zone=HierarchyNode(
                    name=hier_data.get("zone", {}).get("name", "Unknown Zone"),
                    code=hier_data.get("zone", {}).get("code", "Z-00"),
                ),
                circle=HierarchyNode(
                    name=hier_data.get("circle", {}).get("name", "Unknown Circle"),
                    code=hier_data.get("circle", {}).get("code", "C-00"),
                ),
                division=HierarchyNode(
                    name=hier_data.get("division", {}).get("name", "Unknown Division"),
                    code=hier_data.get("division", {}).get("code", "D-00"),
                ),
                subdivision=HierarchyNode(
                    name=hier_data.get("subdivision", {}).get("name", "Unknown Subdivision"),
                    code=hier_data.get("subdivision", {}).get("code", "SD-00"),
                ),
                substation=HierarchyNode(
                    name=hier_data.get("substation", {}).get("name", "Unknown Substation"),
                    code=hier_data.get("substation", {}).get("code", "SS-00"),
                ),
                feeder=HierarchyNode(
                    name=hier_data.get("feeder", {}).get("name", "Unknown Feeder"),
                    code=hier_data.get("feeder", {}).get("code", "F-000"),
                ),
                dt=HierarchyNode(
                    name=hier_data.get("dt", {}).get("name", "Unknown DT"),
                    code=hier_data.get("dt", {}).get("code", summary.dt_code or "DT-000"),
                ),
            )
        except Exception:
            hierarchy = None

    return MeterDetail(
        meter_id=summary.meter_id,
        serial_number=summary.serial_number,
        make=summary.make,
        phase_type=summary.phase_type,
        install_status=summary.install_status,
        dt_code=summary.dt_code,
        install_type=raw.get("installType") or raw.get("install_type"),
        build_type=raw.get("build") or raw.get("build_type"),
        geo=geo,
        hierarchy=hierarchy,
    )


def normalize_consumption_reading(raw: Dict[str, Any]) -> ConsumptionReading:
    """Casts string telemetry numbers to native floats and handles missing or em-dash entries."""
    ts = parse_legacy_timestamp(raw.get("timestamp", ""))
    
    def to_float(val: Any) -> float:
        # Legacy portal occasionally sends "—" or empty string when readings are missing
        if val is None or val == "" or val == "—":
            return 0.0
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    return ConsumptionReading(
        timestamp=ts,
        kwh=to_float(raw.get("kwh")),
        kvah=to_float(raw.get("kvah")),
        voltage_r=to_float(raw.get("voltR")),
    )


def normalize_transformer(raw: Dict[str, Any]) -> TransformerSummary:
    """Normalizes raw DT record into a typed TransformerSummary model."""
    cap = raw.get("capacityKva") or raw.get("capacity_kva", 0)
    try:
        cap_val = int(cap)
    except (ValueError, TypeError):
        cap_val = 0
        
    return TransformerSummary(
        code=raw.get("code", ""),
        name=raw.get("name", "Unknown"),
        feeder_code=raw.get("feederCode") or raw.get("feeder_code", ""),
        capacity_kva=cap_val,
    )
