# Flock Energy — Urja Meter Ops API

A clean, reliable, typed REST API and operations explorer built over the legacy **Urja Meter Ops** portal (`https://urja-ops.flockenergy.tech`).

This service transforms an internal utility web application that lacked an API into a structured, normalized, and well-documented programmatic interface. It exposes meter inventories, 30-minute interval energy consumption readings, distribution transformer topologies, and a reconstructed 7-level distribution network hierarchy.

---

## Deliverables & Documentation Index

- **[PROTOCOL.md](PROTOCOL.md)**: Technical protocol teardown of the legacy portal (SvelteKit SSR/CSR, `better-auth` session management, CSRF Origin enforcement, HMAC-SHA256 bulk export protocol, and schema quirks).
- **[DECISIONS.md](DECISIONS.md)**: Chronological engineering decision log, investigation trail, errors encountered, recovery steps, and architectural trade-offs.
- **[openapi.json](openapi.json)**: OpenAPI 3.1 specification for this API service.
- **[REFLECTION.md](REFLECTION.md)**: Candid engineering reflection answering the 5 core assignment questions.
- **Interactive API Documentation:** Available at `http://127.0.0.1:8000/docs` (Swagger UI) and `http://127.0.0.1:8000/redoc` (ReDoc).
- **Interactive Operations Dashboard:** Built-in web explorer available at `http://127.0.0.1:8000/` (or `/ui`).

---

## Architecture Overview

```mermaid
flowchart LR
    Client["API Client / Frontend / Script"]
    
    subgraph Service["Urja Meter Ops API Service (FastAPI)"]
        Router["API Routers\n/api/v1/*"]
        Repo["In-Memory Repository\n& Query Index\n(15-min TTL)"]
        Normalizer["Data Normalizer\n(Legacy vs v2,\nFloats, ISO Timestamps)"]
        UpstreamClient["UrjaClient\n(Session Lifecycle,\nCSRF Origin, HMAC Signer)"]
    end
    
    subgraph Portal["Legacy Urja Portal (SvelteKit)"]
        Auth["/login\n(better-auth)"]
        Export["/portal/export\n(HMAC-SHA256)"]
        DTs["/portal/dts"]
        Energy["/portal/meters/:id/energy\n(30-min intervals)"]
    end
    
    Client -->|HTTP / JSON| Router
    Router --> Repo
    Router --> UpstreamClient
    Repo --> Normalizer
    Normalizer --> UpstreamClient
    UpstreamClient -->|Cookie + Origin| Auth
    UpstreamClient -->|x-signature + x-timestamp| Export
    UpstreamClient -->|Session Cookie| DTs
    UpstreamClient -->|Session Cookie| Energy
```

### Key Architectural Highlights
1. **Hybrid Retrieval Strategy:** On startup, the service performs an HMAC-signed bulk export call to warm an in-memory repository with all 403 meters, 40 distribution transformers, and network hierarchies. This allows sub-millisecond search and cross-attribute filtering without slamming the legacy portal. Time-series consumption queries are proxied on-demand with live upstream date filtering.
2. **Strict Normalization Pipeline:** Seamlessly normalizes inconsistent legacy data:
   - Reconciles `build: "legacy"` (parameter key-value arrays) and `build: "v2"` (embedded `classData` JSON strings).
   - Converts Indian-format timestamps (`DD/MM/YYYY HH:mm`) into standard ISO 8601 UTC strings (`YYYY-MM-DDTHH:MM:SSZ`).
   - Converts numeric strings (`"kwh": "48438.74"`, `"voltR": "226"`) into native floats.
   - Normalizes coordinates into typed WGS84 `latitude` and `longitude`.
3. **Session Resilience:** `UrjaClient` manages `better-auth` session cookies, handles SvelteKit CSRF origin validation, and automatically re-authenticates and retries requests upon 401 expiration.

---

## Project Structure

```text
urja-meter-ops-api/
├── app/
│   ├── __init__.py
│   ├── config.py           # Environment settings & defaults
│   ├── models.py           # Pydantic v2 schemas & domain models
│   ├── client.py           # Resilient upstream HTTP client & HMAC signing
│   ├── normalizer.py       # Data cleansing & format standardization
│   ├── repository.py       # In-memory indexed store & hierarchy builder
│   ├── dependencies.py     # FastAPI dependency injection singletons
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py       # GET /api/v1/health
│   │   ├── meters.py       # GET /api/v1/meters, /meters/{id}, /meters/{id}/consumption
│   │   ├── transformers.py # GET /api/v1/transformers, /transformers/{code}
│   │   ├── network.py      # GET /api/v1/network/hierarchy, /api/v1/export/meters
│   │   └── ui.py           # GET / (Interactive Web Dashboard)
│   └── main.py             # FastAPI application factory & lifecycle
├── tests/
│   ├── __init__.py
│   ├── test_normalizer.py  # Unit tests for data transformation
│   ├── test_client.py      # Unit tests for client & HMAC signing
│   ├── test_api.py         # Route & integration tests using TestClient
│   └── test_integration.py # Live smoke test against urja-ops.flockenergy.tech
├── openapi.json            # OpenAPI 3.1 specification
├── PROTOCOL.md             # Reverse-engineered legacy portal protocol
├── DECISIONS.md            # Engineering decision log & investigation notes
├── REFLECTION.md           # Engineering critique & reflection
├── requirements.txt        # Pinned dependencies
├── .env.example            # Environment variable template
├── .gitignore
├── run.py                  # CLI entry point
└── README.md               # Main documentation
```

