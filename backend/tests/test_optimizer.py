"""组合优化（背包 DP）单元测试。"""
from decimal import Decimal
from datetime import datetime, timezone

from app.agents.optimizer import (
    knapsack_combo,
    generate_combo_summary,
    _partition_by_slots,
    _match_slot,
)
from app.agents.scoring import _score_single_product, _compute_dynamic_weights
from app.models.decision import ScoredProduct
from app.models.product import NormalizedProduct
from app.models.requirement import ShoppingRequirement


def _make_scored(goods_id, title, price, total):
    """造一个 ScoredProduct，total 直接指定。"""
    p = NormalizedProduct(
        goods_id=goods_id, title=title, price=Decimal(price),
        original_price=Decimal(str(float(price) * 1.3)),
        coupon_amount=Decimal("5"), sales=500, brand="测试品牌",
        shop_type="tmall", shop_name="测试旗舰店",
        main_image="https://img.test.com/t.jpg",
        detail_url="https://detail.tmall.com/t",
        fetched_at=datetime.now(timezone.utc), dtitle=title,
        dsr_score=4.8, ship_score=4.7, service_score=4.6,
    )
    return ScoredProduct(product=p, aspects=[], total=total, rank=0)


# ---- 槽位匹配 ----

def test_match_slot_basic():
    assert _match_slot("户外露营帐篷防雨", "帐篷") is True
    assert _match_slot("蓝牙耳机降噪", "帐篷") is False


def test_partition_by_slots():
    scored = [
        _make_scored("001", "户外帐篷防雨", "199", 8.0),
        _make_scored("002", "睡袋加厚保暖", "99", 7.5),
        _make_scored("003", "便携炉具", "79", 7.0),
        _make_scored("004", "另一款帐篷", "299", 8.5),
    ]
    partition = _partition_by_slots(scored, ["帐篷", "睡袋", "炉具"])
    assert len(partition["帐篷"]) == 2
    assert len(partition["睡袋"]) == 1
    assert len(partition["炉具"]) == 1
    # 排序后 top-1 应该是高分那个
    assert partition["帐篷"][0].total == 8.5


# ---- 背包 DP ----

def test_knapsack_basic_combo():
    """三个槽位各一个候选，预算充足 → 应选中所有。"""
    scored = [
        _make_scored("001", "户外帐篷", "199", 8.0),
        _make_scored("002", "睡袋", "99", 7.5),
        _make_scored("003", "炉具", "79", 7.0),
    ]
    req = ShoppingRequirement(
        category="露营装备", combo=True, slots=["帐篷", "睡袋", "炉具"],
        budget_max=Decimal("500"),
    )
    schemes = knapsack_combo(scored, req)
    assert len(schemes) >= 1
    assert len(schemes[0]) == 3  # 三槽位各选一个
    total_price = sum(float(sp.product.price) for sp in schemes[0])
    assert total_price <= 500


def test_knapsack_budget_constraint():
    """预算不够买全部最贵的组合 → 应选次优搭配。"""
    scored = [
        _make_scored("001", "帐篷A", "299", 9.0),
        _make_scored("002", "帐篷B", "199", 7.0),
        _make_scored("003", "睡袋A", "159", 8.0),
        _make_scored("004", "睡袋B", "59", 6.0),
        _make_scored("005", "炉具", "79", 7.0),
    ]
    req = ShoppingRequirement(
        category="露营装备", combo=True, slots=["帐篷", "睡袋", "炉具"],
        budget_max=Decimal("340"),
    )
    schemes = knapsack_combo(scored, req)
    assert len(schemes) >= 1
    # 299+159+79=537 > 340, 199+59+79=337 <= 340
    total_price = sum(float(sp.product.price) for sp in schemes[0])
    assert total_price <= 340


def test_knapsack_missing_slot():
    """某槽位无候选 → 返回空列表。"""
    scored = [
        _make_scored("001", "帐篷", "199", 8.0),
        _make_scored("002", "炉具", "79", 7.0),
    ]
    req = ShoppingRequirement(
        category="露营装备", combo=True, slots=["帐篷", "睡袋", "炉具"],
        budget_max=Decimal("500"),
    )
    schemes = knapsack_combo(scored, req)
    assert schemes == []


def test_knapsack_non_combo_returns_empty():
    """非组合场景 → 返回空列表。"""
    scored = [_make_scored("001", "耳机", "99", 8.0)]
    req = ShoppingRequirement(category="蓝牙耳机", combo=False, budget_max=Decimal("200"))
    assert knapsack_combo(scored, req) == []


def test_knapsack_multiple_schemes():
    """有多个候选时应产出多套方案。"""
    scored = [
        _make_scored("001", "帐篷A", "199", 8.0),
        _make_scored("002", "帐篷B", "179", 7.5),
        _make_scored("003", "睡袋A", "99", 7.0),
        _make_scored("004", "睡袋B", "79", 6.5),
    ]
    req = ShoppingRequirement(
        category="露营装备", combo=True, slots=["帐篷", "睡袋"],
        budget_max=Decimal("400"),
    )
    schemes = knapsack_combo(scored, req)
    assert len(schemes) >= 2
    # 第 1 套总分应 >= 第 2 套
    t1 = sum(s.total for s in schemes[0])
    t2 = sum(s.total for s in schemes[1]) if len(schemes) > 1 else 0
    assert t1 >= t2


def test_combo_summary():
    scored = [
        _make_scored("001", "帐篷", "199", 8.0),
        _make_scored("002", "睡袋", "99", 7.0),
    ]
    req = ShoppingRequirement(
        category="露营装备", combo=True, slots=["帐篷", "睡袋"],
        budget_max=Decimal("300"),
    )
    schemes = knapsack_combo(scored, req)
    summary = generate_combo_summary(schemes, req)
    assert "方案1" in summary
    assert "298" in summary or "199" in summary


# ---- 动态权重 ----

def test_dynamic_weights_low_budget():
    """低预算时 price 权重应上调。"""
    req = ShoppingRequirement(category="耳机", budget_max=Decimal("100"))
    weights = _compute_dynamic_weights(req)
    assert weights["price"] > 0.25  # 上调了


def test_dynamic_weights_high_budget():
    """高预算时 price 权重不上调。"""
    req = ShoppingRequirement(category="耳机", budget_max=Decimal("2000"))
    weights = _compute_dynamic_weights(req)
    assert abs(weights["price"] - 0.25) < 0.01


def test_dynamic_weights_must_have():
    """有硬约束时 reputation 权重应上调。"""
    req = ShoppingRequirement(
        category="耳机", budget_max=Decimal("500"),
        must_have=["续航>20h"],
    )
    weights = _compute_dynamic_weights(req)
    assert weights["reputation"] > 0.25


def test_dynamic_weights_combo():
    """组合场景 coupon 权重应下调。"""
    req = ShoppingRequirement(
        category="露营装备", budget_max=Decimal("500"),
        combo=True, slots=["帐篷", "睡袋"],
    )
    weights = _compute_dynamic_weights(req)
    assert weights["coupon"] < 0.15


def test_dynamic_weights_normalized():
    """权重归一化后总和应为 1.0。"""
    req = ShoppingRequirement(
        category="耳机", budget_max=Decimal("50"),
        must_have=["降噪"], nice_to_have=["白色"], combo=True, slots=["耳机"],
    )
    weights = _compute_dynamic_weights(req)
    assert abs(sum(weights.values()) - 1.0) < 0.001
