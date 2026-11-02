"""
MinerU FastAPI 服务测试客户端示例
运行前请确保:
1. FastAPI 服务已在本地启动: uvicorn app:app --host 0.0.0.0 --port 8000
2. 准备好您的官方 MinerU API Token (可在 https://mineru.net/apiManage/docs 获取)
"""

import argparse
import json
import os
import sys
import httpx

API_SERVER_URL = "http://127.0.0.1:8000/parse"
DEFAULT_TEST_PDF = "https://cdn-mineru.openxlab.org.cn/demo/example.pdf"


def main():
    parser = argparse.ArgumentParser(description="测试 MinerU FastAPI 单文件解析接口")
    parser.add_argument("--url", default=DEFAULT_TEST_PDF, help="待解析的文件 URL (默认官方 demo.pdf)")
    parser.add_argument("--token", default=os.getenv("MINERU_API_KEY"), help="官方 MinerU API Token (或读取环境变量 MINERU_API_KEY)")
    parser.add_argument("--server", default=API_SERVER_URL, help="FastAPI 服务接口地址")
    parser.add_argument("--output", default=None, help="将结果 Markdown 保存到文件")
    args = parser.parse_args()

    token = args.token
    if not token:
        print("[!] 警告: 未提供 MinerU API Token。")
        print("    请通过参数传入: python test_client.py --token <YOUR_TOKEN>")
        print("    或设置环境变量: export MINERU_API_KEY=<YOUR_TOKEN> (PowerShell: $env:MINERU_API_KEY='...')")
        token = input("请输入您的 MinerU API Token (直接回车退出): ").strip()
        if not token:
            sys.exit(1)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "file_url": args.url,
        "is_ocr": False,
        "enable_formula": True,
        "enable_table": True
    }

    print(f"[*] 正在向服务发送请求: {args.server}")
    print(f"[*] 目标文件 URL: {args.url}")
    print("[*] 正在等待服务端处理 (提交 ➔ 轮询 ➔ 解压)...")

    try:
        # 设置相对宽松的客户端超时时间
        with httpx.Client(timeout=360.0) as client:
            resp = client.post(args.server, headers=headers, json=payload)
            resp.raise_for_status()
            res = resp.json()

        print("\n" + "="*50)
        print(f"[+] 响应状态码 code: {res.get('code')}")
        print(f"[+] 任务 task_id: {res.get('task_id')}")
        print(f"[+] 消息 msg: {res.get('msg')}")
        print("="*50)

        markdown_content = res.get("content", "")
        if res.get("code") == 200:
            print(f"[+] 解析成功！Markdown 总长度: {len(markdown_content)} 字符")
            print("-" * 50)
            preview = markdown_content[:500]
            print("【Markdown 预览前 500 字】:\n")
            print(preview)
            if len(markdown_content) > 500:
                print("\n... (更多内容已截断)")

            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(markdown_content)
                print(f"\n[+] 完整 Markdown 已保存至: {args.output}")
        else:
            print(f"[-] 解析失败: {res.get('msg')}")

    except Exception as e:
        print(f"[-] 请求异常: {e}")


if __name__ == "__main__":
    main()
