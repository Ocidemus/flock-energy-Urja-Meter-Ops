import asyncio
import hashlib
import hmac
import time
from typing import Any, Dict, List, Optional
import httpx
from app.config import settings


class UrjaClientError(Exception):
    pass


class UrjaAuthError(UrjaClientError):
    pass


class UrjaNotFoundError(UrjaClientError):
    pass


class UrjaUpstreamError(UrjaClientError):
    pass


class UrjaClient:
    """Handles communication with the Urja Meter Ops SvelteKit backend.

    Manages better-auth session cookies, CSRF Origin headers, token refresh on 401,
    and HMAC request signing for the bulk export endpoint.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.base_url = (base_url or settings.portal_url).rstrip("/")
        self.username = username or settings.portal_username
        self.password = password or settings.portal_password
        self.timeout = timeout or settings.request_timeout

        self._session_token: Optional[str] = None
        self._session_expires_at: float = 0
        self._lock = asyncio.Lock()
        self._http: Optional[httpx.AsyncClient] = None

    def _get_http_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=False,
                headers={"User-Agent": "Urja-Meter-Ops-API/1.0"},
            )
        return self._http

    async def close(self):
        if self._http and not self._http.is_closed:
            await self._http.aclose()
            self._http = None

    @property
    def is_authenticated(self) -> bool:
        return bool(self._session_token and time.time() < self._session_expires_at)

    async def login(self, force: bool = False) -> str:
        """Authenticates with the portal and stores the session token.

        Quirk discovered during testing: SvelteKit form actions reject POST requests
        without an Origin header (returning 403 Forbidden). We must explicitly pass
        the portal's Origin header here.
        """
        async with self._lock:
            if not force and self.is_authenticated and self._session_token:
                return self._session_token

            client = self._get_http_client()
            login_url = f"{self.base_url}/login"
            
            headers = {
                "Origin": self.base_url,
                "Content-Type": "application/x-www-form-urlencoded",
            }
            payload = {
                "email": self.username,
                "password": self.password,
            }

            try:
                resp = await client.post(login_url, data=payload, headers=headers)
            except httpx.RequestError as exc:
                raise UrjaUpstreamError(f"Network error during login: {exc}") from exc

            if resp.status_code == 403:
                raise UrjaAuthError("Login failed: SvelteKit CSRF origin check rejected the request.")

            # better-auth sets __Secure-better-auth.session_token with Max-Age=3600
            session_cookie = None
            for cookie_header in resp.headers.get_list("set-cookie"):
                if "__Secure-better-auth.session_token=" in cookie_header:
                    token_part = cookie_header.split("__Secure-better-auth.session_token=")[1]
                    session_cookie = token_part.split(";")[0]
                    break

            if not session_cookie:
                try:
                    data = resp.json()
                    if data.get("type") == "failure":
                        raise UrjaAuthError(f"Invalid credentials for user '{self.username}'")
                except Exception:
                    pass
                raise UrjaAuthError("Authentication failed: No session cookie returned by portal.")

            self._session_token = session_cookie
            # Session cookie has a 1-hour Max-Age; refresh slightly earlier (at 50 min)
            self._session_expires_at = time.time() + 3000
            return self._session_token

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        retries_on_401: bool = True,
    ) -> httpx.Response:
        """Executes an authenticated request, auto-recovering on session expiry."""
        token = await self.login()
        client = self._get_http_client()

        req_headers = {"Cookie": f"__Secure-better-auth.session_token={token}"}
        if headers:
            req_headers.update(headers)

        url = f"{self.base_url}{path}"

        try:
            resp = await client.request(method, url, params=params, headers=req_headers)
        except httpx.RequestError as exc:
            raise UrjaUpstreamError(f"Network error requesting {path}: {exc}") from exc

        # If the session expired on the server, re-authenticate once and retry
        if resp.status_code == 401 and retries_on_401:
            await self.login(force=True)
            return await self._request(method, path, params=params, headers=headers, retries_on_401=False)

        if resp.status_code == 404:
            raise UrjaNotFoundError(f"Resource not found at {path}")

        if resp.status_code >= 500:
            raise UrjaUpstreamError(f"Upstream portal returned {resp.status_code} for {path}")

        return resp

    async def search_meters(self, q: str = "", page: int = 1) -> Dict[str, Any]:
        resp = await self._request("GET", "/portal/meters/search", params={"q": q, "page": page})
        return resp.json()

    async def get_dts(self, page: int = 1) -> Dict[str, Any]:
        resp = await self._request("GET", "/portal/dts", params={"page": page})
        return resp.json()

    async def get_all_dts(self) -> List[Dict[str, Any]]:
        """Fetches all distribution transformers across all pages (40 DTs total)."""
        all_dts: List[Dict[str, Any]] = []
        page = 1
        while True:
            data = await self.get_dts(page=page)
            items = data.get("data", [])
            all_dts.extend(items)
            total = data.get("total", 0)
            if len(all_dts) >= total or not items:
                break
            page += 1
        return all_dts

    async def get_signing_secret(self) -> str:
        resp = await self._request("GET", "/portal/keys")
        data = resp.json()
        secret = data.get("data", {}).get("signingSecret")
        if not secret:
            raise UrjaUpstreamError("Missing signing secret from /portal/keys.")
        return secret

    async def get_bulk_export(self) -> List[Dict[str, Any]]:
        """Fetches all 403 meters using the portal's HMAC export path.

        Reverse-engineered from the Transformers client bundle (4.2Bgc2kUI.js):
        The portal signs 'GET\n/portal/export\npage=1\n<timestamp>' with the secret
        from /portal/keys and passes x-timestamp and x-signature headers.
        """
        secret = await self.get_signing_secret()
        timestamp = str(int(time.time()))
        path = "/portal/export"
        query = "page=1"
        
        sig_payload = f"GET\n{path}\n{query}\n{timestamp}"
        signature = hmac.new(
            secret.encode("utf-8"),
            sig_payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        headers = {
            "x-timestamp": timestamp,
            "x-signature": signature,
        }

        resp = await self._request("GET", f"{path}?{query}", headers=headers)
        data = resp.json()
        return data.get("data", [])

    async def get_meter_geo(self, meter_id: str) -> Dict[str, Any]:
        resp = await self._request("GET", f"/portal/meters/{meter_id}/geo")
        return resp.json().get("data", {})

    async def get_meter_energy(
        self,
        meter_id: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Queries 30-minute interval readings. Supports from/to date filtering (YYYY-MM-DD)."""
        params: Dict[str, Any] = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        resp = await self._request("GET", f"/portal/meters/{meter_id}/energy", params=params)
        return resp.json().get("data", [])
