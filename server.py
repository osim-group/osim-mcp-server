"""
OSIM MCP Server - 基于 FastMCP 的 Model Context Protocol 服务器
提供 OSIM (Open Security Information Model) 数据标准 schema 的查询和访问能力

功能特性：
- 提供 schema 列表、描述、字段定义等查询工具
- 支持通过资源 URI 访问 schema 文件内容
- 启动后异步检查并更新 schemas（支持版本号判断）
"""
import asyncio
import functools
import inspect
import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

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

# 是否启用自动更新（可通过环境变量控制）
AUTO_UPDATE_ENABLED = os.environ.get("OSIM_AUTO_UPDATE", "true").lower() in ("true", "1", "yes")

# 更新检查超时时间（秒）
UPDATE_CHECK_TIMEOUT = float(os.environ.get("OSIM_UPDATE_TIMEOUT", "30"))


async def check_and_update_schemas():
    """
    异步检查并更新 schemas。
    
    在服务器启动后后台运行，不阻塞主服务。
    更新完成后自动重新加载 loader。
    """
    if not AUTO_UPDATE_ENABLED:
        logger.info("自动更新已禁用 (设置 OSIM_AUTO_UPDATE=true 启用)")
        return
    
    logger.info("开始后台检查 schemas 更新...")
    
    try:
        from version_manager import VersionManager
        from update_schemas import do_update_async
        
        version_manager = VersionManager()
        
        # 检查是否有更新
        need_update, local_ver, remote_ver = await version_manager.check_update_available(
            timeout=UPDATE_CHECK_TIMEOUT
        )
        
        if not need_update:
            if local_ver:
                logger.info(f"Schemas 已是最新版本: {local_ver}")
            return
        
        logger.info(f"发现新版本，准备更新: {local_ver or '无'} -> {remote_ver}")
        
        # 定义更新完成回调
        def on_update_complete(success: bool):
            if success:
                logger.info("Schemas 更新成功，重新加载...")
                loader.reload()
                logger.info("Schemas 重新加载完成")
            else:
                logger.warning("Schemas 更新失败，继续使用现有版本")
        
        # 执行异步更新
        await do_update_async(force=False, on_complete=on_update_complete)
        
    except ImportError as e:
        logger.warning(f"无法导入更新模块: {e}")
    except Exception as e:
        logger.error(f"检查更新时发生错误: {e}", exc_info=True)


def schedule_update_check():
    """
    调度更新检查任务。
    
    在服务器启动后延迟执行，避免阻塞启动过程。
    """
    async def delayed_check():
        # 延迟 2 秒后开始检查，让服务器先完成启动
        await asyncio.sleep(2)
        await check_and_update_schemas()
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果事件循环已在运行，创建任务
            asyncio.create_task(delayed_check())
        else:
            # 否则在新的事件循环中运行
            loop.run_until_complete(delayed_check())
    except RuntimeError:
        # 没有事件循环时，创建新的
        asyncio.run(delayed_check())


@mcp.tool()
def list_schema_names() -> List[Dict[str, Any]]:
    """
    列出所有可用的数据标准 schema 名称。
    
    返回对象列表，每个对象包含：
    - title: schema 名称，格式为 {group}.{category}.{title}（例如：log.network_session_audit.http_audit）
    - label: schema 的英文标签（来自 schema 文件）
    - label_{locale}: schema 的各语言标签（动态生成，根据 i18n 目录下的文件自动生成）
      例如：如果存在 zh_CN.json，则会有 label_zh_CN 字段；如果存在 en_US.json，则会有 label_en_US 字段
    
    如需获取描述，请使用 describe_schemas 工具。
    
    Returns:
        List[Dict[str, Any]]: schema 信息列表，每个对象包含 title、label 和动态的 label_{locale} 字段
    """
    try:
        schemas = loader.list_schema_names()
        logger.info(f"列出 {len(schemas)} 个 schema 名称")
        return schemas
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


@mcp.tool()
def get_schema_version() -> Dict[str, Any]:
    """
    获取当前 schemas 的版本信息。
    
    返回包含本地版本号和更新状态的字典。
    
    Returns:
        Dict[str, Any]: 包含 version（版本号）和 auto_update_enabled（是否启用自动更新）的字典
    """
    try:
        from version_manager import VersionManager
        
        version_manager = VersionManager()
        local_version = version_manager.get_local_version()
        
        return {
            "version": str(local_version) if local_version else "unknown",
            "auto_update_enabled": AUTO_UPDATE_ENABLED,
            "update_timeout": UPDATE_CHECK_TIMEOUT
        }
    except Exception as e:
        logger.error(f"获取版本信息失败: {e}", exc_info=True)
        return {
            "version": "unknown",
            "auto_update_enabled": AUTO_UPDATE_ENABLED,
            "error": str(e)
        }


@mcp.tool()
def get_dictionaries() -> Dict[str, Any]:
    """
    获取 dictionaries.json 文件内容。
    
    返回 OSIM 数据标准中定义的字典项，包含字段名、标签、描述、类型等信息。
    这些字典项定义了数据标准中使用的通用字段定义。
    
    Returns:
        Dict[str, Any]: dictionaries.json 的完整内容，如果读取失败则返回包含错误信息的字典
    """
    try:
        dictionaries = loader.get_dictionaries()
        logger.info("获取 dictionaries.json 内容")
        return dictionaries
    except Exception as e:
        logger.error(f"获取 dictionaries.json 失败: {e}", exc_info=True)
        return {"error": f"获取 dictionaries.json 失败: {str(e)}"}


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
    # 在服务器启动前调度更新检查
    # 注意：FastMCP 会在 run() 中启动事件循环
    # 我们需要在 FastMCP 的事件循环启动后再调度任务
    
    # 使用 lifespan 或 startup 事件来调度更新检查
    # 由于 FastMCP 可能不直接支持 lifespan，我们使用替代方案
    
    import threading
    
    def background_update_check():
        """在后台线程中运行更新检查"""
        import time
        time.sleep(3)  # 等待服务器启动
        
        try:
            # 创建新的事件循环用于异步更新
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(check_and_update_schemas())
            loop.close()
        except Exception as e:
            logger.error(f"后台更新检查失败: {e}", exc_info=True)
    
    if AUTO_UPDATE_ENABLED:
        # 启动后台更新检查线程
        update_thread = threading.Thread(target=background_update_check, daemon=True)
        update_thread.start()
        logger.info("后台更新检查已调度")
    
    mcp.run()


if __name__ == "__main__":
    # 运行服务器，默认使用 STDIO 传输
    main()
