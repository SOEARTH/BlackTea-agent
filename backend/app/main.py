"""FastAPI 入口，M1 骨架。

启动时通过 lifespan 初始化 PostgresSaver checkpointer 并编译 graph，
挂到 app.state 供路由使用。
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.graph import build_graph
from app.config import settings
from app.db.checkpointer import get_checkpointer, init_checkpointer
from app.routes.chat import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭生命周期。

    启动：
    1. 连接 PG，创建 AsyncPostgresSaver
    2. 调用 setup() 建表 + 迁移（首次执行）
    3. 编译带 checkpointer 的 graph 挂到 app.state.graph

    关闭：async with 退出时自动释放 PG 连接。
    """
    if settings.database_url:
        async with get_checkpointer() as checkpointer:
            await init_checkpointer(checkpointer)
            app.state.graph = build_graph(checkpointer)
            yield
    else:
        # 无 DB 配置时退化到无 checkpointer 模式
        app.state.graph = build_graph()
        yield


app = FastAPI(title="BlackTea", version="0.1.0", lifespan=lifespan)

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