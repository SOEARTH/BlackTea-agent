"""口碑语料 RAG 检索：从 Milvus review_corpus 做方面级口碑聚合。"""
from __future__ import annotations

import logging
from typing import Any

from app.db.milvus.client import REVIEW_CORPUS, get_embedding, get_milvus_client

logger = logging.getLogger(__name__)

# 方面关键词映射：品牌维度 -> 检索时用于过滤或加权
ASPECT_KEYWORDS = {
    "续航": ["续航", "电量", "电池", "充电", "耗电"],
    "做工": ["做工", "质感", "材质", "工艺", "细节", "品质"],
    "售后": ["售后", "客服", "退换", "保修", "维修"],
    "性价比": ["性价比", "划算", "值不值", "价格", "便宜"],
    "音质": ["音质", "声音", "降噪", "底噪"],
    "舒适度": ["舒适", "佩戴", "重量", "压头"],
    "防水": ["防水", "防汗", "IPX", "淋雨"],
    "便携": ["便携", "轻便", "体积", "收纳"],
}


async def search_review_corpus(
    query: str,
    category: str | None = None,
    top_k: int = 20,
) -> list[dict]:
    """从 review_corpus 语义检索与查询相关的口碑语料。

    Args:
        query: 检索文本（品类名 + 场景 + 商品标题等）
        category: 可选品类过滤
        top_k: 返回条数

    Returns:
        list[dict]: 每条含 text, aspects, source, category, score
    """
    try:
        client = get_milvus_client()
        query_vector = await get_embedding(query)

        # 构建过滤条件
        filter_expr = ""
        if category:
            filter_expr = f'category == "{category}"'

        results = client.search(
            collection_name=REVIEW_CORPUS,
            data=[query_vector],
            limit=top_k,
            filter=filter_expr or None,
            output_fields=["text", "aspects", "source", "category", "goods_id"],
            search_params={"metric_type": "COSINE", "params": {"nprobe": 16}},
        )

        if not results:
            return []

        hits = results[0]
        return [
            {
                "text": hit["entity"].get("text", ""),
                "aspects": hit["entity"].get("aspects", []),
                "source": hit["entity"].get("source", ""),
                "category": hit["entity"].get("category", ""),
                "goods_id": hit["entity"].get("goods_id", ""),
                "score": hit["distance"],
            }
            for hit in hits
        ]
    except Exception as e:
        logger.warning("review_corpus 检索失败: %s", e)
        return []


async def aggregate_aspect_scores(
    reviews: list[dict],
    target_aspects: list[str] | None = None,
) -> dict[str, float]:
    """把检索到的口碑语料按方面聚合为结构化评分（0-10）。

    简化策略：按 aspect 关键词命中频次 + 语义相似度加权，
    产出 {aspect: score} 字典。无命中的 aspect 不返回。

    Args:
        reviews: search_review_corpus 的返回
        target_aspects: 限定聚合的 aspect 列表，None 则用全部

    Returns:
        {aspect_name: score(0-10)}
    """
    if not reviews:
        return {}

    aspect_scores: dict[str, list[float]] = {}

    for review in reviews:
        text = review["text"]
        aspects = review.get("aspects", [])
        similarity = max(0, review.get("score", 0))  # cosine similarity 0-1

        # 用 review 自己标注的 aspects，或关键词匹配
        matched = aspects if aspects else _match_aspects(text)

        for aspect in matched:
            if target_aspects and aspect not in target_aspects:
                continue
            # 正面/负面判断（简化：相似度高 + 含正面词 -> 高分）
            sentiment = _estimate_sentiment(text)
            raw = similarity * 5 + sentiment * 5  # 0-10
            aspect_scores.setdefault(aspect, []).append(raw)

    # 均值聚合
    return {
        aspect: round(sum(scores) / len(scores), 1)
        for aspect, scores in aspect_scores.items()
    }


def _match_aspects(text: str) -> list[str]:
    """用关键词匹配把文本归到 aspect 类别。"""
    text_lower = text.lower()
    matched = []
    for aspect, keywords in ASPECT_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            matched.append(aspect)
    return matched


def _estimate_sentiment(text: str) -> float:
    """简化情感估计：正面词 +1，负面词 -1，归一化到 0-10。

    M4 可替换为 LLM-as-judge 做精细情感分析。
    """
    positive_words = ["好", "优秀", "推荐", "满意", "不错", "出色", "耐用", "舒服", "值得"]
    negative_words = ["差", "烂", "问题", "退货", "失望", "不行", "槽", "难用"]

    text_lower = text.lower()
    pos = sum(1 for w in positive_words if w in text_lower)
    neg = sum(1 for w in negative_words if w in text_lower)

    if pos + neg == 0:
        return 5.0  # 中性
    return max(0, min(10, 5 + (pos - neg) * 3))


async def get_reputation_for_product(
    product_title: str,
    category: str | None = None,
) -> dict[str, Any]:
    """为单个商品获取方面级口碑分。

    Returns:
        {
            "overall": float,         # 综合口碑分 0-10
            "aspects": {aspect: score}, # 方面级分
            "review_count": int,        # 命中语料数
            "source": "rag" | "dsr_fallback",
        }
    """
    query = f"{category} {product_title}" if category else product_title
    reviews = await search_review_corpus(query, category=category, top_k=20)

    if not reviews:
        return {
            "overall": 0.0,
            "aspects": {},
            "review_count": 0,
            "source": "dsr_fallback",
        }

    aspect_scores = await aggregate_aspect_scores(reviews)

    # 综合分 = 方面分均值
    overall = round(sum(aspect_scores.values()) / len(aspect_scores), 1) if aspect_scores else 0.0

    return {
        "overall": overall,
        "aspects": aspect_scores,
        "review_count": len(reviews),
        "source": "rag",
    }
