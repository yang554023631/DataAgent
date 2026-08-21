"""
CoT 分析 Skill 注册表
支持懒加载，启动时只注册工厂，第一次用到才实例化
"""
from typing import Dict, Callable
from .base_cot_skill import BaseCotSkill


class CotSkillRegistry:
    """CoT 分析 Skill 注册表，支持懒加载"""

    def __init__(self):
        self._instances: Dict[str, BaseCotSkill] = {}
        self._lazy_factories: Dict[str, Callable[[], BaseCotSkill]] = {}

    def register_lazy(self, analysis_type: str, factory: Callable[[], BaseCotSkill]) -> None:
        """注册懒加载 Skill

        Args:
            analysis_type: 分析类型标识
            factory: 创建 Skill 实例的工厂函数
        """
        self._lazy_factories[analysis_type] = factory

    def get(self, analysis_type: str) -> BaseCotSkill:
        """获取 Skill 实例，懒加载首次调用才实例化

        Args:
            analysis_type: 分析类型标识

        Returns:
            BaseCotSkill: Skill 实例

        Raises:
            ValueError: 如果找不到对应分析类型的 Skill
        """
        if analysis_type in self._instances:
            return self._instances[analysis_type]

        if analysis_type in self._lazy_factories:
            skill = self._lazy_factories[analysis_type]()
            self._instances[analysis_type] = skill
            return skill

        raise ValueError(f"CoT Skill for analysis_type '{analysis_type}' not found")


# 全局单例注册表
cot_skill_registry = CotSkillRegistry()


def get_cot_skill(analysis_type: str) -> BaseCotSkill:
    """便捷函数：根据分析类型获取对应的 Skill

    Args:
        analysis_type: 分析类型标识

    Returns:
        BaseCotSkill: Skill 实例
    """
    return cot_skill_registry.get(analysis_type)


# ========== 懒加载注册所有分析类型 Skill ==========
# 注意：使用 lambda 延迟导入和实例化，启动时不加载所有模块
cot_skill_registry.register_lazy(
    "time_trend",
    lambda: __import__("src.skills.cot.time_trend_cot", fromlist=["TimeTrendCotSkill"]).TimeTrendCotSkill()
)
cot_skill_registry.register_lazy(
    "entity_table",
    lambda: __import__("src.skills.cot.entity_table_cot", fromlist=["EntityTableCotSkill"]).EntityTableCotSkill()
)
cot_skill_registry.register_lazy(
    "period_comparison",
    lambda: __import__("src.skills.cot.period_comparison_cot", fromlist=["PeriodComparisonCotSkill"]).PeriodComparisonCotSkill()
)
cot_skill_registry.register_lazy(
    "audience_distribution",
    lambda: __import__("src.skills.cot.audience_distribution_cot", fromlist=["AudienceDistributionCotSkill"]).AudienceDistributionCotSkill()
)
cot_skill_registry.register_lazy(
    "summary",
    lambda: __import__("src.skills.cot.summary_cot", fromlist=["SummaryCotSkill"]).SummaryCotSkill()
)
