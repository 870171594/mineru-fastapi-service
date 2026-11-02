"""
MinerU 官方在线 API FastAPI 请求套件
文档依据: https://mineru.net/apiManage/docs (精准解析 - 单文件解析)
支持模式:
1. 私有模式 (private, 默认): 默认直接使用服务端环境变量/ .env 中的 MINERU_API_KEY，客户端无需在请求头传入 Authorization
2. 公开模式 (public): 严格要求客户端在请求头传入各自分配的 MinerU Authorization Token
"""

import asyncio
import io
import logging
import os
import time
import zipfile
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# 优先加载本地 .env 文件
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("mineru-service")

# 读取服务模式与初始环境配置
DEFAULT_SERVICE_MODE = os.getenv("MINERU_SERVICE_MODE", "private").strip().lower()
logger.info("MinerU 服务启动中... 运行模式: [%s]", DEFAULT_SERVICE_MODE)

app = FastAPI(
    title="MinerU 官方云端解析 FastAPI 服务",
    description="免本地安装大模型与 GPU，直接调用 MinerU 官方云端 API 解析单文件并返回 Markdown 内容。支持私有模式与公开模式",
    version="1.1.0"
)

# 允许跨域（方便前端或 Agent 调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 官方 API 地址
MINERU_BASE_URL = "https://mineru.net/api/v4"
EXTRACT_TASK_URL = f"{MINERU_BASE_URL}/extract/task"


class ParseRequest(BaseModel):
    file_url: str = Field(..., description="待解析的文件 URL，支持 PDF、Word、PPT、Excel、图片、HTML 等格式")
    model_version: Optional[str] = Field(
        default=None,
        description="模型版本：vlm（推荐，高精度视觉大模型）、pipeline（经典流水线）或 MinerU-HTML（html专属）。默认自动推断"
    )
    is_ocr: Optional[bool] = Field(default=False, description="是否启用 OCR 功能（主要对扫描件有效）")
    enable_formula: Optional[bool] = Field(default=True, description="是否开启数学公式识别")
    enable_table: Optional[bool] = Field(default=True, description="是否开启表格结构识别")
    language: Optional[str] = Field(default="ch", description="文档语言代码，默认 ch (中英)")
    poll_timeout: Optional[int] = Field(default=300, description="任务轮询最大等待时间（秒），默认 300 秒")
    poll_interval: Optional[float] = Field(default=2.0, description="轮询间隔（秒），默认 2.0 秒")


class ParseResponse(BaseModel):
    code: int = Field(..., description="状态码，200 为成功，其他为错误码")
    content: str = Field(..., description="解析提取出的完整 Markdown 内容（失败时为错误描述）")
    msg: Optional[str] = Field(default="ok", description="详细提示信息")
    task_id: Optional[str] = Field(default=None, description="官方 MinerU 解析任务 ID")
    trace_id: Optional[str] = Field(default=None, description="请求跟踪 ID")


def resolve_auth_token(auth_header: Optional[str]) -> str:
    """
    鉴权凭证解析策略：
    1. 若请求头中携带了 Authorization（且非空），优先使用客户端传入的 Token（支持 Bearer 或纯 Token）；
    2. 若请求头未携带 Authorization：
       - 私有模式 (private, 默认)：自动读取环境变量/ .env 中的 MINERU_API_KEY；
       - 公开模式 (public)：抛出 401 Unauthorized 异常，强制客户端自行传参。
    """
    # 客户端显式传递了 Token，直接使用
    if auth_header and auth_header.strip():
        token = auth_header.strip()
        if not token.lower().startswith("bearer "):
            return f"Bearer {token}"
        return token

    # 未传递 Token 时，根据运行模式判断
    mode = os.getenv("MINERU_SERVICE_MODE", "private").strip().lower()

    if mode == "private":
        env_key = os.getenv("MINERU_API_KEY", "").strip()
        if not env_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="当前处于 [私有模式 (private)]，但未在服务端环境变量或 .env 中设置 MINERU_API_KEY。请先配置该环境变量，或在请求头中传入 Authorization。"
            )
        if not env_key.lower().startswith("bearer "):
            return f"Bearer {env_key}"
        return env_key

    # 公开模式：强制要求客户端提供
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="当前处于 [公开多租户模式 (public)]，必须在请求头中传入 Authorization: Bearer <YOUR_API_KEY>。"
    )


