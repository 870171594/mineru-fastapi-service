@echo off
chcp 65001 >nul
echo ========================================================
echo        MinerU 官方云端解析 FastAPI 服务启动脚本
echo ========================================================

if not exist ".venv\Scripts\python.exe" (
    echo [!] 检测到未创建虚拟环境，正在通过 uv 创建...
    uv venv .venv --python 3.12
    echo [!] 正在安装依赖包...
    uv pip install -r requirements.txt
)

echo [*] 正在启动 FastAPI 服务 (http://127.0.0.1:8000)...
echo [*] Swagger 文档地址: http://127.0.0.1:8000/docs
.venv\Scripts\uvicorn.exe app:app --host 0.0.0.0 --port 8000 --reload
pause
