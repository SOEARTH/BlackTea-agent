"""打分与组合规划 Agent：加权打分矩阵 + 动态权重 + 预算约束组合优化。

M2 升级：
- 动态权重：根据用户需求调整打分权重（预算敏感→价格权重上调，
  有硬约束→relevant 权重上调，组合场景→coupon 维度下调）
- 软偏好匹配：nice_to_have 命中加分，excluded 命中直接过滤
- 单品打分后，combo 场景调用 optimizer 生成组合方案
"""
from __future__ import annotations

import logging

from langchain_core.messages import AIMessage

from app.agents.optimizer import generate_combo_summary, knapsack_combo
from app.agents.state import GraphState
from app.models.decision import AspectScore, ScoredProduct
from app.models.requirement import ShoppingRequirement

logger = logging.getLogger(__name__)

# 基础权重（5 维度归一化为 1.0）
BASE_WEIGHTS: dict[str, float] = {
    "price": 0.25,
    "reputation": 0.25,
    "sales": 0.20,
    "coupon": 0.15,
    "brand": 0.15,
}


def _compute_dynamic_weights(requirement: ShoppingRequirement | None) -> dict[str, float]:
    """根据用户需求动态调整打分权重。

    规则：
    1. 预算敏感（budget_max 存在且偏低）→ price 权重 +0.10
    2. 有硬约束（must_have 非空）→ reputation 权重 +0.05（约束满足靠口碑/品质）
    3. 组合场景（combo=True）→ coupon 权重 -0.05（组合更看整体而非单券）
    4. 有软偏好（nice_to_have 非空）→ brand 权重 +0.05（品牌匹配软偏好）
    调整后归一化，确保权重之和 = 1.0。
    """
    weights = dict(BASE_WEIGHTS)

    if requirement:
        # 预算敏感：budget_max < 200 元算低预算
        if requirement.budget_max and float(requirement.budget_max) < 200:
            weights["price"] += 0.10

        # 有硬约束
        if requirement.must_have:
            weights["reputation"] += 0.05

        # 组合场景
        if requirement.combo:
            weights["coupon"] -= 0.05

        # 有软偏好
        if requirement.nice_to_have:
            weights["brand"] += 0.05

    # 归一化
    total = sum(weights.values())
    if total > 0:
        weights = {k: v / total for k, v in weights.items()}

    return weights


