"""M3 tests: reputation RAG mock + Skill loading + memory weight adjustment."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.skills.loader import detect_category, load_skill_prompt, enrich_requirement_prompt
from app.agents.memory_integration import apply_memory_weights


# ---- Skill system tests ----

def test_detect_category():
    assert detect_category("耳机") == "audio.md"
    assert detect_category("露营帐篷") == "outdoor.md"
    assert detect_category("机械键盘") == "digital.md"
    assert detect_category("no match here") is None


def test_load_skill_prompt():
    prompt = load_skill_prompt("耳机")
    assert len(prompt) > 0
    assert "音质" in prompt or "battery" in prompt.lower()

    prompt_unknown = load_skill_prompt("no match at all")
    assert prompt_unknown == ""


def test_enrich_requirement_prompt():
    enriched = enrich_requirement_prompt("耳机")
    assert len(enriched) > 0
    assert enrich_requirement_prompt("") == ""


# ---- Memory weight tests ----

@pytest.mark.asyncio
async def test_apply_memory_weights_no_user():
    weights = {"price": 0.25, "reputation": 0.25, "sales": 0.2, "coupon": 0.15, "brand": 0.15}
    result = await apply_memory_weights(weights, None, None)
    assert result == weights


@pytest.mark.asyncio
async def test_apply_memory_weights_pool_none():
    weights = {"price": 0.25, "reputation": 0.25, "sales": 0.2, "coupon": 0.15, "brand": 0.15}
    with patch("app.db.checkpointer.get_connection_pool", new_callable=AsyncMock, return_value=None):
        result = await apply_memory_weights(weights, "user-123", None)
    assert result == weights


@pytest.mark.asyncio
async def test_apply_memory_weights_normalizes():
    weights = {"price": 0.25, "reputation": 0.25, "sales": 0.2, "coupon": 0.15, "brand": 0.15}
    mock_pool = MagicMock()

    async def mock_read_facts(pool, user_id):
        return [{"category": "budget", "key": "budget_band", "value": "low", "confidence": 1.0, "source": "dialog"}]

    async def mock_recall(user_id, query, top_k=5):
        return [{"content": "budget sensitive", "importance": 0.8, "score": 0.9}]

    with patch("app.db.checkpointer.get_connection_pool", new_callable=AsyncMock, return_value=mock_pool), \
         patch("app.db.milvus.memory.read_profile_facts", side_effect=mock_read_facts), \
         patch("app.db.milvus.memory.recall_episodic_memories", side_effect=mock_recall):
        result = await apply_memory_weights(weights, "user-123", None)
    total = sum(result.values())
    assert abs(total - 1.0) < 0.001
    assert result["price"] > 0.25


# ---- Reputation RAG tests (mock Milvus) ----

@pytest.mark.asyncio
async def test_reputation_rag_hit():
    from app.agents.reputation import reputation_node
    from app.models.product import NormalizedProduct
    from app.models.requirement import ShoppingRequirement
    from decimal import Decimal
    from datetime import datetime, timezone

    products = [NormalizedProduct(
        goods_id="001", title="Sony WH-1000XM5",
        price=Decimal("1899"), main_image="", detail_url="",
        fetched_at=datetime.now(timezone.utc),
        dsr_score=4.8, ship_score=4.7, service_score=4.6)]
    state = {"products": products, "reputation_scores": {}, "messages": [],
             "requirement": ShoppingRequirement(category="earbuds", budget_max=Decimal("2000"))}
    mock_rag = {"overall": 8.5, "aspects": {"battery": 9.0}, "review_count": 3, "source": "rag"}
    with patch("app.agents.reputation.get_reputation_for_product", new_callable=AsyncMock, return_value=mock_rag):
        result = await reputation_node(state)
    assert result["reputation_scores"]["001"] == 8.5


@pytest.mark.asyncio
async def test_reputation_dsr_fallback():
    from app.agents.reputation import reputation_node
    from app.models.product import NormalizedProduct
    from app.models.requirement import ShoppingRequirement
    from decimal import Decimal
    from datetime import datetime, timezone

    products = [NormalizedProduct(
        goods_id="002", title="earbuds test",
        price=Decimal("99"), main_image="", detail_url="",
        fetched_at=datetime.now(timezone.utc),
        dsr_score=4.8, ship_score=4.7, service_score=4.6)]
    state = {"products": products, "reputation_scores": {}, "messages": [],
             "requirement": ShoppingRequirement(category="earbuds", budget_max=Decimal("200"))}
    mock_rag = {"overall": 0.0, "aspects": {}, "review_count": 0, "source": "dsr_fallback"}
    with patch("app.agents.reputation.get_reputation_for_product", new_callable=AsyncMock, return_value=mock_rag):
        result = await reputation_node(state)
    assert result["reputation_scores"]["002"] == pytest.approx(9.4, abs=0.1)


@pytest.mark.asyncio
async def test_reputation_exception_fallback():
    from app.agents.reputation import reputation_node
    from app.models.product import NormalizedProduct
    from decimal import Decimal
    from datetime import datetime, timezone

    products = [NormalizedProduct(
        goods_id="003", title="test",
        price=Decimal("50"), main_image="", detail_url="",
        fetched_at=datetime.now(timezone.utc),
        dsr_score=5.0, ship_score=5.0, service_score=5.0)]
    state = {"products": products, "reputation_scores": {}, "messages": []}
    with patch("app.agents.reputation.get_reputation_for_product", new_callable=AsyncMock, side_effect=Exception("fail")):
        result = await reputation_node(state)
    assert result["reputation_scores"]["003"] == pytest.approx(10.0, abs=0.1)


# ---- Module import tests ----

def test_collections_import():
    from app.db.milvus.collections import init_collections, drop_all_collections
    assert callable(init_collections)

def test_milvus_client_import():
    from app.db.milvus.client import get_milvus_client, get_embedding, get_embeddings
    assert callable(get_milvus_client)
