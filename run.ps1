# PowerShell 启动脚本
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "       MinerU 官方云端解析 FastAPI 服务启动脚本" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[!] 检测到未创建虚拟环境，正在通过 uv 创建..." -ForegroundColor Yellow
    uv venv .venv --python 3.12
    Write-Host "[!] 正在安装依赖包..." -ForegroundColor Yellow
    uv pip install -r requirements.txt
}

Write-Host "[*] 正在启动 FastAPI 服务 (http://127.0.0.1:8000)..." -ForegroundColor Green
Write-Host "[*] 在线交互文档地址: http://127.0.0.1:8000/docs" -ForegroundColor Green
& ".venv\Scripts\uvicorn.exe" app:app --host 0.0.0.0 --port 8000 --reload