def _match_keywords(text: str, keywords: list[str]) -> list[str]:
    """返回 text 中命中的关键词列表。"""
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def _score_single_product(
    product,
    price_analysis: dict,
    reputation_scores: dict,
    weights: dict[str, float],
    requirement: ShoppingRequirement | None,
) -> ScoredProduct:
    """对单个商品计算加权打分矩阵。"""
    aspects: list[AspectScore] = []

    # -- 价格维度 --
    pa = price_analysis.get(product.goods_id, {})
    is_good = pa.get("is_good_price", True)
    percent_str = str(pa.get("current_percentile", "N/A") or "N/A")
    if isinstance(pa.get("current_percentile"), float):
        percent_str = f"{pa['current_percentile']:.0%}"
    price_factor = 6.0
    if is_good:
        price_factor = 8.5
    # 预算充裕度加分：越接近预算下限越划算
    if requirement and requirement.budget_max:
        ratio = float(product.price) / float(requirement.budget_max)
        if ratio < 0.5:
            price_factor = 9.0  # 远低于预算
        elif ratio > 0.9:
            price_factor = 7.0 if is_good else 4.0  # 逼近预算上限
    aspects.append(AspectScore(
        aspect="price",
        score=round(price_factor, 2),
        weight=round(weights["price"], 4),
        evidence=f"当前价 {product.price} 元，{'好价区间' if is_good else '偏高'}"
                 f"（历史分位 {percent_str}）"
    ))

    # -- 口碑维度 --
    rep_score = reputation_scores.get(product.goods_id, 0.0)
    # 无 RAG 口碑时，用店铺 DSR 评分兜底
    if rep_score == 0.0:
        dsr = product.dsr_score or 0
        ship = product.ship_score or 0
        service = product.service_score or 0
        avg = (dsr + ship + service) / 3 if (dsr + ship + service) > 0 else 4.5
        rep_score = round(avg * 2, 1)  # 5 分制 → 10 分制
    aspects.append(AspectScore(
        aspect="reputation",
        score=round(rep_score, 2),
        weight=round(weights["reputation"], 4),
        evidence=f"店铺评分：描述{product.dsr_score} 物流{product.ship_score} 服务{product.service_score}"
                 + (f"｜口碑RAG {rep_score}" if reputation_scores.get(product.goods_id) else "（无RAG，DSR兜底）")
    ))

    # -- 销量维度 --
    sales_score = 5.0
    if product.sales and product.sales > 5000:
        sales_score = 9.0
    elif product.sales and product.sales > 1000:
        sales_score = 8.0
    elif product.sales and product.sales > 100:
        sales_score = 6.0
    aspects.append(AspectScore(
        aspect="sales",
        score=sales_score,
        weight=round(weights["sales"], 4),
        evidence=f"30天热销 {product.sales or 'N/A'} 件"
    ))

    # -- 券力度维度 --
    coupon_score = 5.0
    if product.coupon_amount and product.coupon_amount > 0:
        ratio = float(product.coupon_amount) / max(float(product.original_price or product.price), 1)
        coupon_score = min(10.0, 3.0 + ratio * 20)
    aspects.append(AspectScore(
        aspect="coupon",
        score=round(coupon_score, 2),
        weight=round(weights["coupon"], 4),
        evidence=f"券 {product.coupon_amount} 元，折扣力度 {product.discounts or 'N/A'}"
    ))

    # -- 品牌/店铺维度 --
    brand_score = 5.0
    if product.brand:
        brand_score = 7.0
    if product.shop_type == "tmall":
        brand_score += 1.0
    # 软偏好命中加分
    nice_hits: list[str] = []
    if requirement and requirement.nice_to_have:
        full_text = f"{product.title or ''} {product.brand or ''} {product.shop_name or ''}"
        nice_hits = _match_keywords(full_text, requirement.nice_to_have)
        if nice_hits:
            brand_score = min(10.0, brand_score + 1.5)
    aspects.append(AspectScore(
        aspect="brand",
        score=round(min(10.0, brand_score), 2),
        weight=round(weights["brand"], 4),
        evidence=f"品牌 {product.brand or '无'}，店铺 {product.shop_name or 'N/A'}（{product.shop_type or 'N/A'}）"
                 + (f"｜命中软偏好：{nice_hits}" if nice_hits else "")
    ))

    total = sum(a.score * a.weight for a in aspects)
    return ScoredProduct(product=product, aspects=aspects, total=round(total, 2), rank=0)


def _filter_excluded(
    products: list,
    requirement: ShoppingRequirement | None,
) -> tuple[list, list[str]]:
    """过滤掉 excluded 列表中命中的商品，返回 (过滤后列表, 被过滤的商品标题)。"""
    if not requirement or not requirement.excluded:
        return products, []
    kept = []
    removed_titles = []
    for p in products:
        full_text = f"{p.title or ''} {p.brand or ''} {p.shop_name or ''}".lower()
        if any(kw.lower() in full_text for kw in requirement.excluded):
            removed_titles.append(p.title or p.dtitle or p.goods_id)
        else:
            kept.append(p)
    return kept, removed_titles


def scoring_node(state: GraphState) -> GraphState:
    """打分节点：动态权重打分 → 排序 → 组合优化（combo 场景）。"""
    products = state.get("products", [])
    price_analysis = state.get("price_analysis", {})
    reputation_scores = state.get("reputation_scores", {})
    requirement = state.get("requirement")

    # 1. 过滤排除项
    products, removed = _filter_excluded(products, requirement)
    filter_msg = f"（已排除 {len(removed)} 个商品）" if removed else ""

    # 2. 动态权重
    weights = _compute_dynamic_weights(requirement)
    weight_desc = "、".join(f"{k}={v:.2f}" for k, v in weights.items())

    # 3. 逐商品打分
    scored = [
        _score_single_product(p, price_analysis, reputation_scores, weights, requirement)
        for p in products
    ]
    scored.sort(key=lambda s: s.total, reverse=True)
    for i, s in enumerate(scored):
        s.rank = i + 1

    # 4. 组合优化（combo 场景）
    combos: list[list[ScoredProduct]] = []
    if requirement and requirement.combo and requirement.slots:
        combos = knapsack_combo(scored, requirement)
    combo_msg = f"，生成 {len(combos)} 套组合方案" if combos else ""

    return {
        **state,
        "scored_products": scored,
        "combos": combos,
        "messages": [AIMessage(
            content=f"打分完成（权重：{weight_desc}），已排序 {len(scored)} 个商品{filter_msg}{combo_msg}，正在反思校验..."
        )],
        "next_agent": "reflect",
    }
