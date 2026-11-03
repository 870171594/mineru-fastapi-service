"""Standalone AgentArts search relay using Zhipu Web Search API."""
import logging
from typing import Literal

import httpx
from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, Field

UPSTREAM_URL = "https://open.bigmodel.cn/api/paas/v4/web_search"
logger = logging.getLogger("uvicorn.error")
app = FastAPI(
    title="AgentArts 智谱联网搜索",
    version="1.0.0",
    docs_url="/search/docs",
    openapi_url="/search/openapi.json",
    redoc_url=None,
)


def resolve_auth_token(authorization: str | None) -> str:
    key = (authorization or "").strip()
    if key.lower() == "bearer":
        key = ""
    elif key.lower().startswith("bearer "):
        key = key[7:].strip()
    if not key:
        raise HTTPException(401, detail="请传入鉴权信息：智谱 APIKEY", headers={"WWW-Authenticate": "Bearer", "X-Auth-Source": "missing"})
    return "Bearer " + key


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=70, description="搜索词，最多70字符")
    max_results: int = Field(default=5, ge=1, le=50)
    search_engine: Literal["search_std", "search_pro"] = "search_std"
    search_domain_filter: str | None = Field(default=None, max_length=253, pattern=r"^[A-Za-z0-9.-]+$")
    search_recency_filter: Literal["noLimit", "oneDay", "oneWeek", "oneMonth", "oneYear"] = "noLimit"
    content_size: Literal["medium", "high"] = "medium"


class SearchResult(BaseModel):
    title: str = ""
    url: str = ""
    snippet: str = ""
    site_name: str = ""
    publish_date: str = ""
    reference: str = ""


class SearchResponse(BaseModel):
    query: str
    search_engine: str
    count: int
    results: list[SearchResult]
    request_id: str | None = None


@app.get("/search/health")
def health():
    return {"status": "ok", "service": "agentarts-search", "provider": "zhipu", "auth_mode": "client", "auth_header": "Authorization"}


@app.post("/search", response_model=SearchResponse, summary="智谱联网搜索")
async def search(request: SearchRequest, response: Response, authorization: str | None = Header(default=None, description="调用者的智谱 API Key，支持 Bearer 前缀或纯 Key")):
    token = resolve_auth_token(authorization)
    auth_headers = {"X-Auth-Source": "client"}
    logger.info("Search request: Authorization received; credential source=client")
    query = request.query.strip()
    if not query:
        raise HTTPException(422, detail="query 不能为空")
    payload = {
        "search_query": query,
        "search_engine": request.search_engine,
        "search_intent": False,
        "count": request.max_results,
        "search_recency_filter": request.search_recency_filter,
        "content_size": request.content_size,
    }
    if request.search_domain_filter:
        payload["search_domain_filter"] = request.search_domain_filter
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(35.0, connect=8.0)) as client:
            upstream = await client.post(UPSTREAM_URL, headers={"Authorization": token}, json=payload)
    except httpx.TimeoutException:
        raise HTTPException(504, detail="智谱搜索请求超时，请稍后重试", headers=auth_headers) from None
    except httpx.RequestError:
        raise HTTPException(502, detail="无法连接智谱搜索服务", headers=auth_headers) from None
    if upstream.status_code == 429:
        raise HTTPException(429, detail="智谱搜索频率或并发超限，请稍后重试", headers=auth_headers)
    if upstream.status_code in (401, 403):
        raise HTTPException(401, detail="已收到 Authorization，但智谱认证或权限校验失败，请检查传入的 APIKEY 和搜索服务权限", headers=auth_headers)
    if not upstream.is_success:
        raise HTTPException(502, detail="已收到 Authorization，智谱搜索请求失败，请检查账户余额、权限和请求参数", headers=auth_headers)
    try:
        data = upstream.json()
        if not isinstance(data, dict) or data.get("error") or not isinstance(data.get("search_result"), list):
            raise ValueError()
        results = [
            SearchResult(
                title=item.get("title") or "",
                url=item.get("link") or "",
                snippet=item.get("content") or "",
                site_name=item.get("media") or "",
                publish_date=item.get("publish_date") or "",
                reference=item.get("refer") or "",
            )
            for item in data["search_result"][:request.max_results]
        ]
        response.headers["X-Auth-Source"] = "client"
        return SearchResponse(query=query, search_engine=request.search_engine, count=len(results), results=results, request_id=data.get("request_id") or data.get("id"))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(502, detail="智谱返回异常数据，未生成搜索结果", headers=auth_headers) from None
