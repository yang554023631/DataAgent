"""
CoT 分析类型 Skill 模块
- 按分析类型拆分 Skill，每个 Skill 只带当前分析类型的 Prompt
- 减少 Token 浪费，提升性能
"""
from .skill_registry import cot_skill_registry, get_cot_skill
from .base_cot_skill import BaseCotSkill

__all__ = [
    "cot_skill_registry",
    "get_cot_skill",
    "BaseCotSkill",
]
