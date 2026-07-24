"""组合优化 Agent：背包 DP 求解多品类组合采购方案。

当 ShoppingRequirement.combo == True 且 slots 非空时，将候选商品按槽位
分组，用 0/1 背包动态规划在预算约束下最大化总得分，产出 2-3 套方案对比。

算法：
1. 按槽位分组：用关键词匹配把 scored_products 归入各 slot
2. 每个槽位取 top-K 候选（默认 K=5），避免组合爆炸
3. 多维 0/1 背包 DP：状态 = (槽位索引, 剩余预算), 价值 = 总得分
4. 回溯选中的商品，并产出 2-3 套备选方案（次优解）
"""
from __future__ import annotations

import logging
from decimal import Decimal

from app.models.decision import ScoredProduct
from app.models.requirement import ShoppingRequirement

logger = logging.getLogger(__name__)

# 每个槽位最多保留多少候选参与 DP，避免组合爆炸
CANDIDATES_PER_SLOT = 5
# 最多产出几套备选方案
MAX_COMBO_SCHEMES = 3
# 预算量化精度（元），背包容量按此粒度离散化
BUDGET_GRANULARITY = Decimal("1")


def _match_slot(product_title: str, slot: str) -> bool:
    """判断商品标题是否匹配某槽位品类关键词。"""
    title_lower = product_title.lower()
    slot_lower = slot.lower()
    # 直接包含
    if slot_lower in title_lower:
        return True
    # 拆词匹配（slot 可能是"睡袋"这种单义词，title 可能含" Camping 睡袋"）
    slot_words = [w for w in slot_lower.replace("/", " ").split() if w]
    return any(w in title_lower for w in slot_words)


def _partition_by_slots(
    scored: list[ScoredProduct],
    slots: list[str],
) -> dict[str, list[ScoredProduct]]:
    """把已打分商品按槽位分组，返回 {slot: [ScoredProduct, ...]}。

    匹配规则：商品标题包含槽位关键词即归入该槽位。
    一个商品可匹配多个槽位但只归入第一个匹配的槽位，避免重复。
    """
    partition: dict[str, list[ScoredProduct]] = {s: [] for s in slots}
    for sp in scored:
        title = sp.product.title or sp.product.dtitle or ""
        for slot in slots:
            if _match_slot(title, slot):
                partition[slot].append(sp)
                break
    # 每个槽位按得分降序，取 top-K
    for slot in slots:
        partition[slot].sort(key=lambda s: s.total, reverse=True)
        partition[slot] = partition[slot][:CANDIDATES_PER_SLOT]
    return partition


def _quantize_price(price: Decimal) -> int:
    """把价格量化为整数粒度用于背包容量。"""
    return int((price / BUDGET_GRANULARITY).quantize(Decimal("1")))


def knapsack_combo(
    scored: list[ScoredProduct],
    requirement: ShoppingRequirement,
) -> list[list[ScoredProduct]]:
    """背包 DP 求解组合方案，返回最多 MAX_COMBO_SCHEMES 套方案。

    每套方案是一个 list[ScoredProduct]，长度 = len(slots)（每个槽位选一个）。
    方案按总得分降序排列；第 1 套为最优解，第 2/3 套为近似次优解。

    无组合场景或数据不足时返回空列表。
    """
    if not requirement.combo or not requirement.slots:
        return []

    slots = requirement.slots
    partition = _partition_by_slots(scored, slots)

    # 每个槽位必须有候选，否则无法组完整方案
    if any(len(partition[s]) == 0 for s in slots):
        missing = [s for s in slots if len(partition[s]) == 0]
        logger.warning("槽位 %s 无候选商品，无法组合", missing)
        return []

    budget = requirement.budget_max
    if budget is None:
        # 无预算约束时直接取每槽位 top-1，但仍生成 2-3 套备选
        budget = Decimal("999999")

    capacity = _quantize_price(budget)

    # ---- 多维 0/1 背包 DP ----
    # 状态: dp[slot_idx][remaining_capacity] = (max_score, choice_list)
    # 但为了回溯多套方案，我们记录路径。
    # 简化做法：先求最优解，然后通过禁用选择求次优解。

    schemes = _solve_topk_schemes(partition, slots, capacity, k=MAX_COMBO_SCHEMES)
    return schemes


