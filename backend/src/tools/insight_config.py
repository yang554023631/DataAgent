"""
洞察规则配置管理
支持从YAML配置文件读取规则阈值和开关配置
"""
import os
import yaml
from typing import Dict, Any, Optional

# 配置文件路径
CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "config",
    "insight_rules.yaml"
)


class InsightConfig:
    """洞察规则配置类"""

    _instance: Optional['InsightConfig'] = None
    _config: Dict[str, Any] = {}

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self) -> None:
        """加载配置文件"""
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    self._config = yaml.safe_load(f) or {}
            except Exception as e:
                print(f"警告: 加载配置文件失败: {e}，使用默认配置")
                self._config = self._get_default_config()
        else:
            print(f"警告: 配置文件不存在: {CONFIG_PATH}，使用默认配置")
            self._config = self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """默认配置（与配置文件一致）"""
        return {
            "highlight_rules": {
                "A01_high_ctr": {"enabled": True, "name": "CTR表现优异", "percentile": 80},
                "A02_high_cvr": {"enabled": True, "name": "CVR表现优异", "percentile": 80},
                "A03_low_cpc": {"enabled": True, "name": "CPC成本优势显著", "percentile": 20},
                "A07_cvr_contrast": {"enabled": True, "name": "CVR反差亮点", "percentile": 85},
                "A09_ctr_low_cvr_high": {"enabled": True, "name": "精准定向潜力股",
                                         "ctr_percentile": 15, "cvr_percentile": 85},
            },
            "problem_rules": {
                "P01_low_cvr": {"enabled": True, "name": "CVR转化低下", "percentile": 20},
                "P03_high_cpa": {"enabled": True, "name": "CPA转化成本过高", "percentile": 80},
                "P05_ctr_anomaly": {"enabled": True, "name": "CTR异常波动",
                                    "low_percentile": 5, "high_percentile": 95},
            },
            "timing_rules": {
                "P02_creative_fatigue": {"enabled": True, "name": "创意疲劳衰减",
                                         "decline_days": 3, "decline_threshold": 0.2},
            },
            "special_rules": {}
        }

    def reload(self) -> None:
        """重新加载配置"""
        self._load_config()

    def get(self, key_path: str, default: Any = None) -> Any:
        """获取配置，支持点号路径，如 'highlight_rules.A01_high_ctr.percentile' """
        keys = key_path.split('.')
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def is_rule_enabled(self, rule_key: str) -> bool:
        """检查规则是否启用"""
        # 在各个规则分类中查找
        for category in ['highlight_rules', 'problem_rules', 'timing_rules', 'special_rules']:
            if rule_key in self._config.get(category, {}):
                return self._config[category][rule_key].get('enabled', True)
        return True  # 默认启用

    def get_highlight_rule(self, rule_id: str) -> Dict[str, Any]:
        """获取亮点规则配置"""
        rules = self._config.get('highlight_rules', {})
        for key, rule in rules.items():
            if key.startswith(rule_id) or rule.get('name', '').startswith(rule_id):
                return rule
        return {}

    def get_problem_rule(self, rule_id: str) -> Dict[str, Any]:
        """获取问题规则配置"""
        rules = self._config.get('problem_rules', {})
        for key, rule in rules.items():
            if key.startswith(rule_id) or rule.get('name', '').startswith(rule_id):
                return rule
        return {}

    def get_percentile(self, rule_id: str, default: int = 80) -> int:
        """获取规则的百分位阈值"""
        # 先查找亮点规则
        h_rule = self.get_highlight_rule(rule_id)
        if h_rule and 'percentile' in h_rule:
            return h_rule['percentile']

        # 再查找问题规则
        p_rule = self.get_problem_rule(rule_id)
        if p_rule and 'percentile' in p_rule:
            return p_rule['percentile']

        return default

    def get_percentiles(self, rule_id: str) -> Dict[str, int]:
        """获取规则的多个百分位阈值（用于A09、P05等多阈值规则）"""
        result = {}

        h_rule = self.get_highlight_rule(rule_id)
        if h_rule:
            for k, v in h_rule.items():
                if 'percentile' in k:
                    result[k] = v

        p_rule = self.get_problem_rule(rule_id)
        if p_rule:
            for k, v in p_rule.items():
                if 'percentile' in k:
                    result[k] = v

        return result


# 全局配置实例
insight_config = InsightConfig()
