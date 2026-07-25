"""Postgres checkpointer 生命周期管理 + 连接池（记忆系统用）。

提供：
- get_checkpointer(): 异步上下文管理器，yield AsyncPostgresSaver
- init_checkpointer(): 启动时调用一次，建表 + 迁移
- get_connection_pool(): 获取 AsyncConnectionPool（记忆系统用，M3 新增）
- init_connection_pool() / close_connection_pool(): 生命周期管理

用法（FastAPI lifespan）：

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(app):
        await init_connection_pool()
        async with get_checkpointer() as checkpointer:
            await init_checkpointer(checkpointer)
            app.state.graph = build_graph(checkpointer)
            yield
        await close_connection_pool()

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


# ---- 连接池（M3 记忆系统用）----

_pool = None


async def init_connection_pool():
    """初始化 AsyncConnectionPool，供记忆系统读写 app.* 业务表。"""
    global _pool
    if _pool is None:
        from psycopg_pool import AsyncConnectionPool
        _pool = AsyncConnectionPool(
            conninfo=settings.database_url,
            min_size=2,
            max_size=10,
            open=False,
        )
        await _pool.open()
    return _pool


async def get_connection_pool():
    """获取连接池单例。未初始化时返回 None（降级跳过记忆功能）。"""
    return _pool


async def close_connection_pool():
    """关闭连接池（FastAPI shutdown 时调用）。"""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
