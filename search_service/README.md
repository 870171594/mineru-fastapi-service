# AgentArts 智谱联网搜索服务

基于 FastAPI 封装智谱官方 [Web Search API](https://docs.bigmodel.cn/cn/guide/tools/web-search)，供 AgentArts 工作流调用。服务独立运行，不修改 MinerU 解析接口。

## API

`POST /search`

请求必须携带 `Authorization: Bearer <调用者的智谱APIKEY>`，也兼容纯 Key。每位插件使用者配置自己的 Key，服务不会回退使用服务器环境变量或 `.env`。未传时返回 `401` 和 `请传入鉴权信息：智谱 APIKEY`。

响应头 `X-Auth-Source: client` 表示已收到客户端凭证（不表示智谱已认证通过）；`missing` 表示未收到。服务日志只记录凭证是否收到，不记录 Key。

```json
{
  "query": "大学生创新创业比赛评审规则",
  "max_results": 5,
  "search_engine": "search_std",
  "search_recency_filter": "noLimit",
  "content_size": "medium"
}
```

`query` 为必填，最多 70 个字符。`max_results` 范围为 1–50。搜索引擎可选 `search_std`（默认）或 `search_pro`。可选提供 `search_domain_filter`。

统一响应示例：

```json
{
  "query": "大学生创新创业比赛评审规则",
  "search_engine": "search_std",
  "count": 1,
  "results": [
    {
      "title": "赛事通知",
      "url": "https://example.com/notice",
      "snippet": "网页摘要",
      "site_name": "赛事官网",
      "publish_date": "2026-01-01",
      "reference": "ref_1"
    }
  ],
  "request_id": "request-id"
}
```

`GET /search/health` 返回服务状态和 `auth_mode: client`。Swagger 文档位于 `/search/docs`。`401` 表示缺少凭证或智谱拒绝凭证，`429` 表示上游限流，`502`/`504` 表示上游失败或超时；不会把上游错误伪装成空搜索结果。

## 本地运行

```bash
cd search_service
python -m venv .venv
.venv/bin/pip install -r requirements.txt
# API Key 由调用者通过 Authorization 请求头提供
.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8100
```

Windows 虚拟环境可使用 `.venv\Scripts\pip` 和 `.venv\Scripts\uvicorn`。

## systemd 部署示例

部署到 `/opt/agentarts-search`，并创建专用系统账号 `agentarts-search`。依赖建议放在专用虚拟环境中。

```ini
[Unit]
Description=AgentArts Zhipu web search relay
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=agentarts-search
Group=agentarts-search
WorkingDirectory=/opt/agentarts-search
ExecStart=/opt/agentarts-search/.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8100 --workers 2 --no-access-log --limit-concurrency 32
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
UMask=0077
```

无需在服务器配置智谱 Key。请勿将调用者的真实密钥写入日志或提交到 Git。

HTTPS Nginx 反代示例（把 `location` 放到现有 TLS server 内；按需与已有路径规则合并）：

```nginx
location = /search {
    limit_req zone=agentarts_search_limit burst=5 nodelay;
    limit_req_status 429;
    proxy_pass http://127.0.0.1:8100/search;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_read_timeout 60s;
}

location /search/ {
    proxy_pass http://127.0.0.1:8100;
    proxy_set_header Host $host;
    proxy_read_timeout 60s;
}
```

`limit_req_zone $binary_remote_addr zone=agentarts_search_limit:10m rate=10r/m;` 需定义在 Nginx `http` 块中。若接口暴露公网，建议再加调用方认证、来源 IP 限制或 API Gateway 保护；限流只能降低误用风险，不能替代认证。

## 测试

```bash
python -m pip install -r requirements.txt
python -m pip install pytest
python -m pytest search_service/test_app.py -q
```

测试使用本地模拟上游响应，不会消耗智谱搜索额度。