def _solve_topk_schemes(
    partition: dict[str, list[ScoredProduct]],
    slots: list[str],
    capacity: int,
    k: int,
) -> list[list[ScoredProduct]]:
    """求 top-k 套组合方案。

    方法：先用标准 DP 求最优解；然后逐个禁用最优解中的某个选择，
    重新 DP 求次优解，去重后取前 k 套。
    """
    n = len(slots)
    best = _dp_solve(partition, slots, capacity, forbidden=set())
    if not best:
        return []

    schemes = [best]
    # 禁用最优解中的每个 (slot_idx, goods_id) 组合，求次优解
    seen = {frozenset(sp.product.goods_id for sp in best)}

    candidates: list[tuple[float, list[ScoredProduct]]] = []
    for i, sp in enumerate(best):
        forbidden_key = (i, sp.product.goods_id)
        alt = _dp_solve(partition, slots, capacity, forbidden={forbidden_key})
        if alt:
            key = frozenset(sp2.product.goods_id for sp2 in alt)
            if key not in seen:
                seen.add(key)
                total = sum(s.total for s in alt)
                candidates.append((total, alt))

    candidates.sort(key=lambda x: x[0], reverse=True)
    for _, alt in candidates[:k - 1]:
        schemes.append(alt)

    return schemes


def _dp_solve(
    partition: dict[str, list[ScoredProduct]],
    slots: list[str],
    capacity: int,
    forbidden: set[tuple[int, str]],  # (slot_idx, goods_id) 被禁用
) -> list[ScoredProduct] | None:
    """标准多槽位 0/1 背包 DP，返回最优选择的商品列表。

    forbidden: 禁用某些 (槽位索引, goods_id) 组合，用于求次优解。
    """
    n = len(slots)
    # dp[c] = (max_score, [(slot_idx, goods_id, price_quant), ...])
    # 初始化: dp[0] = (0, [])，其余 = -inf
    dp: dict[int, tuple[float, list[tuple[int, str, int]]]] = {0: (0.0, [])}

    for slot_idx in range(n):
        slot = slots[slot_idx]
        candidates = partition[slot]
        new_dp: dict[int, tuple[float, list[tuple[int, str, int]]]] = {}

        for cap, (score, path) in dp.items():
            for cand in candidates:
                gid = cand.product.goods_id
                if (slot_idx, gid) in forbidden:
                    continue
                price_q = _quantize_price(cand.product.price)
                if cap + price_q > capacity:
                    continue  # 超预算
                new_cap = cap + price_q
                new_score = score + cand.total
                new_path = path + [(slot_idx, gid, price_q)]
                if new_cap not in new_dp or new_dp[new_cap][0] < new_score:
                    new_dp[new_cap] = (new_score, new_path)

        dp = new_dp
        if not dp:
            break  # 某槽位无可行选择

    if not dp:
        return None

    # 取最大得分
    best_cap = max(dp, key=lambda c: dp[c][0])
    best_score, best_path = dp[best_cap]

    # 回溯：把 path 中的 goods_id 映射回 ScoredProduct
    goods_map: dict[str, ScoredProduct] = {}
    for slot_idx, gid, _ in best_path:
        slot = slots[slot_idx]
        for sp in partition[slot]:
            if sp.product.goods_id == gid:
                goods_map[gid] = sp
                break

    result = [goods_map[gid] for _, gid, _ in best_path]
    return result


def generate_combo_summary(
    schemes: list[list[ScoredProduct]],
    requirement: ShoppingRequirement,
) -> str:
    """生成组合方案的文字摘要。"""
    if not schemes:
        return ""
    lines = [f"组合采购方案（{requirement.category}，预算 {requirement.budget_max} 元）："]
    for i, scheme in enumerate(schemes):
        total_price = sum(float(sp.product.price) for sp in scheme)
        total_score = sum(sp.total for sp in scheme)
        items = " + ".join(sp.product.dtitle or sp.product.title for sp in scheme)
        lines.append(f"方案{i + 1}：{items}，合计 {total_price:.0f} 元，总分 {total_score:.1f}")
    return "\n".join(lines)
