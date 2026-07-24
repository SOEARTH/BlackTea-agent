"""需求结构，澄清 agent 的结构化输出。"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class ShoppingRequirement(BaseModel):
    category: str
    scenario: str | None = None
    budget_min: Decimal | None = None
    budget_max: Decimal | None = None
    must_have: list[str] = []
    nice_to_have: list[str] = []
    excluded: list[str] = []
    combo: bool = False
    slots: list[str] = []
