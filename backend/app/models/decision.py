"""打分明细与决策报告。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.product import NormalizedProduct
from app.models.requirement import ShoppingRequirement


class AspectScore(BaseModel):
    aspect: str
    score: float
    weight: float
    evidence: str


class ScoredProduct(BaseModel):
    product: NormalizedProduct
    aspects: list[AspectScore]
    total: float
    rank: int


class DecisionReport(BaseModel):
    requirement: ShoppingRequirement
    recommendations: list[ScoredProduct] = []
    combos: list[list[ScoredProduct]] = []
    summary: str = ""
    reflection_notes: list[str] = []
    created_at: datetime
