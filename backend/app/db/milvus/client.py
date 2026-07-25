"""Milvus 向量数据库封装：collection 管理 + embedding + 检索。

三个 collection：
- review_corpus: 口碑语料（方面级标注），reputation agent 检索
- episodic_memory: 情景记忆（用户事件向量），记忆召回
- product_pool: 用户关注商品池（M3 可选）

embedding 用本地 Ollama qwen3-embedding（4096 维）。
"""
from __future__ import annotations

import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# qwen3-embedding 输出维度
EMBEDDING_DIM = 4096

# Collection 名称
REVIEW_CORPUS = "review_corpus"
EPISODIC_MEMORY = "episodic_memory"
PRODUCT_POOL = "product_pool"

_client: Any = None  # MilvusClient 单例


def get_milvus_client():
    """获取 MilvusClient 单例（惰性连接）。"""
    global _client
    if _client is None:
        from pymilvus import MilvusClient
        _client = MilvusClient(
            uri=f"http://{settings.milvus_host}:{settings.milvus_port}"
        )
        logger.info("Milvus 连接成功: %s:%s", settings.milvus_host, settings.milvus_port)
    return _client


async def get_embedding(text: str) -> list[float]:
    """调用 Ollama qwen3-embedding 生成向量。"""
    import httpx
    async with httpx.AsyncClient() as http:
        resp = await http.post(
            f"{settings.embedding_api_base}/embeddings",
            json={
                "model": settings.embedding_model,
                "input": text,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["data"][0]["embedding"]


async def get_embeddings(texts: list[str]) -> list[list[float]]:
    """批量生成向量。"""
    import httpx
    async with httpx.AsyncClient() as http:
        resp = await http.post(
            f"{settings.embedding_api_base}/embeddings",
            json={
                "model": settings.embedding_model,
                "input": texts,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return [d["embedding"] for d in data["data"]]