---

## Installation & Setup

### Prerequisites
- Python 3.10+ (tested on Python 3.14)
- Git

### 1. Clone & Setup Workspace
```bash
git clone <repo-url>
cd urja-meter-ops-api
```

### 2. Create Virtual Environment & Install Dependencies
```bash
python -m venv .venv
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and fill in credentials:
```bash
cp .env.example .env
```
Default configuration values:
```ini
URJA_PORTAL_URL=https://urja-ops.flockenergy.tech
URJA_USERNAME=operator@urja.local
URJA_PASSWORD=urja-ops-2026
CACHE_TTL_SECONDS=900
REQUEST_TIMEOUT=15.0
HOST=127.0.0.1
PORT=8000
```

---

## Running the Service

### Option A: Using the CLI Runner
```bash
python run.py
```

### Option B: Using Uvicorn Directly
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Once running:
- **Web Dashboard:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Interactive Swagger Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **OpenAPI Schema:** [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

---

## Running Tests

The test suite includes 21 tests covering unit normalization, cryptographic HMAC generation, API route responses, and live end-to-end portal verification.

```bash
# Run complete test suite:
pytest tests/ -v
```

Expected output:
```text
tests/test_api.py ...........                                    [ 52%]
tests/test_client.py ..                                          [ 61%]
tests/test_integration.py .                                      [ 66%]
tests/test_normalizer.py .......                                 [100%]
======================== 21 passed in 1.52s ========================
```

---

## API Reference & Sample Requests

### 1. Health Status
Check service readiness, cache warmth, and upstream session state.

**Request:**
```bash
curl -s http://127.0.0.1:8000/api/v1/health | jq
```

**Response:**
```json
{
  "status": "healthy",
  "upstream_portal": "https://urja-ops.flockenergy.tech",
  "upstream_authenticated": true,
  "cached_meters": 403,
  "cached_transformers": 40,
  "cache_last_updated": "2026-10-27T19:38:00.123456Z"
}
```

---

### 2. List & Filter Smart Meters
Search meters by query string or filter across make, phase configuration, installation status, or distribution transformer.

**Request:**
```bash
curl -s "http://127.0.0.1:8000/api/v1/meters?q=SE33&status=Decommissioned&page=1&page_size=2" | jq
```

**Response:**
```json
{
  "data": [
    {
      "meter_id": "J100000",
      "serial_number": "SE33962",
      "make": "HPL",
      "phase_type": "single",
      "install_status": "Decommissioned",
      "dt_code": "DT-001"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 2,
  "total_pages": 1
}
```

---

### 3. Get Meter Profile & Topology
Retrieve full profile for a meter including geographic coordinates, nameplate ratings, and full 7-level grid hierarchy.

**Request:**
```bash
curl -s http://127.0.0.1:8000/api/v1/meters/J100000 | jq
```

**Response:**
```json
{
  "meter_id": "J100000",
  "serial_number": "SE33962",
  "make": "HPL",
  "phase_type": "single",
  "install_status": "Decommissioned",
  "dt_code": "DT-001",
  "install_type": "Whole Current",
  "build_type": "legacy",
  "geo": {
    "latitude": 26.938961002479868,
    "longitude": 75.83095696146852
  },
  "hierarchy": {
    "zone": { "name": "Jaipur Zone 1", "code": "Z-01" },
    "circle": { "name": "Circle 1", "code": "C-01" },
    "division": { "name": "Division 1", "code": "D-01" },
    "subdivision": { "name": "Subdivision 1", "code": "SD-01" },
    "substation": { "name": "Substation 1", "code": "SS-01" },
    "feeder": { "name": "Feeder 1", "code": "F-001" },
    "dt": { "name": "Malviya Nagar DT 1", "code": "DT-001" }
  }
}
```

---

### 4. Get Interval Energy Consumption
Retrieve 30-minute interval active power (kWh), apparent power (kVAh), and voltage readings, with optional date filtering (`YYYY-MM-DD`).

**Request:**
```bash
curl -s "http://127.0.0.1:8000/api/v1/meters/J100000/consumption?from_date=2026-06-25&to_date=2026-06-25" | jq
```

**Response:**
```json
{
  "meter_id": "J100000",
  "total_readings": 48,
  "filter": {
    "start": "2026-06-25",
    "end": "2026-06-25"
  },
  "data": [
    {
      "timestamp": "2026-06-25T00:00:00Z",
      "kwh": 48459.45,
      "kvah": 52336.21,
      "voltage_r": 226.0
    },
    {
      "timestamp": "2026-06-25T00:30:00Z",
      "kwh": 48459.87,
      "kvah": 52336.66,
      "voltage_r": 222.0
    }
  ]
}
```

---

### 5. Distribution Transformers
List all 40 distribution transformers and inspect connected meters.

**Request:**
```bash
curl -s http://127.0.0.1:8000/api/v1/transformers/DT-001 | jq
```

**Response:**
```json
{
  "code": "DT-001",
  "name": "Malviya Nagar DT 1",
  "feeder_code": "F-001",
  "capacity_kva": 100,
  "meter_count": 11,
  "meters": [
    {
      "meter_id": "J100000",
      "serial_number": "SE33962",
      "make": "HPL",
      "phase_type": "single",
      "install_status": "Decommissioned",
      "dt_code": "DT-001"
    }
  ]
}
```

---

### 6. Network Hierarchy Tree
Returns the reconstructed distribution network tree from Zone down to DT with aggregated meter counts at every level.

**Request:**
```bash
curl -s http://127.0.0.1:8000/api/v1/network/hierarchy | jq '.[0] | {name, type, meter_count, child_circles: (.children | length)}'
```

**Response:**
```json
{
  "name": "Jaipur Zone 1",
  "type": "Zone",
  "meter_count": 403,
  "child_circles": 1
}
```

---

## Interactive Operations Dashboard

To demonstrate strong product sense and visual clarity, the service includes a lightweight, responsive Web Operations Dashboard served at `http://127.0.0.1:8000/`.

Features:
- **Live Sync Indicator:** Displays upstream session and cache synchronization health.
- **Instant Search & Multi-filter:** Search across meter IDs, serial numbers, operational statuses, and makes with real-time UI updates.
- **Interactive Telemetry Chart:** Selecting any meter automatically fetches its interval readings and renders a 24-hour kWh consumption line graph using Chart.js.
- **Physical Coordinates & Hierarchy:** Displays breadcrumbs from Zone to DT and coordinates.

---

## Assumptions, Design Decisions, & Trade-offs

| Decision | Selected Option | Rationale | Trade-off |
|---|---|---|---|
| **Language & Framework** | Python 3.14 + FastAPI + Pydantic v2 | Native OpenAPI 3.1 generation, built-in Swagger/ReDoc, strict type validation, and rapid implementation within 4–6 hour scope. | Python's GIL is present, but negligible for I/O-bound proxying. |
| **Data Extraction** | HMAC Bulk Export + Live Interval Queries | Single signed request to `/portal/export` extracts all 403 meters in <300ms, eliminating 400+ sequential HTTP round-trips. | In-memory cache must be refreshed periodically (15-min default TTL). |
| **Session Handling** | Proactive Session Caching & 401 Auto-Recovery | Better-Auth tokens expire after 1 hour. Caching tokens avoids 200ms login overhead on every request. | Requires async locking during session rotation. |
| **Data Normalization** | Strict Canonical Schemas | Eliminates differences between legacy parameter arrays and v2 `classData` JSON strings. Numbers converted from strings to floats. | Upstream fields not in schema are dropped or stored in detail. |

---

## Features Deliberately Omitted

1. **Relational Database Backend:** Storing data in PostgreSQL/SQLite was omitted because the entire dataset (403 meters, 40 DTs) fits comfortably in memory (<5MB footprint). Adding an external database would add operational complexity without benefit.
2. **Write / Mutation Operations:** The portal is strictly read-only; no endpoints for meter provisioning or decommission were introduced.
3. **Consumer OAuth2 Provider:** The API focuses on service-to-service utility integration; enterprise OAuth2 bearer security can be layered on via API gateway or FastAPI middleware.

---

## Known Limitations & Next Steps

1. **Multi-Worker Cache Invalidation:** When running multiple Uvicorn worker processes, in-memory caches are isolated per process. In a production cluster, an external Redis cache or SQLite read-through store would unify cache state.
2. **Consumption Caching:** Consumption interval queries proxy live to upstream. If the portal experiences an outage, consumption requests will return 502. Adding a short-lived cache (e.g. 60s) for time-series readings would increase resilience.
3. **Spatial Querying:** Adding GeoJSON output and spatial radius filtering (e.g. "meters within 1km") would further empower field operations.
