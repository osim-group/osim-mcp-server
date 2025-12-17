"""
OSIM MCP Server - 基于 FastMCP 的 Model Context Protocol 服务器
提供 OSIM (Open Security Information Model) 数据标准 schema 的查询和访问能力
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

from fastmcp import FastMCP

from loader import DataStandardLoader

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建 FastMCP 服务器实例
mcp = FastMCP(
    "OSIM MCP Server",
    instructions="This server provides data standard schema tools and resources for OSIM (Open Security Information Model)"
)

# 初始化数据标准加载器
loader = DataStandardLoader()


@mcp.tool()
def list_schema_names() -> List[str]:
    """
    列出所有可用的数据标准 schema 名称。
    
    返回名称列表，格式为 {group}.{category}.{title}（例如：log.network_session_audit.http_audit）。
    为了避免上下文过长，此工具只返回名称，不包含描述信息。
    如需获取描述，请使用 describe_schemas 工具。
    
    Returns:
        List[str]: schema 名称列表，格式为 {group}.{category}.{title}
    """
    try:
        names = loader.list_schema_names()
        logger.info(f"列出 {len(names)} 个 schema 名称")
        return names
    except Exception as e:
        logger.error(f"列出 schema 名称失败: {e}", exc_info=True)
        return []


@mcp.tool()
def describe_schemas(schema_names: List[str]) -> Dict[str, str]:
    """
    获取指定 schema 名称列表的描述信息。
    
    参数 schema_names 是 schema 名称列表，格式为 {group}.{category}.{title}
    （例如：["log.network_session_audit.http_audit", "alert.network_attack.apt_attack"]）。
    返回字典，键为 schema 名称，值为描述信息，方便理解应该使用哪个 schema。
    
    Args:
        schema_names: schema 名称列表，格式为 {group}.{category}.{title}
    
    Returns:
        Dict[str, str]: 字典，键为 schema 名称，值为描述信息
    """
    try:
        descriptions = loader.describe_schemas(schema_names)
        logger.info(f"获取 {len(descriptions)} 个 schema 的描述信息")
        return descriptions
    except Exception as e:
        logger.error(f"获取 schema 描述失败: {e}", exc_info=True)
        return {}


@mcp.tool()
def get_schema(schema_path: str) -> Dict[str, Any]:
    """
    获取指定 schema 的字段定义。
    
    参数 schema_path 格式为 {group}.{category}.{title}
    （例如：log.network_session_audit.http_audit），可以从 list_schema_names 中获取所有可用的 schema 名称。
    返回字段定义字典，包含字段名、标签、类型、要求、描述等信息。
    
    Args:
        schema_path: schema 路径，格式为 {group}.{category}.{title}
    
    Returns:
        Dict[str, Any]: 字段定义字典，包含字段名、标签、类型、要求、描述等信息
    """
    try:
        schema = loader.get_schema(schema_path)
        if schema is None:
            logger.warning(f"找不到 schema: {schema_path}")
            return {"error": f"找不到 schema: {schema_path}"}
        logger.info(f"获取 schema 字段定义: {schema_path}")
        return schema
    except Exception as e:
        logger.error(f"获取 schema 字段定义失败: {e}", exc_info=True)
        return {"error": f"获取 schema 字段定义失败: {str(e)}"}


# 注册资源处理器
# FastMCP 使用 resource 装饰器注册资源
# URI 模板: data-standard://{group}/{category}/{title}
# 注意：函数参数必须与 URI 路径参数匹配
@mcp.resource("data-standard://{group}/{category}/{title}")
def get_data_standard_resource(group: str, category: str, title: str) -> str:
    """
    获取数据标准 schema 文件内容。
    
    资源 URI 格式: data-standard://{group}/{category}/{title}
    例如: data-standard://log/network_session_audit/http_audit
    
    Args:
        group: 分组（例如：log, alert, asset）
        category: 分类（例如：network_session_audit, network_attack）
        title: 标题（例如：http_audit, apt_attack）
    
    Returns:
        str: JSON 格式的完整 schema 文件内容
    """
    try:
        content = loader.get_schema_resource(group, category, title)
        logger.info(f"获取 schema 资源: {group}/{category}/{title}")
        return content
    except Exception as e:
        logger.error(f"获取 schema 资源失败: {e}", exc_info=True)
        error_msg = json.dumps({"error": f"获取 schema 资源失败: {str(e)}"}, ensure_ascii=False)
        return error_msg


def main():
    """主入口函数，用于 console_scripts"""
    mcp.run()


if __name__ == "__main__":
    # 运行服务器，默认使用 STDIO 传输
    main()

