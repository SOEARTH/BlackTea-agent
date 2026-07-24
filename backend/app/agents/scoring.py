"""打分与组合规划 Agent：加权打分矩阵 + 预算约束组合优化。"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from langchain_core.messages import AIMessage

from app.agents.state import GraphState
from app.models.decision import AspectScore, ScoredProduct


def _score_single_product(product, price_analysis: dict, reputation_scores: dict) -> ScoredProduct:
    """对单个商品计算加权打分矩阵。"""
    aspects: list[AspectScore] = []

    # 价格维度
    pa = price_analysis.get(product.goods_id, {})
    is_good = pa.get("is_good_price", True)
    aspects.append(AspectScore(
        aspect="price",
        score=8.0 if is_good else 5.0,
        weight=0.25,
        evidence=f"当前价 {product.price} 元，{'好价区间' if is_good else '偏高'}"
                 f"（历史分位 {pa.get('current_percentile', 'N/A')}）"
    ))

    # 口碑维度
    rep_score = reputation_scores.get(product.goods_id, 6.0)
    aspects.append(AspectScore(
        aspect="reputation",
        score=rep_score,
        weight=0.25,
        evidence=f"店铺评分聚合：描述{product.dsr_score} 物流{product.ship_score} 服务{product.service_score}"
    ))

    # 销量维度（平台内分位归一化）
    score = 5.0
    if product.sales and product.sales > 1000:
        score = 8.0
    elif product.sales and product.sales > 100:
        score = 6.0
    aspects.append(AspectScore(
        aspect="sales",
        score=score,
        weight=0.2,
        evidence=f"30天热销 {product.sales or 'N/A'} 件"
    ))

    # 券力度维度
    coupon_score = 5.0
    if product.coupon_amount and product.coupon_amount > 0:
        ratio = float(product.coupon_amount) / max(float(product.original_price or product.price), 1)
        coupon_score = min(10.0, 3.0 + ratio * 20)
    aspects.append(AspectScore(
        aspect="coupon",
        score=coupon_score,
        weight=0.15,
        evidence=f"券 {product.coupon_amount} 元，折扣力度 {product.discounts or 'N/A'}"
    ))

    # 品牌/店铺维度
    brand_score = 7.0 if product.brand else 5.0
    if product.shop_type == "tmall":
        brand_score += 1.0
    aspects.append(AspectScore(
        aspect="brand",
        score=min(10.0, brand_score),
        weight=0.15,
        evidence=f"品牌 {product.brand or '无'}，店铺 {product.shop_name or 'N/A'}（{product.shop_type or 'N/A'}）"
    ))

    total = sum(a.score * a.weight for a in aspects)
    return ScoredProduct(product=product, aspects=aspects, total=round(total, 2), rank=0)


def scoring_node(state: GraphState) -> GraphState:
    """打分节点：对候选商品加权打分并排序。"""
    products = state.get("products", [])
    price_analysis = state.get("price_analysis", {})
    reputation_scores = state.get("reputation_scores", {})

    scored = [_score_single_product(p, price_analysis, reputation_scores) for p in products]
    scored.sort(key=lambda s: s.total, reverse=True)
    for i, s in enumerate(scored):
        s.rank = i + 1

    return {
        **state,
        "scored_products": scored,
        "next_agent": "reflect",
        "messages": [AIMessage(content=f"打分完成，已排序 {len(scored)} 个商品，正在反思校验...")],
    }
