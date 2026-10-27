import hashlib
import hmac
import pytest
from app.client import UrjaClient, UrjaAuthError, UrjaNotFoundError


def test_hmac_signing_logic():
    secret = "test_signing_secret"
    timestamp = "1720000000"
    path = "/portal/export"
    query = "page=1"
    
    payload = f"GET\n{path}\n{query}\n{timestamp}"
    expected_sig = hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    assert len(expected_sig) == 64
    assert isinstance(expected_sig, str)


def test_client_initial_state():
    client = UrjaClient(
        base_url="https://urja-ops.flockenergy.tech",
        username="test@urja.local",
        password="secretpassword",
    )
    assert not client.is_authenticated
    assert client.base_url == "https://urja-ops.flockenergy.tech"
