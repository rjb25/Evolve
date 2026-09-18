from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.app import app

WEB_ROOT = Path(__file__).resolve().parent.parent / "web"


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _assert_manifest(response):
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    body = response.json()
    assert body["solfray_playable"] == 1
    assert isinstance(body["solfray_playable"], int)
    assert body["name"] == "Evolution"
    assert body["description"] == (
        "Ten survivors, three goods, produce / deal / relate. "
        "Python sim; you are one body in the population."
    )
    assert body["aspect"] == "4:3"
    assert body["start_url"] == "/Evolution/"
    assert body["players"] == {"min": 1, "max": 10}
    assert body["version"] == "1.0.0"
    assert body["author"] == "Evolve"
    assert body["tags"] == ["survival", "multiplayer", "sim"]
    assert "image" not in body
    assert "owner" not in body
    csp = response.headers.get("content-security-policy", "")
    assert "frame-ancestors https://solfray.com" in csp
    assert "no-cache" in response.headers.get("cache-control", "")
    assert len(response.content) < 16 * 1024
    return body


def test_evolution_json_manifest(client):
    _assert_manifest(client.get("/Evolution.json"))


def test_directory_fallback_same_body(client):
    primary = client.get("/Evolution.json")
    fallback = client.get("/Evolution/solfray-playable.json")
    assert fallback.json() == primary.json()
    _assert_manifest(fallback)


def test_lowercase_evolution_json(client):
    _assert_manifest(client.get("/evolution.json"))


def test_index_has_framing_headers(client):
    response = client.get("/Evolution/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "frame-ancestors https://solfray.com" in response.headers.get(
        "content-security-policy", ""
    )
    assert "no-cache" in response.headers.get("cache-control", "")
    assert response.headers.get("x-frame-options") != "DENY"


def test_root_still_404(client):
    assert client.get("/").status_code == 404


def test_no_origin_root_playable(client):
    assert client.get("/solfray-playable.json").status_code == 404


def test_playable_file_is_source():
    path = WEB_ROOT / "solfray-playable.json"
    assert path.is_file()
    assert path.stat().st_size < 16 * 1024


def test_static_css_skips_framing_headers(client):
    response = client.get("/Evolution/static/css/app.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]
    assert "content-security-policy" not in response.headers
    assert "no-cache" not in response.headers.get("cache-control", "")