def determine_model_version(file_url: str, custom_model: Optional[str]) -> str:
    """根据文件 URL 后缀智能推断适用的模型版本"""
    if custom_model:
        return custom_model
    url_lower = file_url.lower().split("?")[0]
    if url_lower.endswith(".html") or url_lower.endswith(".htm"):
        return "MinerU-HTML"
    return "vlm"


async def fetch_markdown_from_zip(zip_url: str, client: httpx.AsyncClient) -> str:
    """从官方生成的 zip 结果包中直接在内存中提取 full.md 内容"""
    logger.info("正在下载解析结果 ZIP: %s", zip_url)
    resp = await client.get(zip_url, timeout=60.0)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        namelist = z.namelist()
        logger.info("ZIP 包含文件列表: %s", namelist)

        # 优先寻找 full.md
        target_name = None
        for name in namelist:
            if name.endswith("full.md") or name == "full.md":
                target_name = name
                break

        # 兼容备选：如果找不到 full.md，取任意 .md 文件
        if not target_name:
            for name in namelist:
                if name.endswith(".md"):
                    target_name = name
                    break

        if not target_name:
            raise ValueError(f"解析结果 ZIP 包内未找到 Markdown 文件，文件列表为: {namelist}")

        content_bytes = z.read(target_name)
        return content_bytes.decode("utf-8", errors="replace")


