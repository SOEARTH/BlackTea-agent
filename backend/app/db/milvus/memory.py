"""双层记忆：PG 结构化画像 + Milvus 情景记忆。

记忆写入流程：
1. 对话结束（或反思通过后），异步提取记忆事件
2. 结构化画像写入 PG app.profile_facts（预算带/品牌偏好/排除项）
3. 情景记忆写入 Milvus episodic_memory + PG app.episodic_memories（元数据）

记忆召回流程：
1. scoring 节点前，按 user_id 从 PG 读画像，从 Milvus 语义召回情景记忆
2. 画像调整打分权重（预算敏感→price 权重上调）
3. 情景记忆影响商品过滤或权重微调（如退过某品牌→降权）
"""
from __future__ import annotations

import logging
import time
from typing import Any
from uuid import uuid4

from app.db.milvus.client import EPISODIC_MEMORY, get_embedding, get_milvus_client

logger = logging.getLogger(__name__)


# ---- 情景记忆写入/召回 ----

async def write_episodic_memory(
    user_id: str,
    content: str,
    importance: float = 0.5,
) -> str | None:
    """写入一条情景记忆到 Milvus + PG。

    Args:
        user_id: 用户 ID
        content: 记忆内容（如"用户对某品牌耳机续航不满"）
        importance: 重要性权重 0-1

    Returns:
        Milvus 记录 ID（也作为 PG milvus_id），失败返回 None
    """
    try:
        client = get_milvus_client()
        vector = await get_embedding(content)
        mem_id = str(uuid4())
        created_at = int(time.time())

        # 写 Milvus
        client.insert(
            collection_name=EPISODIC_MEMORY,
            data=[{
                "id": mem_id,
                "vector": vector,
                "user_id": user_id,
                "content": content,
                "importance": importance,
                "created_at": created_at,
            }],
        )

        # 写 PG 元数据（调用方负责，这里只返回 ID）
        return mem_id
    except Exception as e:
        logger.warning("写入情景记忆失败: %s", e)
        return None


async def recall_episodic_memories(
    user_id: str,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """按语义召回用户的情景记忆。

    Returns:
        list[dict]: [{content, importance, created_at, score}]
    """
    try:
        client = get_milvus_client()
        query_vector = await get_embedding(query)

        results = client.search(
            collection_name=EPISODIC_MEMORY,
            data=[query_vector],
            limit=top_k,
            filter=f'user_id == "{user_id}"',
            output_fields=["content", "importance", "created_at"],
            search_params={"metric_type": "COSINE", "params": {"nprobe": 16}},
        )

        if not results:
            return []

        return [
            {
                "content": hit["entity"].get("content", ""),
                "importance": hit["entity"].get("importance", 0.5),
                "created_at": hit["entity"].get("created_at", 0),
                "score": hit["distance"],
            }
            for hit in results[0]
        ]
    except Exception as e:
        logger.warning("召回情景记忆失败: %s", e)
        return []


# ---- 结构化画像（PG）----

async def write_profile_fact(
    pool,
    user_id: str,
    category: str,
    key: str,
    value: str,
    confidence: float = 1.0,
    source: str = "dialog",
):
    """写入/更新一条用户画像事实到 PG app.profile_facts。

    Args:
        pool: AsyncConnectionPool（由 checkpointer 提供）
        user_id: 用户 ID
        category: 画像类别（budget / brand / scenario）
        key: 事实键（如"预算带" / "偏好品牌" / "排斥品牌"）
        value: 事实值
    """
    try:
        async with pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO app.profile_facts (user_id, category, key, value, confidence, source, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, now())
                ON CONFLICT (user_id, category, key)
                DO UPDATE SET value = $4, confidence = $5, source = $6, updated_at = now()
                """,
                user_id, category, key, value, confidence, source,
            )
    except Exception as e:
        logger.warning("写入画像事实失败: %s", e)


async def read_profile_facts(
    pool,
    user_id: str,
) -> list[dict]:
    """读取用户所有画像事实。

    Returns:
        [{category, key, value, confidence, source}]
    """
    try:
        async with pool.connection() as conn:
            cur = await conn.execute(
                "SELECT category, key, value, confidence, source FROM app.profile_facts WHERE user_id = $1",
                user_id,
            )
            rows = await cur.fetchall()
            return [
                {"category": r[0], "key": r[1], "value": r[2], "confidence": r[3], "source": r[4]}
                for r in rows
            ]
    except Exception as e:
        logger.warning("读取画像事实失败: %s", e)
        return []


async def extract_and_store_memories(
    pool,
    user_id: str,
    requirement,
    report,
):
    """对话结束后异步提取记忆：画像入 PG，情景入 Milvus。

    Args:
        pool: AsyncConnectionPool
        user_id: 用户 ID
        requirement: ShoppingRequirement
        report: DecisionReport
    """
    # 1. 画像提取
    if requirement:
        if requirement.budget_max:
            budget_val = float(requirement.budget_max)
            band = "低" if budget_val < 200 else "中" if budget_val < 1000 else "高"
            await write_profile_fact(pool, user_id, "budget", "预算带", band)
            await write_profile_fact(pool, user_id, "budget", "预算上限", str(budget_val))

        if requirement.excluded:
            for brand in requirement.excluded:
                await write_profile_fact(pool, user_id, "brand", "排斥品牌", brand)

        if requirement.nice_to_have:
            for pref in requirement.nice_to_have:
                await write_profile_fact(pool, user_id, "preference", "软偏好", pref)

    # 2. 情景记忆提取
    if report and report.recommendations:
        top = report.recommendations[0]
        content = f"用户搜索{requirement.category if requirement else '商品'}，推荐了{top.product.title}，得分{top.total}"
        await write_episodic_memory(user_id, content, importance=0.6)
