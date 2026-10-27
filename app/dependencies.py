from app.client import UrjaClient

_client = UrjaClient()

def get_urja_client() -> UrjaClient:
    return _client
