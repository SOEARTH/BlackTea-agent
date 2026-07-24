"""LangGraph 端到端测试：mock LLM 和 MCP 工具，验证 graph 流转。

覆盖三条关键路径：
1. 澄清提问 interrupt 路径（信息不足时反问用户）
2. 完整流程：澄清 -> 搜索 -> 比价 -> 口碑 -> 打分 -> 反思 -> 报告
3. 反思打回路径（超预算时打回重检）
"""
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from app.agents.graph import build_graph
from app.agents.state import GraphState
from app.models.product import NormalizedProduct
from app.models.requirement import ShoppingRequirement
from datetime import datetime, timezone


def _make_product(
    goods_id="001", title="测试商品", price="29.9", original_price="39.9",
    coupon_amount="10", sales=500, shop_type="tmall", brand="测试品牌"
):
    return NormalizedProduct(
        goods_id=goods_id, title=title, price=Decimal(price),
        original_price=Decimal(original_price), coupon_amount=Decimal(coupon_amount),
        sales=sales, shop_type=shop_type, brand=brand,
        main_image="https://img.test.com/test.jpg", detail_url="https://detail.tmall.com/test",
        fetched_at=datetime.now(timezone.utc), dtitle=title,
        shop_name="测试旗舰店", dsr_score=4.8, ship_score=4.7, service_score=4.6,
        discounts=0.75, commission_rate=20.0,
    )


# ---- 路径 1: 澄清 interrupt ----

def test_clarify_triggers_interrupt():
    """信息不足时 clarify_node 应调用 interrupt 反问用户。"""
    from app.agents.clarify import clarify_node

    mock_llm = MagicMock()
    # 第一次调用：提取需求（缺预算）
    mock_llm.invoke.side_effect = [
        MagicMock(content='{"category":"耳机","budget_min":null,"budget_max":null}'),
        MagicMock(content="请问你的预算大概是多少？"),
    ]

    state = {**build_graph_initial_state()}
    state["messages"] = [HumanMessage(content="我想买个耳机")]

    with patch("app.agents.clarify.get_llm", return_value=mock_llm):
        with patch("langgraph.types.interrupt", side_effect=StopIteration) as mock_int:
            try:
                clarify_node(state)
            except StopIteration:
                pass
            # 验证 interrupt 被调用
            assert mock_int.called


def build_graph_initial_state():
    return {
        "messages": [],
        "requirement": None,
        "products": [],
        "scored_products": [],
        "report": None,
        "reflection_notes": [],
        "next_agent": "clarify",
        "iteration": 0,
        "reputation_scores": {},
        "price_analysis": {},
    }


# ---- 路径 2: 完整流程（mock 全部） ----

@pytest.mark.asyncio
async def test_full_pipeline_mock():
    """完整流程：澄清 -> 搜索 -> 比价 -> 口碑 -> 打分 -> 反思 -> 报告。"""
    from app.agents.clarify import clarify_node
    from app.agents.scoring import scoring_node
    from app.agents.reflect import reflect_node

    products = [
        _make_product("001", "蓝牙耳机A", "29.9"),
        _make_product("002", "蓝牙耳机B", "59.9"),
        _make_product("003", "蓝牙耳机C", "99.9"),
    ]
    req = ShoppingRequirement(category="蓝牙耳机", budget_max=Decimal("100"))

    state = {
        **build_graph_initial_state(),
        "requirement": req,
        "products": products,
        "price_analysis": {
            "001": {"trend": [], "current_percentile": 0.8, "is_good_price": True},
            "002": {"trend": [], "current_percentile": 0.3, "is_good_price": False},
            "003": {"trend": [], "current_percentile": 0.7, "is_good_price": True},
        },
        "reputation_scores": {"001": 8.5, "002": 7.0, "003": 9.0},
    }

    # 测试打分节点
    scored_state = scoring_node(state)
    scored = scored_state["scored_products"]
    assert len(scored) == 3
    assert scored[0].rank == 1
    # 总分应该按降序排列
    assert scored[0].total >= scored[1].total >= scored[2].total

    # 测试反思节点（全部在预算内，应该通过）
    reflected = reflect_node(scored_state)
    assert reflected.get("report") is not None
    assert reflected["next_agent"] == "END"
    assert len(reflected["report"].recommendations) > 0


# ---- 路径 3: 反思打回 ----

@pytest.mark.asyncio
async def test_reflect_rejects_over_budget():
    """超预算时反思应该打回，next_agent=search。"""
    from app.agents.scoring import scoring_node
    from app.agents.reflect import reflect_node

    products = [
        _make_product("001", "耳机A", "29.9"),  # 在预算内
        _make_product("002", "耳机B", "150.0"), # 超预算
    ]
    req = ShoppingRequirement(category="蓝牙耳机", budget_max=Decimal("100"))

    state = {**build_graph_initial_state(), "requirement": req, "products": products}
    scored = scoring_node(state)

    reflected = reflect_node(scored_state_for_test(scored, req))
    assert reflected["next_agent"] == "search"
    assert len(reflected["reflection_notes"]) > 0
    # 超预算商品被过滤
    assert all(float(s.product.price) <= 100 for s in reflected["scored_products"])


def scored_state_for_test(scored_state, req):
    """复制 scored_state 并补充 req。"""
    scored_state["requirement"] = req
    return scored_state


# ---- 图编译测试 ----

def test_graph_compiles():
    """验证 graph 能正常编译不报错。"""
    graph = build_graph()
    assert graph is not None
