"""
MCP 配置加载
从配置文件读取 MCP Server 连接配置
"""
import os
import logging
from typing import Optional, List, Literal, Dict
from pydantic import BaseModel, Field
import yaml

logger = logging.getLogger(__name__)

class MCPServerConfig(BaseModel):
    """单个 MCP Server 配置"""
    type: Literal["stdio", "sse"]
    # stdio 模式
    command: Optional[str] = None
    args: Optional[List[str]] = None
    # sse 模式
    url: Optional[str] = None
    api_key: Optional[str] = None

class MCPConfig(BaseModel):
    """MCP 整体配置"""
    use_mcp: bool = False
    servers: Dict[str, MCPServerConfig] = Field(default_factory=dict)

def load_mcp_config(config_path: str = "config/mcp.yaml") -> MCPConfig:
    """从 YAML 文件加载 MCP 配置，支持环境变量占位符"""
    # 读取文件
    with open(config_path, 'r', encoding='utf-8') as f:
        raw_config = yaml.safe_load(f)

    # 处理环境变量占位符 ${VAR_NAME}
    def substitute_env(value):
        if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
            env_var = value[2:-1]
            return os.environ.get(env_var, value)
        if isinstance(value, list):
            return [substitute_env(item) for item in value]
        if isinstance(value, dict):
            return {k: substitute_env(v) for k, v in value.items()}
        return value

    raw_config = substitute_env(raw_config)
    config = MCPConfig(**raw_config)

    logger.info(f"MCP config loaded: use_mcp={config.use_mcp}, servers={list(config.servers.keys())}")
    return config


# 全局配置实例，由应用启动时初始化
mcp_config: MCPConfig = load_mcp_config()
