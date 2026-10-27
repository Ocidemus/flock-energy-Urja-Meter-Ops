from __future__ import annotations
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class PhaseType(str, Enum):
    SINGLE = "single"
    THREE = "three"


class InstallStatus(str, Enum):
    INSTALLED = "Installed"
    FAULTY = "Faulty"
    DECOMMISSIONED = "Decommissioned"


class InstallType(str, Enum):
    WHOLE_CURRENT = "Whole Current"
    CT_OPERATED = "CT Operated"


class GeoCoordinates(BaseModel):
    latitude: float = Field(..., description="WGS84 Latitude")
    longitude: float = Field(..., description="WGS84 Longitude")


class HierarchyNode(BaseModel):
    name: str = Field(..., description="Entity display name")
    code: str = Field(..., description="Entity unique code identifier")


class NetworkHierarchy(BaseModel):
    zone: HierarchyNode
    circle: HierarchyNode
    division: HierarchyNode
    subdivision: HierarchyNode
    substation: HierarchyNode
    feeder: HierarchyNode
    dt: HierarchyNode


class MeterSummary(BaseModel):
    meter_id: str = Field(..., description="Utility meter identifier (e.g. J100000)")
    serial_number: str = Field(..., description="Hardware manufacturer serial number")
    make: str = Field(..., description="Hardware manufacturer (e.g. Genus, HPL, L&T, Secure, Allied)")
    phase_type: str = Field(..., description="Phase configuration: single or three")
    install_status: str = Field(..., description="Operational status: Installed, Faulty, or Decommissioned")
    dt_code: str = Field(..., description="Distribution transformer code (e.g. DT-001)")


class MeterDetail(MeterSummary):
    install_type: Optional[str] = Field(None, description="Installation type (e.g. Whole Current, CT Operated)")
    build_type: Optional[str] = Field(None, description="Internal telemetry revision: legacy or v2")
    geo: Optional[GeoCoordinates] = Field(None, description="Physical geographic coordinates")
    hierarchy: Optional[NetworkHierarchy] = Field(None, description="7-level grid hierarchy")


class MeterListResponse(BaseModel):
    data: List[MeterSummary]
    total: int = Field(..., description="Total matching meter count")
    page: int = Field(..., description="Current page number (1-based)")
    page_size: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total available pages")


class ConsumptionReading(BaseModel):
    timestamp: str = Field(..., description="Reading interval timestamp in ISO 8601 format (UTC)")
    kwh: float = Field(..., description="Active energy consumed in kWh")
    kvah: float = Field(..., description="Apparent energy consumed in kVAh")
    voltage_r: float = Field(..., description="R-phase voltage in Volts")


class DateRange(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None


class ConsumptionResponse(BaseModel):
    meter_id: str
    total_readings: int
    filter: DateRange
    data: List[ConsumptionReading]


class TransformerSummary(BaseModel):
    code: str = Field(..., description="Distribution Transformer code (e.g. DT-001)")
    name: str = Field(..., description="Transformer station name")
    feeder_code: str = Field(..., description="Feeding 11kV line code (e.g. F-001)")
    capacity_kva: int = Field(..., description="Transformer rated capacity in kVA")


class TransformerDetail(TransformerSummary):
    meter_count: int = Field(..., description="Number of active meters connected to this transformer")
    meters: List[MeterSummary] = Field(default_factory=list, description="Connected meters")


class TransformerListResponse(BaseModel):
    data: List[TransformerSummary]
    total: int


class NetworkTreeNode(BaseModel):
    name: str
    code: str
    type: str = Field(..., description="Hierarchy level: Zone, Circle, Division, Subdivision, Substation, Feeder, DT, or Meter")
    meter_count: int = Field(default=0, description="Total meters subordinate to this node")
    children: Optional[List[NetworkTreeNode]] = None


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service status: healthy or degraded")
    upstream_portal: str = Field(..., description="Base URL of upstream portal")
    upstream_authenticated: bool = Field(..., description="Whether upstream session is currently active")
    cached_meters: int = Field(..., description="Number of meters currently indexed in memory")
    cached_transformers: int = Field(..., description="Number of transformers currently indexed in memory")
    cache_last_updated: Optional[str] = Field(None, description="ISO timestamp of last cache synchronization")
