"""agent 共用工具：LLM 实例 + JSON 解析。"""
from __future__ import annotations

import json

from app.config import settings


def get_llm(temperature: float = 0):
    """获取 ChatOpenAI 实例（OpenAI 兼容接口）。"""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=settings.model_name,
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base,
        temperature=temperature,
    )


def parse_json_response(text: str) -> dict:
    """从 LLM 输出中提取 JSON（兼容 markdown 代码块包裹）。"""
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return {}
