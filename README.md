# MinerU 官方云端解析 FastAPI 请求套件

本项目基于 [MinerU 官方精准解析 API 文档](https://mineru.net/apiManage/docs)，使用 **FastAPI** 封装了一个开箱即用的高性能异步解析服务。

无需在本地安装笨重的 PyTorch、大模型权重或依赖本地昂贵的显卡算力，只需配置 MinerU 官方的 API Key，即可直接将任何远程文档（PDF、Word、PPT、Excel、图片、HTML等）解析转换为高质量 Markdown！

---

## 一、 功能特性

1. **双模式支持（私有模式 / 公开模式）**：
   - **私有模式（Private Mode，默认）**：服务端默认读取环境变量或 `.env` 中的 `MINERU_API_KEY`，客户端调用时**无需传递 Authorization 请求头**，随调随用；如果客户端传递了 Token，则优先使用客户端指定的 Token 覆盖。
   - **公开多租户模式（Public Mode）**：严格要求每个调用方在请求头中传入各自独立的 MinerU API Key，适合多用户/对外共享部署。
2. **零本地算力依赖**：纯轻量服务，所有大模型抽取与版面计算全部在 MinerU 官方云端集群完成。
3. **一步式调用体验**：对外提供简单的单步阻塞/即时接口，内部自动执行：
   - 提交任务 (`POST /api/v4/extract/task`)
   - 异步轮询解析进度直至完成 (`GET /api/v4/extract/task/{task_id}`)
   - 内存流式解压结果 ZIP 并提取 `full.md`（无需写入磁盘临时文件，极致性能）
4. **标准化输入输出**：
   - **请求参数**：输入 `"file_url"`。
   - **响应格式**：返回 `"code"` 状态码与 `"content"`（解析提取出的 Markdown 正文）。
5. **智能格式推断**：针对 `.html` 格式自动匹配 `MinerU-HTML` 模型，其他文档默认使用高精度的 `vlm` 视觉大模型。

---

## 二、 目录结构

```text
mineru_fastapi_service/
├── app.py              # FastAPI 核心服务代码（支持私有/公开双模式）
├── requirements.txt    # 依赖包列表
├── .env.example        # 环境变量模板配置
├── test_client.py      # 客户端测试调用脚本
├── test_unit.py        # 单元测试用例
├── run.bat             # Windows CMD 一键启动脚本
├── run.ps1             # Windows PowerShell 启动脚本
└── README.md           # 使用说明文档
```

---

## 三、 配置与启动

### 1. 配置文件（私有模式必备）
复制根目录的 `.env.example` 并重命名为 `.env`：
```env
# 运行模式：private（私有模式，默认） | public（公开多租户模式）
MINERU_SERVICE_MODE=private

# MinerU 官方 API Token（在 https://mineru.net/apiManage/docs 创建）
MINERU_API_KEY=your_mineru_api_key_here
```

### 2. 一键启动
- **Windows (PowerShell)**：
  ```powershell
  .\run.ps1
  ```
- **Windows (CMD)**：
  ```cmd
  run.bat
  ```

### 3. 手动启动
```bash
# 1. 创建并激活虚拟环境 (推荐 uv 或 venv)
uv venv .venv --python 3.12
.\.venv\Scripts\activate

# 2. 安装依赖
uv pip install -r requirements.txt

# 3. 启动服务
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

启动成功后，浏览器访问即可查看自动生成的 Swagger 交互式文档：
👉 **http://127.0.0.1:8000/docs**

---

## 四、 接口文档说明

### 核心解析接口：`POST /parse`

#### 请求头 (Headers)
| 键名 | 必填 | 示例 | 说明 |
| :--- | :---: | :--- | :--- |
| `Authorization` | 条件必填 | `Bearer YOUR_TOKEN` | • **私有模式**：**可选**（不传时自动使用服务端的 `MINERU_API_KEY`）<br>• **公开模式**：**必填**（客户端必须各自提供 Token） |
| `Content-Type` | 是 | `application/json` | 数据传输格式 |

#### 请求体 (JSON Body)
```json
{
  "file_url": "https://cdn-mineru.openxlab.org.cn/demo/example.pdf",
  "is_ocr": false,
  "enable_formula": true,
  "enable_table": true,
  "poll_timeout": 300
}
```

- **参数说明**：
  - `file_url`（必填，字符串）：待解析的文件公网直链。支持 `.pdf`, `.doc`, `.docx`, `.ppt`, `.pptx`, `.xls`, `.xlsx`, 图片(`.png`/`.jpg`等), `.html` 等。
  - `model_version`（可选，字符串）：默认自动推断（`vlm`、`pipeline` 或 `MinerU-HTML`）。
  - `is_ocr`（可选，布尔）：是否启用 OCR，默认 `false`。
  - `enable_formula`（可选，布尔）：是否识别公式为 LaTeX，默认 `true`。
  - `enable_table`（可选，布尔）：是否识别表格为 HTML，默认 `true`。
  - `poll_timeout`（可选，整数）：最长轮询等待时间，默认 `300` 秒。

#### 响应结构 (JSON Response)
```json
{
  "code": 200,
  "content": "# 文档标题\n\n这是解析提取出来的 Markdown 内容...\n",
  "msg": "ok",
  "task_id": "a90e6ab6-44f3-4554-b459-b62fe4c6b436",
  "trace_id": "c876cd60b202f2396de1f9e39a1b0172"
}
```

---

## 五、 调用示例

### 1. 私有模式调用（最简调用，无需传 Authorization）
```bash
curl --location --request POST 'http://127.0.0.1:8000/parse' \
--header 'Content-Type: application/json' \
--data-raw '{
    "file_url": "https://cdn-mineru.openxlab.org.cn/demo/example.pdf"
}'
```

```python
import requests

resp = requests.post(
    "http://127.0.0.1:8000/parse",
    json={"file_url": "https://cdn-mineru.openxlab.org.cn/demo/example.pdf"}
)
data = resp.json()
print("Code:", data["code"])
print("Markdown:\n", data["content"])
```

### 2. 公开模式 / 指定自定义 Token 调用
```bash
curl --location --request POST 'http://127.0.0.1:8000/parse' \
--header 'Authorization: Bearer YOUR_MINERU_API_KEY' \
--header 'Content-Type: application/json' \
--data-raw '{
    "file_url": "https://cdn-mineru.openxlab.org.cn/demo/example.pdf"
}'
```

### 3. 使用内置测试客户端 `test_client.py`
```bash
# 私有模式下直接运行
python test_client.py --url "https://cdn-mineru.openxlab.org.cn/demo/example.pdf"

# 或指定 Token 运行
python test_client.py --token "YOUR_API_KEY" --output "result.md"
```
