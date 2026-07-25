"""Milvus collection schema 定义与初始化。

三个 collection 的 schema：
1. review_corpus — 口碑语料 chunk，方面级标注
2. episodic_memory — 用户情景记忆事件向量
3. product_pool — 用户关注商品语义向量（M3 可选）

索引策略：IVF_FLAT + nprobe 16，距离 COSINE。
4096 维向量内存开销较大，量大时可迁移到 HNSW 或 IVF_SQ8。
"""
from __future__ import annotations

import logging

from app.db.milvus.client import EMBEDDING_DIM, EPISODIC_MEMORY, PRODUCT_POOL, REVIEW_CORPUS, get_milvus_client

logger = logging.getLogger(__name__)


def init_collections():
    """创建所有 Milvus collection（幂等，已存在则跳过）。"""
    from pymilvus import DataType

    client = get_milvus_client()

    # ---- review_corpus ----
    if not client.has_collection(REVIEW_CORPUS):
        schema = client.create_schema(auto_id=True, enable_dynamic_field=True)
        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM)
        schema.add_field("text", DataType.VARCHAR, max_length=4096)
        schema.add_field("source", DataType.VARCHAR, max_length=256)
        schema.add_field("category", DataType.VARCHAR, max_length=128)
        schema.add_field("aspects", DataType.ARRAY, element_type=DataType.VARCHAR, max_capacity=20, max_length=64)
        schema.add_field("goods_id", DataType.VARCHAR, max_length=64)

        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type="IVF_FLAT",
            metric_type="COSINE",
            params={"nlist": 128},
        )
        client.create_collection(
            collection_name=REVIEW_CORPUS,
            schema=schema,
            index_params=index_params,
        )
        logger.info("Collection %s 创建成功", REVIEW_CORPUS)

    # ---- episodic_memory ----
    if not client.has_collection(EPISODIC_MEMORY):
        schema = client.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM)
        schema.add_field("user_id", DataType.VARCHAR, max_length=64)
        schema.add_field("content", DataType.VARCHAR, max_length=1024)
        schema.add_field("importance", DataType.FLOAT)
        schema.add_field("created_at", DataType.INT64)

        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type="IVF_FLAT",
            metric_type="COSINE",
            params={"nlist": 128},
        )
        client.create_collection(
            collection_name=EPISODIC_MEMORY,
            schema=schema,
            index_params=index_params,
        )
        logger.info("Collection %s 创建成功", EPISODIC_MEMORY)

    # ---- product_pool ----
    if not client.has_collection(PRODUCT_POOL):
        schema = client.create_schema(auto_id=True, enable_dynamic_field=True)
        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM)
        schema.add_field("user_id", DataType.VARCHAR, max_length=64)
        schema.add_field("goods_id", DataType.VARCHAR, max_length=64)
        schema.add_field("title", DataType.VARCHAR, max_length=512)
        schema.add_field("price", DataType.FLOAT)
        schema.add_field("event_type", DataType.VARCHAR, max_length=32)
        schema.add_field("created_at", DataType.INT64)

        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type="IVF_FLAT",
            metric_type="COSINE",
            params={"nlist": 128},
        )
        client.create_collection(
            collection_name=PRODUCT_POOL,
            schema=schema,
            index_params=index_params,
        )
        logger.info("Collection %s 创建成功", PRODUCT_POOL)


def drop_all_collections():
    """删除所有 collection（测试/调试用，谨慎！）。"""
    client = get_milvus_client()
    for name in [REVIEW_CORPUS, EPISODIC_MEMORY, PRODUCT_POOL]:
        if client.has_collection(name):
            client.drop_collection(name)
            logger.warning("Collection %s 已删除", name)
