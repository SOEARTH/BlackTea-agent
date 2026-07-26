"""FastAPI 入口。

启动时通过 lifespan 初始化 PostgresSaver checkpointer + 连接池 + Milvus collection，
编译 graph 挂到 app.state 供路由使用。

M3 新增：
- 连接池（记忆系统读写 app.* 业务表）
- Milvus collection 初始化（review_corpus / episodic_memory / product_pool）
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import asyncio
import sys

# Windows 上 psycopg3 异步驱动不能在默认的 ProactorEventLoop 上运行，
# uvicorn 在 Windows 默认用的也是 ProactorEventLoop，会导致连接 PG 时
# 报 "Psycopg cannot use the 'ProactorEventLoop'..." 并让 lifespan 启动失败。
# 这里在导入应用、创建事件循环之前，切换为 SelectorEventLoopPolicy。
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.graph import build_graph
from app.config import settings
from app.db.checkpointer import (
    close_connection_pool,
    get_checkpointer,
    init_checkpointer,
    init_connection_pool,
)
from app.routes.chat import router as chat_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭生命周期。

    启动：
    1. 初始化 PG 连接池（记忆系统用）
    2. 连接 PG，创建 AsyncPostgresSaver checkpointer
    3. 调用 setup() 建表 + 迁移
    4. 初始化 Milvus collection（M3，可选——失败不阻塞）
    5. 编译带 checkpointer 的 graph 挂到 app.state.graph

    关闭：关闭连接池，async with 退出时自动释放 PG checkpointer 连接。
    """
    # 1. 先启动连接池（记忆系统用）
    await init_connection_pool()

    # 4. Milvus collection 初始化（失败不阻塞，降级为无记忆模式）
    try:
        from app.db.milvus.collections import init_collections
        init_collections()
        logger.info("Milvus collection 初始化完成")
    except Exception as e:
        logger.warning("Milvus 初始化失败，RAG/记忆功能降级: %s", e)

    if settings.database_url:
        async with get_checkpointer() as checkpointer:
            await init_checkpointer(checkpointer)
            app.state.graph = build_graph(checkpointer)
            yield
    else:
        app.state.graph = build_graph()
        yield

    # 关闭连接池
    await close_connection_pool()


app = FastAPI(title="BlackTea", version="0.2.0", lifespan=lifespan)

# CORS — Vue3 开发服务器（localhost:5173）跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(chat_router)


@app.get("/health")
async def health():
    graph_ready = hasattr(app.state, "graph") and app.state.graph is not None
    return {"status": "ok", "graph_ready": graph_ready}
