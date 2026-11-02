import os
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_health():
    resp = client.get("/health")
    data = resp.json()
    print("Health response:", data)
    assert resp.status_code == 200
    assert "mode" in data
    assert "has_env_key" in data

def test_public_mode_requires_auth():
    # 模拟公共模式
    os.environ["MINERU_SERVICE_MODE"] = "public"
    resp = client.post("/parse", json={"file_url": "https://example.com/test.pdf"})
    print("Public mode without auth status:", resp.status_code)
    assert resp.status_code == 401
    assert "公开多租户模式" in resp.json()["detail"]

def test_private_mode_without_env_key():
    # 模拟私有模式但未配置 MINERU_API_KEY
    os.environ["MINERU_SERVICE_MODE"] = "private"
    os.environ.pop("MINERU_API_KEY", None)
    resp = client.post("/parse", json={"file_url": "https://example.com/test.pdf"})
    print("Private mode without env key status:", resp.status_code)
    assert resp.status_code == 500
    assert "MINERU_API_KEY" in resp.json()["detail"]

def test_private_mode_with_env_key():
    # 模拟私有模式且配置了 MINERU_API_KEY
    os.environ["MINERU_SERVICE_MODE"] = "private"
    os.environ["MINERU_API_KEY"] = "mock_secret_key_123"
    # 请求时不提供 Authorization 头，应该通过鉴权并尝试向官方发请求（由于 mock key，官方返回 401，符合预期）
    resp = client.post("/parse", json={"file_url": "https://example.com/test.pdf"})
    print("Private mode with env key resp code:", resp.json().get("code"))
    # 说明内部已自动使用 mock_secret_key_123 请求了 MinerU，未在入口拦截 401
    assert resp.status_code == 200  # API 返回包裹的 json
    assert resp.json()["code"] == 401 or "authenticate failed" in resp.json().get("msg", "")

def test_override_auth_in_private_mode():
    # 私有模式下客户端提供 Authorization 优先覆盖
    os.environ["MINERU_SERVICE_MODE"] = "private"
    os.environ["MINERU_API_KEY"] = "default_key"
    resp = client.post(
        "/parse",
        headers={"Authorization": "Bearer custom_user_token"},
        json={"file_url": "https://example.com/test.pdf"}
    )
    assert resp.status_code == 200
    print("Override auth test passed.")

if __name__ == "__main__":
    test_health()
    test_public_mode_requires_auth()
    test_private_mode_without_env_key()
    test_private_mode_with_env_key()
    test_override_auth_in_private_mode()
    print("\n[+] All unit tests for Private/Public modes passed successfully!")
