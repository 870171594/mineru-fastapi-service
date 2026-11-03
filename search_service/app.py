"""Standalone AgentArts search relay using Zhipu Web Search API."""
import os
from pathlib import Path
from typing import Literal

import httpx
from dotenv import dotenv_values
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

UPSTREAM_URL = "https://open.bigmodel.cn/api/paas/v4/web_search"
KEY_FILE = Path(__file__).with_name(".env")
app = FastAPI(
    title="AgentArts 智谱联网搜索",
    version="1.0.0",
    docs_url="/search/docs",
    openapi_url="/search/openapi.json",
    redoc_url=None,
)


def get_api_key():
    return (os.getenv("ZHIPU_API_KEY") or dotenv_values(KEY_FILE).get("ZHIPU_API_KEY") or "").strip()


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
    return {"status": "ok", "service": "agentarts-search", "provider": "zhipu", "has_env_key": bool(get_api_key())}


@app.post("/search", response_model=SearchResponse, summary="智谱联网搜索")
async def search(request: SearchRequest):
    query = request.query.strip()
    if not query:
        raise HTTPException(422, detail="query 不能为空")
    key = get_api_key()
    if not key:
        raise HTTPException(503, detail="服务端尚未配置 ZHIPU_API_KEY")
    token = key if key.lower().startswith("bearer ") else "Bearer " + key
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
            response = await client.post(UPSTREAM_URL, headers={"Authorization": token}, json=payload)
    except httpx.TimeoutException:
        raise HTTPException(504, detail="智谱搜索请求超时，请稍后重试") from None
    except httpx.RequestError:
        raise HTTPException(502, detail="无法连接智谱搜索服务") from None
    if response.status_code == 429:
        raise HTTPException(429, detail="智谱搜索频率或并发超限，请稍后重试")
    if response.status_code in (401, 403):
        raise HTTPException(502, detail="智谱认证或权限校验失败，请检查服务器 Key 和搜索服务权限")
    if not response.is_success:
        raise HTTPException(502, detail="智谱搜索请求失败，请检查账户余额、权限和请求参数")
    try:
        data = response.json()
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
        return SearchResponse(query=query, search_engine=request.search_engine, count=len(results), results=results, request_id=data.get("request_id") or data.get("id"))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(502, detail="智谱返回异常数据，未生成搜索结果") from None
