import importlib

import httpx
import pytest
from fastapi.testclient import TestClient

search_app = importlib.import_module("search_service.app")
client = TestClient(search_app.app)


def test_health_does_not_expose_key(monkeypatch):
    monkeypatch.setattr(search_app, "get_api_key", lambda: "secret")
    response = client.get("/search/health")
    assert response.status_code == 200
    assert response.json()["has_env_key"] is True
    assert "secret" not in response.text


def test_missing_key_is_explicit(monkeypatch):
    monkeypatch.setattr(search_app, "get_api_key", lambda: "")
    response = client.post("/search", json={"query": "测试搜索"})
    assert response.status_code == 503
    assert "ZHIPU_API_KEY" in response.json()["detail"]


def test_invalid_query_and_bounds():
    for payload in ({"query": " "}, {"query": "x" * 71}, {"query": "test", "max_results": 51}):
        assert client.post("/search", json=payload).status_code == 422


def mock_upstream(monkeypatch, handler):
    original_client = httpx.AsyncClient
    monkeypatch.setattr(search_app, "get_api_key", lambda: "test-key")
    monkeypatch.setattr(search_app.httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))


def test_maps_official_response(monkeypatch):
    def handler(request):
        assert str(request.url) == search_app.UPSTREAM_URL
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(200, json={"id": "req-123", "search_result": [{"title": "标题", "link": "https://example.com", "content": "摘要", "media": "Example", "publish_date": "2026-01-01", "refer": "ref_1"}]})
    mock_upstream(monkeypatch, handler)
    response = client.post("/search", json={"query": "竞赛通知"})
    assert response.status_code == 200
    assert response.json()["results"][0] == {"title": "标题", "url": "https://example.com", "snippet": "摘要", "site_name": "Example", "publish_date": "2026-01-01", "reference": "ref_1"}
    assert response.json()["count"] == 1


@pytest.mark.parametrize("status, body, expected", [
    (401, {"error": {"message": "secret"}}, 502),
    (429, {}, 429),
    (500, {}, 502),
    (200, {"error": {"message": "secret"}}, 502),
    (200, {"search_result": "invalid"}, 502),
])
def test_upstream_errors_are_not_empty_success(monkeypatch, status, body, expected):
    mock_upstream(monkeypatch, lambda request: httpx.Response(status, json=body))
    response = client.post("/search", json={"query": "test"})
    assert response.status_code == expected
    assert "secret" not in response.text


def test_upstream_timeout(monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout("timeout", request=request)
    mock_upstream(monkeypatch, handler)
    assert client.post("/search", json={"query": "test"}).status_code == 504