@app.post("/parse", response_model=ParseResponse, summary="解析单文件并直接返回 Markdown 内容")
@app.get("/parse", response_model=ParseResponse, summary="解析单文件 (GET 快捷调用)")
async def parse_single_file(
    request_data: Optional[ParseRequest] = None,
    file_url: Optional[str] = Query(None, description="待解析的文件 URL (兼容 GET/Query 参数)"),
    authorization: Optional[str] = Header(None, alias="Authorization", description="MinerU 官方 API Key (私有模式下可选，公共模式下必填)")
):
    """
    单文件精准解析接口：
    1. 解析鉴权凭证（私有模式自动使用环境 MINERU_API_KEY，公开模式强制要求传入）；
    2. 向 MinerU 官方接口提交任务；
    3. 异步轮询任务状态直至完成；
    4. 内存流式解压并返回解析出的 Markdown 文本内容。
    """
    # 兼容 JSON Body 与 Query 参数
    target_url = None
    model_version = None
    is_ocr = False
    enable_formula = True
    enable_table = True
    language = "ch"
    poll_timeout = 300
    poll_interval = 2.0

    if request_data:
        target_url = request_data.file_url
        model_version = request_data.model_version
        is_ocr = request_data.is_ocr or False
        enable_formula = request_data.enable_formula if request_data.enable_formula is not None else True
        enable_table = request_data.enable_table if request_data.enable_table is not None else True
        language = request_data.language or "ch"
        poll_timeout = request_data.poll_timeout or 300
        poll_interval = request_data.poll_interval or 2.0
    elif file_url:
        target_url = file_url

    if not target_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少必填参数 'file_url'。"
        )

    # 确定最终使用的 API Key Token
    auth_token = resolve_auth_token(authorization)
    selected_model = determine_model_version(target_url, model_version)

    headers = {
        "Content-Type": "application/json",
        "Authorization": auth_token,
        "Accept": "*/*"
    }

    payload = {
        "url": target_url,
        "model_version": selected_model,
        "is_ocr": is_ocr,
        "enable_formula": enable_formula,
        "enable_table": enable_table,
        "language": language
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 第一步：提交解析任务
        logger.info("向 MinerU 提交任务: URL=%s, model=%s", target_url, selected_model)
        try:
            submit_resp = await client.post(EXTRACT_TASK_URL, headers=headers, json=payload)
        except Exception as e:
            logger.error("请求 MinerU 任务接口失败: %s", e)
            return ParseResponse(code=500, content="", msg=f"连接 MinerU 官方接口失败: {str(e)}")

        if submit_resp.status_code != 200:
            logger.error("MinerU 接口 HTTP %s: %s", submit_resp.status_code, submit_resp.text)
            return ParseResponse(
                code=submit_resp.status_code,
                content="",
                msg=f"MinerU 任务创建失败 (HTTP {submit_resp.status_code}): {submit_resp.text}"
            )

        submit_data = submit_resp.json()
        if submit_data.get("code") != 0:
            logger.error("MinerU 业务错误: %s", submit_data)
            return ParseResponse(
                code=submit_data.get("code", 500),
                content="",
                msg=f"MinerU 返回错误: {submit_data.get('msg', '未知错误')}",
                trace_id=submit_data.get("trace_id")
            )

        task_id = submit_data.get("data", {}).get("task_id")
        trace_id = submit_data.get("trace_id")
        if not task_id:
            return ParseResponse(
                code=500,
                content="",
                msg="未能获取到 task_id",
                trace_id=trace_id
            )

        logger.info("任务创建成功, task_id: %s, 开始轮询...", task_id)

        # 第二步：轮询任务状态
        query_url = f"{EXTRACT_TASK_URL}/{task_id}"
        start_time = time.time()
        full_zip_url = None

        while True:
            elapsed = time.time() - start_time
            if elapsed > poll_timeout:
                logger.warning("任务轮询超时: %s 秒", poll_timeout)
                return ParseResponse(
                    code=504,
                    content="",
                    msg=f"解析任务超时（超过 {poll_timeout} 秒）。任务仍在官方服务端执行中，task_id: {task_id}",
                    task_id=task_id,
                    trace_id=trace_id
                )

            await asyncio.sleep(poll_interval)

            try:
                query_resp = await client.get(query_url, headers=headers, timeout=15.0)
            except Exception as e:
                logger.warning("轮询任务网络异常（将重试）: %s", e)
                continue

            if query_resp.status_code != 200:
                logger.warning("轮询接口返回 HTTP %s: %s", query_resp.status_code, query_resp.text)
                continue

            res_json = query_resp.json()
            data = res_json.get("data", {})
            state = data.get("state")
            logger.info("任务状态轮询 [%s]: state=%s, 已用时=%.1fs", task_id, state, elapsed)

            if state == "done":
                full_zip_url = data.get("full_zip_url")
                if not full_zip_url:
                    return ParseResponse(
                        code=500,
                        content="",
                        msg="任务状态标记为完成，但未返回 full_zip_url 下载链接",
                        task_id=task_id,
                        trace_id=trace_id
                    )
                break
            elif state == "failed":
                err_msg = data.get("err_msg", "未知错误")
                logger.error("解析任务失败: %s", err_msg)
                return ParseResponse(
                    code=500,
                    content="",
                    msg=f"官方服务端解析失败: {err_msg}",
                    task_id=task_id,
                    trace_id=trace_id
                )
            elif state in ("pending", "running", "converting"):
                # 仍在处理中，继续下一次循环
                continue
            else:
                logger.warning("未知的任务状态: %s", state)

        # 第三步：从 ZIP 中提取 Markdown
        try:
            markdown_content = await fetch_markdown_from_zip(full_zip_url, client)
            logger.info("成功获取 Markdown 内容，长度: %d 字符", len(markdown_content))
            return ParseResponse(
                code=200,
                content=markdown_content,
                msg="ok",
                task_id=task_id,
                trace_id=trace_id
            )
        except Exception as e:
            logger.error("下载或解压结果 ZIP 失败: %s", e)
            return ParseResponse(
                code=500,
                content="",
                msg=f"下载或解压解析结果失败: {str(e)}",
                task_id=task_id,
                trace_id=trace_id
            )


@app.get("/health", summary="健康检查与运行模式")
async def health_check():
    """返回当前服务健康状态、运行模式与环境变量凭证配置情况"""
    mode = os.getenv("MINERU_SERVICE_MODE", "private").strip().lower()
    has_key = bool(os.getenv("MINERU_API_KEY", "").strip())
    return {
        "status": "ok",
        "service": "mineru-fastapi-service",
        "mode": mode,
        "has_env_key": has_key
    }
