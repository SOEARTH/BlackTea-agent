"""Skill 系统加载器：按品类动态注入选购方法论 prompt + 工具子集。

渐进披露：supervisor/clarify 识别品类 → 加载对应 SKILL.md（方法论 prompt）
→ 只挂载该品类需要的工具子集，而非一次性塞入全部上下文。

设计参考：Codex Skill 的 progressive disclosure 模式，
但适配到本项目：每个品类一个 .md 文件，内容是选购方法论 + 推荐工具。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 品类 → 文件名 映射（关键词匹配，先到先得）
CATEGORY_FILES: dict[str, str] = {
    "耳机": "audio.md",
    "音箱": "audio.md",
    "麦克风": "audio.md",
    "露营": "outdoor.md",
    "帐篷": "outdoor.md",
    "睡袋": "outdoor.md",
    "背包": "outdoor.md",
    "键盘": "digital.md",
    "鼠标": "digital.md",
    "显示器": "digital.md",
    "笔记本": "digital.md",
    "显卡": "digital.md",
    "手机": "digital.md",
    "平板": "digital.md",
}

# 默认 skill（品类未命中时）
DEFAULT_SKILL = "default.md"

SKILLS_DIR = Path(__file__).parent / "categories"


def detect_category(user_category: str) -> str | None:
    """从用户输入的品类名匹配到 skill 文件名。

    Returns:
        skill 文件名（如 "audio.md"），未匹配返回 None。
    """
    if not user_category:
        return None

    cat_lower = user_category.lower()
    for keyword, filename in CATEGORY_FILES.items():
        if keyword in cat_lower:
            return filename
    return None


def load_skill_prompt(user_category: str) -> str:
    """加载品类的 SKILL.md 内容作为 prompt 注入。

    如果品类未命中或文件不存在，返回空字符串（不影响主流程）。
    """
    filename = detect_category(user_category)
    if not filename:
        return ""  # ???????????

    skill_path = SKILLS_DIR / filename
    if not skill_path.exists():
        logger.warning("Skill 文件不存在: %s", skill_path)
        return ""

    try:
        content = skill_path.read_text(encoding="utf-8")
        logger.info("加载 Skill: %s (品类=%s)", filename, user_category)
        return content
    except Exception as e:
        logger.warning("读取 Skill 文件失败: %s", e)
        return ""


def get_tool_subset(user_category: str) -> list[str] | None:
    """根据品类返回推荐的 MCP 工具子集名称。

    简化版：所有品类用同一套工具（search_goods + get_price_trend），
    M4 可扩展为品类特定工具子集。

    Returns:
        工具名列表，None 表示用全部工具。
    """
    # 目前不区分工具子集，M4 扩展
    return None


def enrich_requirement_prompt(user_category: str) -> str:
    """生成品类方法论 prompt 片段，注入到 clarify 或 search 节点。

    回传格式：一段 Markdown 文本，供 LLM 参考。
    """
    skill_content = load_skill_prompt(user_category)
    if not skill_content:
        return ""
    return f"\n\n## 选购方法论参考（{user_category}）\n\n{skill_content}\n"
