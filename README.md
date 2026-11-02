# MinerU 官方云端解析 FastAPI 请求套件

本项目基于 [MinerU 官方精准解析 API 文档](https://mineru.net/apiManage/docs)，使用 **FastAPI** 封装了一个开箱即用的高性能异步解析服务。

无需在本地安装笨重的 PyTorch、大模型权重或依赖本地昂贵的显卡算力，只需配置 MinerU 官方的 API Key，即可直接将任何远程文档（PDF、Word、PPT、Excel、图片、HTML等）解析转换为高质量 Markdown！

---

## 一、 功能特性

1. **零本地算力依赖**：纯轻量服务，所有大模型抽取与版面计算全部在 MinerU 官方云端集群完成。
2. **一步式调用体验**：对外提供简单的单步阻塞/即时接口，内部自动执行：
   - 提交任务 (`POST /api/v4/extract/task`)
   - 异步轮询解析进度直至完成 (`GET /api/v4/extract/task/{task_id}`)
   - 内存流式解压结果 ZIP 并提取 `full.md`（无需写入磁盘临时文件，极致性能）
3. **标准化输入输出**：
   - **请求头**：`Authorization` 携带 MinerU API Key（自动兼容 `Bearer xxx` 或纯 `xxx`）。
   - **请求参数**：输入 `"file_url"`。
   - **响应格式**：返回 `"code"` 与 `"content"`（解析提取出的 Markdown 正文）。
4. **智能格式推断**：针对 `.html` 格式自动匹配 `MinerU-HTML` 模型，其他文档默认使用高精度的 `vlm` 视觉大模型。

---

## 二、 目录结构

```text
mineru_fastapi_service/
├── app.py              # FastAPI 核心服务代码
├── requirements.txt    # 依赖包列表
├── test_client.py      # 客户端测试调用脚本
├── test_unit.py        # 单元测试用例
├── run.bat             # Windows CMD 一键启动脚本
├── run.ps1             # Windows PowerShell 启动脚本
└── README.md           # 使用说明文档
```

---

## 三、 快速启动

### 方式 1：使用提供的脚本一键启动（推荐）
- **Windows (PowerShell)**：
  ```powershell
  .\run.ps1
  ```
- **Windows (CMD)**：
  ```cmd
  run.bat
  ```

### 方式 2：手动启动
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

### 1. 核心解析接口：`POST /parse`

#### 请求头 (Headers)
| 键名 | 必填 | 示例 | 说明 |
| :--- | :---: | :--- | :--- |
| `Authorization` | 是 | `Bearer YOUR_MINERU_API_KEY` | 官方 MinerU API Token（在 mineru.net 获取） |
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

### 1. cURL 示例
```bash
curl --location --request POST 'http://127.0.0.1:8000/parse' \
--header 'Authorization: Bearer YOUR_MINERU_API_KEY' \
--header 'Content-Type: application/json' \
--data-raw '{
    "file_url": "https://cdn-mineru.openxlab.org.cn/demo/example.pdf"
}'
```

### 2. Python 示例
```python
import requests

url = "http://127.0.0.1:8000/parse"
headers = {
    "Authorization": "Bearer YOUR_MINERU_API_KEY",
    "Content-Type": "application/json"
}
payload = {
    "file_url": "https://cdn-mineru.openxlab.org.cn/demo/example.pdf"
}

response = requests.post(url, headers=headers, json=payload, timeout=360)
data = response.json()

if data.get("code") == 200:
    markdown = data.get("content")
    print("解析成功，Markdown 内容如下：\n")
    print(markdown[:500])
else:
    print(f"解析失败: {data.get('msg')}")
```

### 3. 使用内置测试客户端 `test_client.py`
```bash
python test_client.py --token "YOUR_MINERU_API_KEY" --url "https://cdn-mineru.openxlab.org.cn/demo/example.pdf" --output "result.md"
```
