import pytest
from fastapi.testclient import TestClient

from backend import db as database
from backend.app import ATTEMPTS, app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATA", tmp_path)
    ATTEMPTS.clear()
    with TestClient(app) as client:
        yield client


def request(client, method, url, body=None, **kwargs):
    return client.request(method, url, json=body, **kwargs)


def authenticate(client, username="admin", password="ClaveSeguraPrueba123!"):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    client.headers["x-csrf-token"] = response.json()["csrf"]
    return response.json()["user"]


@pytest.fixture
def admin_client(client):
    result = client.post(
        "/api/setup",
        json={
            "username": "admin",
            "full_name": "Administrador de prueba",
            "password": "ClaveSeguraPrueba123!",
        },
    )
    assert result.status_code == 200, result.text
    authenticate(client)
    return client


def create(client, url, body):
    response = client.post(url, json=body)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def portfolio(admin_client):
    c = admin_client
    entity = create(c, "/api/entities", {"name": "Lotificadora A", "currency": "HNL"})
    client = create(
        c,
        f"/api/entities/{entity['id']}/clients",
        {
            "name": "Cliente sintético",
            "document_type": "DNI",
            "document": "SINTETICO-001",
            "phone": "00000000",
        },
    )
    lot = create(
        c,
        f"/api/entities/{entity['id']}/lots",
        {"code": "A-01", "price": "100000", "currency": "HNL"},
    )
    sale = create(
        c,
        f"/api/entities/{entity['id']}/contracts",
        {
            "lot_id": lot["id"],
            "client_id": client["id"],
            "price": "100000",
            "currency": "HNL",
            "down_payment": "10000",
            "installments": 12,
            "down_due": "2026-01-31",
            "first_due": "2026-01-31",
        },
    )
    return c, entity, client, lot, sale
