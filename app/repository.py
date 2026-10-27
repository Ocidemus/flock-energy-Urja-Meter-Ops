import asyncio
from datetime import datetime, timezone
import time
from typing import Dict, List, Optional, Tuple
from app.client import UrjaClient
from app.config import settings
from app.models import (
    MeterSummary,
    MeterDetail,
    TransformerSummary,
    TransformerDetail,
    NetworkTreeNode,
)
from app.normalizer import (
    normalize_meter_detail,
    normalize_meter_summary,
    normalize_transformer,
)


class MeterRepository:
    """In-memory cache and query layer for meters and transformers.

    Why in-memory?
    The entire portal has exactly 403 meters and 40 transformers (<2MB in memory).
    Caching this locally avoids 21+ paginated HTTP calls on every search and allows
    instant cross-filtering across status, phase, make, and DT code that the legacy
    UI doesn't support.
    """

    def __init__(self):
        self._meters: Dict[str, MeterDetail] = {}
        self._transformers: Dict[str, TransformerDetail] = {}
        self._last_synced_at: Optional[datetime] = None
        self._sync_lock = asyncio.Lock()

    @property
    def is_warmed(self) -> bool:
        return bool(self._meters and self._transformers)

    @property
    def last_synced_at(self) -> Optional[str]:
        if self._last_synced_at:
            return self._last_synced_at.isoformat()
        return None

    def is_stale(self) -> bool:
        if not self._last_synced_at:
            return True
        age = (datetime.now(timezone.utc) - self._last_synced_at).total_seconds()
        return age > settings.cache_ttl_seconds

    async def warm_or_refresh(self, client: UrjaClient, force: bool = False):
        """Fetches fresh meter and transformer records from upstream."""
        async with self._sync_lock:
            if not force and self.is_warmed and not self.is_stale():
                return

            # Pull all 40 transformers first to establish parent references
            raw_dts = await client.get_all_dts()
            transformers_map: Dict[str, TransformerDetail] = {}
            for raw_dt in raw_dts:
                summary = normalize_transformer(raw_dt)
                transformers_map[summary.code] = TransformerDetail(
                    code=summary.code,
                    name=summary.name,
                    feeder_code=summary.feeder_code,
                    capacity_kva=summary.capacity_kva,
                    meter_count=0,
                    meters=[],
                )

            # Pull all 403 meters in one HMAC-signed call
            raw_meters = await client.get_bulk_export()
            meters_map: Dict[str, MeterDetail] = {}
            for raw_m in raw_meters:
                detail = normalize_meter_detail(raw_m)
                meters_map[detail.meter_id] = detail

                # Link each meter to its parent distribution transformer
                if detail.dt_code in transformers_map:
                    summary = normalize_meter_summary(raw_m)
                    transformers_map[detail.dt_code].meters.append(summary)
                    transformers_map[detail.dt_code].meter_count += 1

            self._transformers = transformers_map
            self._meters = meters_map
            self._last_synced_at = datetime.now(timezone.utc)

    def get_meter(self, meter_id: str) -> Optional[MeterDetail]:
        return self._meters.get(meter_id)

    def list_meters(
        self,
        q: Optional[str] = None,
        make: Optional[str] = None,
        phase: Optional[str] = None,
        status: Optional[str] = None,
        dt_code: Optional[str] = None,
        install_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[MeterSummary], int, int]:
        """Filters meter records in-memory and returns a paginated slice."""
        results: List[MeterDetail] = list(self._meters.values())

        # Substring search over meter ID or serial
        if q:
            query = q.strip().lower()
            results = [
                m for m in results
                if query in m.meter_id.lower() or query in m.serial_number.lower()
            ]

        if make:
            make_clean = make.strip().lower()
            results = [m for m in results if m.make.lower() == make_clean]

        if phase:
            phase_clean = phase.strip().lower()
            results = [m for m in results if m.phase_type.lower() == phase_clean]

        if status:
            status_clean = status.strip().lower()
            results = [m for m in results if m.install_status.lower() == status_clean]

        if dt_code:
            dt_clean = dt_code.strip().upper()
            results = [m for m in results if m.dt_code.upper() == dt_clean]

        if install_type:
            it_clean = install_type.strip().lower()
            results = [
                m for m in results
                if m.install_type and m.install_type.lower() == it_clean
            ]

        total = len(results)
        page_size = max(1, min(page_size, 100))
        total_pages = max(1, (total + page_size - 1) // page_size)
        page = max(1, min(page, total_pages))

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        sliced = results[start_idx:end_idx]

        summaries = [
            MeterSummary(
                meter_id=m.meter_id,
                serial_number=m.serial_number,
                make=m.make,
                phase_type=m.phase_type,
                install_status=m.install_status,
                dt_code=m.dt_code,
            )
            for m in sliced
        ]

        return summaries, total, total_pages

    def list_transformers(self) -> List[TransformerSummary]:
        return [
            TransformerSummary(
                code=t.code,
                name=t.name,
                feeder_code=t.feeder_code,
                capacity_kva=t.capacity_kva,
            )
            for t in self._transformers.values()
        ]

    def get_transformer(self, code: str) -> Optional[TransformerDetail]:
        return self._transformers.get(code.upper())

    def reconstruct_network_hierarchy(self) -> List[NetworkTreeNode]:
        """Builds a nested tree of the utility grid with aggregated meter counts.
        
        Structure: Zone -> Circle -> Division -> Subdivision -> Substation -> Feeder -> DT.
        """
        root_nodes: Dict[str, Dict[str, Any]] = {}

        for meter in self._meters.values():
            if not meter.hierarchy:
                continue

            h = meter.hierarchy
            z_key = h.zone.code
            if z_key not in root_nodes:
                root_nodes[z_key] = {
                    "node": NetworkTreeNode(name=h.zone.name, code=h.zone.code, type="Zone", meter_count=0, children=[]),
                    "circles": {},
                }
            root_nodes[z_key]["node"].meter_count += 1

            c_key = h.circle.code
            if c_key not in root_nodes[z_key]["circles"]:
                root_nodes[z_key]["circles"][c_key] = {
                    "node": NetworkTreeNode(name=h.circle.name, code=h.circle.code, type="Circle", meter_count=0, children=[]),
                    "divisions": {},
                }
            root_nodes[z_key]["circles"][c_key]["node"].meter_count += 1

            d_key = h.division.code
            if d_key not in root_nodes[z_key]["circles"][c_key]["divisions"]:
                root_nodes[z_key]["circles"][c_key]["divisions"][d_key] = {
                    "node": NetworkTreeNode(name=h.division.name, code=h.division.code, type="Division", meter_count=0, children=[]),
                    "subdivisions": {},
                }
            root_nodes[z_key]["circles"][c_key]["divisions"][d_key]["node"].meter_count += 1

            sd_key = h.subdivision.code
            if sd_key not in root_nodes[z_key]["circles"][c_key]["divisions"][d_key]["subdivisions"]:
                root_nodes[z_key]["circles"][c_key]["divisions"][d_key]["subdivisions"][sd_key] = {
                    "node": NetworkTreeNode(name=h.subdivision.name, code=h.subdivision.code, type="Subdivision", meter_count=0, children=[]),
                    "substations": {},
                }
            root_nodes[z_key]["circles"][c_key]["divisions"][d_key]["subdivisions"][sd_key]["node"].meter_count += 1

            ss_key = h.substation.code
            if ss_key not in root_nodes[z_key]["circles"][c_key]["divisions"][d_key]["subdivisions"][sd_key]["substations"]:
                root_nodes[z_key]["circles"][c_key]["divisions"][d_key]["subdivisions"][sd_key]["substations"][ss_key] = {
                    "node": NetworkTreeNode(name=h.substation.name, code=h.substation.code, type="Substation", meter_count=0, children=[]),
                    "feeders": {},
                }
            root_nodes[z_key]["circles"][c_key]["divisions"][d_key]["subdivisions"][sd_key]["substations"][ss_key]["node"].meter_count += 1

            f_key = h.feeder.code
            if f_key not in root_nodes[z_key]["circles"][c_key]["divisions"][d_key]["subdivisions"][sd_key]["substations"][ss_key]["feeders"]:
                root_nodes[z_key]["circles"][c_key]["divisions"][d_key]["subdivisions"][sd_key]["substations"][ss_key]["feeders"][f_key] = {
                    "node": NetworkTreeNode(name=h.feeder.name, code=h.feeder.code, type="Feeder", meter_count=0, children=[]),
                    "dts": {},
                }
            root_nodes[z_key]["circles"][c_key]["divisions"][d_key]["subdivisions"][sd_key]["substations"][ss_key]["feeders"][f_key]["node"].meter_count += 1

            dt_key = h.dt.code
            if dt_key not in root_nodes[z_key]["circles"][c_key]["divisions"][d_key]["subdivisions"][sd_key]["substations"][ss_key]["feeders"][f_key]["dts"]:
                root_nodes[z_key]["circles"][c_key]["divisions"][d_key]["subdivisions"][sd_key]["substations"][ss_key]["feeders"][f_key]["dts"][dt_key] = NetworkTreeNode(
                    name=h.dt.name,
                    code=h.dt.code,
                    type="DT",
                    meter_count=0,
                    children=None,
                )
            root_nodes[z_key]["circles"][c_key]["divisions"][d_key]["subdivisions"][sd_key]["substations"][ss_key]["feeders"][f_key]["dts"][dt_key].meter_count += 1

        # Stitch nested child lists together
        tree: List[NetworkTreeNode] = []
        for z_info in root_nodes.values():
            z_node = z_info["node"]
            for c_info in z_info["circles"].values():
                c_node = c_info["node"]
                for d_info in c_info["divisions"].values():
                    d_node = d_info["node"]
                    for sd_info in d_info["subdivisions"].values():
                        sd_node = sd_info["node"]
                        for ss_info in sd_info["substations"].values():
                            ss_node = ss_info["node"]
                            for f_info in ss_info["feeders"].values():
                                f_node = f_info["node"]
                                f_node.children = list(f_info["dts"].values())
                                ss_node.children.append(f_node)
                            sd_node.children.append(ss_node)
                        d_node.children.append(sd_node)
                    c_node.children.append(d_node)
                z_node.children.append(c_node)
            tree.append(z_node)

        return tree

    @property
    def meter_count(self) -> int:
        return len(self._meters)

    @property
    def transformer_count(self) -> int:
        return len(self._transformers)


repository = MeterRepository()
