"""BlackTea 后端启动入口（Windows 兼容）。

必须在导入 uvicorn / app 之前、在任何事件循环创建之前，先把 asyncio
事件循环策略切换为 WindowsSelectorEventLoopPolicy，否则 psycopg3 异步驱动
无法在 uvicorn 默认的 ProactorEventLoop 上连接 Postgres（报
"Psycopg cannot use the 'ProactorEventLoop'..."）。app/main.py 顶部虽然
也设置了 policy，但 uvicorn 在 import main 之前就已经创建了事件循环，为时
已晚，因此必须在独立的启动脚本里先行设置。

用法：
    cd backend && python run.py
或
    $env:PYTHONPATH='backend'; python backend/run.py
"""
from __future__ import annotations

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        loop="asyncio",
        log_level="info",
    )


if __name__ == "__main__":
    main()
