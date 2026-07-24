"""Postgres checkpointer 生命周期管理。

提供两个工厂函数：
- get_checkpointer(): 异步上下文管理器，yield AsyncPostgresSaver
- init_checkpointer(): 启动时调用一次，建表 + 迁移

用法（FastAPI lifespan）：

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app):
        async with get_checkpointer() as checkpointer:
            await init_checkpointer(checkpointer)
            app.state.graph = build_graph(checkpointer)
            yield

    app = FastAPI(lifespan=lifespan)

用法（脚本 / 临时使用）：

    async with get_checkpointer() as cp:
        await init_checkpointer(cp)
        graph = build_graph(cp)
        ...
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.config import settings


async def get_checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    """异步上下文管理器，yield 一个已连接的 AsyncPostgresSaver。

    连接配置：autocommit=True, prepare_threshold=0（psycopg3 原生协议，
    避免 prepared statement 缓存与 LangGraph 并发写入冲突）。
    """
    async with AsyncPostgresSaver.from_conn_string(settings.database_url) as saver:
        yield saver


async def init_checkpointer(checkpointer: AsyncPostgresSaver) -> None:
    """首次使用前调用一次，在 public schema 建表 + 跑迁移。

    LangGraph 的 checkpoint 表（checkpoints / checkpoint_writes /
    checkpoint_blobs / checkpoint_migrations）全部在 public schema，
    与业务表 app.* 互不干扰。
    """
    await checkpointer.setup()