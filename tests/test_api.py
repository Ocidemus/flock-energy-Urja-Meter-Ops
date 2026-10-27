import pytest
from starlette.testclient import TestClient
from app.main import app
from app.repository import repository
from app.models import (
    MeterDetail,
    TransformerDetail,
    NetworkHierarchy,
    HierarchyNode,
    GeoCoordinates,
)


@pytest.fixture(autouse=True)
def seed_repository():
    repository._meters.clear()
    repository._transformers.clear()

    repository._transformers["DT-001"] = TransformerDetail(
        code="DT-001",
        name="Malviya Nagar DT 1",
        feeder_code="F-001",
        capacity_kva=100,
        meter_count=1,
        meters=[],
    )

    repository._meters["J100000"] = MeterDetail(
        meter_id="J100000",
        serial_number="SE33962",
        make="HPL",
        phase_type="single",
        install_status="Installed",
        install_type="Whole Current",
        build_type="legacy",
        dt_code="DT-001",
        geo=GeoCoordinates(latitude=26.9389, longitude=75.8309),
        hierarchy=NetworkHierarchy(
            zone=HierarchyNode(name="Jaipur Zone 1", code="Z-01"),
            circle=HierarchyNode(name="Circle 1", code="C-01"),
            division=HierarchyNode(name="Division 1", code="D-01"),
            subdivision=HierarchyNode(name="Subdivision 1", code="SD-01"),
            substation=HierarchyNode(name="Substation 1", code="SS-01"),
            feeder=HierarchyNode(name="Feeder 1", code="F-001"),
            dt=HierarchyNode(name="Malviya Nagar DT 1", code="DT-001"),
        ),
    )

    repository._meters["J100001"] = MeterDetail(
        meter_id="J100001",
        serial_number="GE84132",
        make="L&T",
        phase_type="three",
        install_status="Faulty",
        install_type="CT Operated",
        build_type="v2",
        dt_code="DT-001",
    )


client = TestClient(app, raise_server_exceptions=False)


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["cached_meters"] == 2
    assert data["cached_transformers"] == 1


def test_list_meters_pagination_and_total():
    response = client.get("/api/v1/meters?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["data"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 10


def test_list_meters_search_filter():
    response = client.get("/api/v1/meters?q=SE33962")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["data"][0]["meter_id"] == "J100000"


def test_list_meters_status_filter():
    response = client.get("/api/v1/meters?status=Faulty")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["data"][0]["meter_id"] == "J100001"


def test_get_meter_by_id_success():
    response = client.get("/api/v1/meters/J100000")
    assert response.status_code == 200
    data = response.json()
    assert data["meter_id"] == "J100000"
    assert data["serial_number"] == "SE33962"
    assert data["geo"]["latitude"] == 26.9389
    assert data["hierarchy"]["zone"]["code"] == "Z-01"


def test_get_meter_by_id_not_found():
    response = client.get("/api/v1/meters/NONEXISTENT")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_list_transformers():
    response = client.get("/api/v1/transformers")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["data"][0]["code"] == "DT-001"


def test_get_transformer_by_code():
    response = client.get("/api/v1/transformers/DT-001")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "DT-001"
    assert data["capacity_kva"] == 100


def test_get_transformer_not_found():
    response = client.get("/api/v1/transformers/DT-999")
    assert response.status_code == 404


def test_network_hierarchy():
    response = client.get("/api/v1/network/hierarchy")
    assert response.status_code == 200
    tree = response.json()
    assert len(tree) == 1
    zone = tree[0]
    assert zone["name"] == "Jaipur Zone 1"
    assert zone["type"] == "Zone"
    assert zone["meter_count"] == 1


def test_dashboard_ui_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "Urja Meter Ops" in response.text
    assert "text/html" in response.headers["content-type"]
