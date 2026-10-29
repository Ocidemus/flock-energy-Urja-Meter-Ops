# Engineering Reflection

## 1. What assumptions did you make?

The primary architectural assumption was that the meter inventory and transformer topology (403 meters across 40 distribution transformers) are relatively static over hours or days, changing only on utility work-order timescales. This justified an in-memory cached repository warmed on startup and refreshed via TTL (default 15 minutes) or operator trigger (`POST /api/v1/meters/sync`), avoiding hundreds of redundant network round-trips to the legacy portal.

A second assumption was regarding time-series energy consumption data: the raw portal timestamps (`"DD/MM/YYYY HH:mm"`) represent 30-minute interval readings aligned with Indian Standard Time (UTC+5:30) utility billing cycles. Normalizing them to ISO 8601 UTC strings (`YYYY-MM-DDTHH:MM:SSZ`) makes them predictable for modern time-series databases while preserving point-in-time accuracy.

Finally, we assumed the portal should strictly remain treated as read-only, never modifying upstream operational states or attempting brute-force exploration beyond the authenticated user's permissions.

---

## 2. Which part was the most difficult, and how did you get unstuck?

The most difficult challenge was untangling the data access paths hidden behind the SvelteKit frontend. Initially, the portal rendered only 20 meters per page in an HTML table, which hinted that reconstructing the full grid would require scraping 21 paginated pages plus hundreds of individual meter views. 

To get unstuck, instead of writing an elaborate DOM scraper, we inspected the compiled client-side JavaScript bundles (`4.2Bgc2kUI.js` and `6.l777LXKL.js`). This revealed two breakthroughs:
1. The SvelteKit form action on `/login` rejected programmatic requests with `HTTP 403 Forbidden: Cross-site POST form submissions are forbidden`. Consulting an LLM to clarify SvelteKit's CSRF mechanics confirmed that SvelteKit strictly checks the `Origin` header on form submissions. Supplying `Origin: https://urja-ops.flockenergy.tech` immediately unblocked login.
2. The "Transformers" page contained an export routine that fetched a signing key from `/portal/keys` and computed an HMAC-SHA256 signature (`GET\n/portal/export\npage=1\n<timestamp>`) over `/portal/export?page=1`. Replicating this cryptographic handshake unlocked all 403 meters with complete 7-level hierarchy and geo-coordinates in a single sub-second call.

---

## 3. If you had another day, what would you improve?

1. **Persistent Local Store (SQLite / DuckDB):** While the in-memory repository is lightweight and requires zero external dependencies, backing it with an embedded SQLite or DuckDB database would allow persistent historical consumption analysis, SQL querying across feeders, and geospatial indexing (e.g. SpatiaLite for "find meters within 500m of DT-001").
2. **Streaming Telemetry & WebSockets:** Provide a WebSocket or Server-Sent Events (SSE) feed for consumption telemetry so monitoring dashboards don't need to poll individual meter endpoints.
3. **Automated Prometheus Metrics:** Expose Prometheus metrics (`/metrics`) tracking upstream portal latency, cache hit ratios, HMAC renewal frequency, and 401 token refresh counters.
4. **Resilience & Circuit Breaking:** Implement Tenacity-based exponential backoff with circuit breaker states for upstream outages.

---

## 4. What mistake did you make while solving this?

When first investigating the `/login` endpoint via `curl`, I neglected SvelteKit's CSRF protection and sent a standard POST without an `Origin` header. The portal immediately responded with `HTTP 403 Forbidden: Cross-site POST form submissions are forbidden`. For a moment, I wondered if the credentials from the PDF were outdated or if a dynamic CSRF token hidden in the DOM was missing.

Before jumping down a rabbit hole of DOM parsing for hidden input tokens, I tested setting the `Origin` header to match the portal's origin. The request immediately succeeded with an HTTP 200 redirect and the `__Secure-better-auth.session_token` cookie. The mistake was assuming standard HTML form behavior without accounting for modern SPA framework CSRF origin enforcement.

---

## 5. If you were reviewing your own submission, what would you criticise?

1. **In-Memory Cache vs. Multi-Worker Deployments:** In a multi-worker production setup (e.g., Uvicorn with 4 worker processes), each process maintains its own independent in-memory repository, causing multiple initial sync requests to the upstream portal. A distributed cache like Redis or a shared SQLite database would be cleaner for multi-process environments.
2. **Direct Upstream Coupling for Energy Readings:** While meter inventory is cached, consumption interval data (`/api/v1/meters/{id}/consumption`) directly proxies upstream requests. If the upstream portal experiences high latency or downtime, time-series requests will stall. A small short-lived cache (e.g., 60 seconds) on consumption responses would improve resilience during burst queries.
3. **OpenAPI Spec Maintenance:** While the OpenAPI specification is dynamically generated and exported, a CI workflow step should enforce that `openapi.json` is automatically verified against code modifications to prevent drift.
