"""需求结构，澄清 agent 的结构化输出。"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, field_validator


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

    @field_validator("must_have", "nice_to_have", "excluded", "slots", mode="before")
    @classmethod
    def _none_to_list(cls, v):
        # LLM 按 prompt 会对空列表输出 null，统一兜底成 []
        return [] if v is None else v
