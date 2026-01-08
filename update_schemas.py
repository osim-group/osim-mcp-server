#!/usr/bin/env python3
"""
从 GitHub 仓库同步最新的 OSIM schemas

功能：
- 支持版本号检查，只在有新版本时更新
- 支持强制更新
- 支持异步更新（用于服务器启动后后台更新）

使用方法:
    python update_schemas.py [--force]

或者直接运行:
    ./update_schemas.py
"""
import asyncio
import json
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# GitHub 仓库配置
SCHEMA_REPO = "osim-group/osim-schema"
SCHEMA_BRANCH = "main"
SCHEMA_REPO_URL = f"https://github.com/{SCHEMA_REPO}.git"

# 本地 osim-schema 目录（整个仓库）
LOCAL_OSIM_SCHEMA_DIR = Path(__file__).parent / "osim-schema"


def check_git_available() -> bool:
    """检查 git 是否可用"""
    try:
        subprocess.run(
            ["git", "--version"],
            capture_output=True,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def clone_repo_to_temp() -> Optional[Path]:
    """克隆整个仓库到临时目录并返回仓库根目录路径"""
    temp_dir = tempfile.mkdtemp(prefix="osim-schema-")
    repo_dir = Path(temp_dir) / "osim-schema"
    
    try:
        logger.info(f"正在克隆仓库 {SCHEMA_REPO_URL}...")
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", SCHEMA_BRANCH, SCHEMA_REPO_URL, str(repo_dir)],
            check=True,
            capture_output=True,
            text=True
        )
        
        if not repo_dir.exists():
            logger.error(f"克隆后的仓库目录不存在: {repo_dir}")
            return None
        
        # 验证关键目录和文件是否存在
        schemas_path = repo_dir / "schemas"
        version_file = repo_dir / "version.json"
        
        if not schemas_path.exists():
            logger.warning(f"仓库中找不到 schemas 目录: {schemas_path}")
        if not version_file.exists():
            logger.warning(f"仓库中找不到 version.json 文件: {version_file}")
        
        return repo_dir
    except subprocess.CalledProcessError as e:
        logger.error(f"克隆仓库失败: {e}")
        if e.stdout:
            logger.error(f"stdout: {e.stdout}")
        if e.stderr:
            logger.error(f"stderr: {e.stderr}")
        return None
    except Exception as e:
        logger.error(f"克隆仓库时发生错误: {e}", exc_info=True)
        return None


def backup_existing_repo() -> Optional[Path]:
    """备份现有的 osim-schema 目录"""
    if not LOCAL_OSIM_SCHEMA_DIR.exists():
        return None
    
    backup_dir = LOCAL_OSIM_SCHEMA_DIR.parent / f"osim-schema.backup"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    
    logger.info(f"备份现有 osim-schema 到 {backup_dir}...")
    shutil.copytree(LOCAL_OSIM_SCHEMA_DIR, backup_dir)
    return backup_dir


def update_schemas(source_repo: Path, new_version: Optional[str] = None) -> bool:
    """
    更新本地 osim-schema 目录（整个仓库）
    
    Args:
        source_repo: 源仓库根目录路径
        new_version: 新版本号，如果提供则保存到本地版本文件
    
    Returns:
        是否更新成功
    """
    backup_dir = None
    try:
        # 备份现有 osim-schema 目录
        backup_dir = backup_existing_repo()
        
        # 删除现有 osim-schema 目录
        if LOCAL_OSIM_SCHEMA_DIR.exists():
            logger.info(f"删除现有 osim-schema 目录: {LOCAL_OSIM_SCHEMA_DIR}")
            shutil.rmtree(LOCAL_OSIM_SCHEMA_DIR)
        
        # 复制整个仓库
        logger.info(f"复制新的 osim-schema 从 {source_repo} 到 {LOCAL_OSIM_SCHEMA_DIR}...")
        shutil.copytree(source_repo, LOCAL_OSIM_SCHEMA_DIR)
        
        # 保存版本号（如果提供了新版本号，否则从复制的 version.json 中读取）
        if new_version:
            from version_manager import VersionManager
            version_manager = VersionManager()
            version_manager.save_local_version(new_version)
        else:
            # 尝试从复制的 version.json 中读取版本号
            version_file = LOCAL_OSIM_SCHEMA_DIR / "version.json"
            if version_file.exists():
                try:
                    with open(version_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        version = data.get("version")
                        if version:
                            from version_manager import VersionManager
                            version_manager = VersionManager()
                            version_manager.save_local_version(version)
                except Exception as e:
                    logger.warning(f"无法从 version.json 读取版本号: {e}")
        
        # 删除备份（如果更新成功）
        if backup_dir and backup_dir.exists():
            logger.info(f"删除备份目录: {backup_dir}")
            shutil.rmtree(backup_dir)
        
        logger.info("OSIM Schema 更新成功！")
        return True
    except Exception as e:
        logger.error(f"更新 osim-schema 失败: {e}", exc_info=True)
        # 尝试恢复备份
        if backup_dir and backup_dir.exists() and not LOCAL_OSIM_SCHEMA_DIR.exists():
            logger.info("尝试恢复备份...")
            shutil.copytree(backup_dir, LOCAL_OSIM_SCHEMA_DIR)
        return False


def verify_schemas() -> bool:
    """验证 osim-schema 目录是否有效"""
    if not LOCAL_OSIM_SCHEMA_DIR.exists():
        logger.error(f"OSIM Schema 目录不存在: {LOCAL_OSIM_SCHEMA_DIR}")
        return False
    
    # 检查 schemas 目录是否存在
    schemas_dir = LOCAL_OSIM_SCHEMA_DIR / "schemas"
    if not schemas_dir.exists():
        logger.error(f"Schemas 目录不存在: {schemas_dir}")
        return False
    
    # 检查是否有 JSON 文件
    json_files = list(schemas_dir.rglob("*.json"))
    if not json_files:
        logger.error("Schemas 目录中没有找到 JSON 文件")
        return False
    
    logger.info(f"找到 {len(json_files)} 个 JSON 文件")
    
    # 检查 version.json 是否存在
    version_file = LOCAL_OSIM_SCHEMA_DIR / "version.json"
    if not version_file.exists():
        logger.warning("未找到 version.json 文件")
    else:
        logger.info(f"找到 version.json: {version_file}")
    
    return True


def do_update(force: bool = False, on_complete: Optional[Callable[[bool], None]] = None) -> bool:
    """
    执行 schemas 更新
    
    Args:
        force: 是否强制更新（忽略版本检查）
        on_complete: 更新完成后的回调函数
    
    Returns:
        是否更新成功
    """
    from version_manager import VersionManager
    
    version_manager = VersionManager()
    new_version = None
    
    # 检查版本
    if not force:
        need_update, local_ver, remote_ver = version_manager.check_update_available_sync()
        
        if not need_update:
            if local_ver:
                logger.info(f"当前版本 {local_ver} 已是最新，无需更新")
            if on_complete:
                on_complete(False)
            return False
        
        if remote_ver:
            new_version = remote_ver.version
            logger.info(f"准备更新: {local_ver or '无'} -> {remote_ver}")
    else:
        # 强制更新时也获取远程版本号
        remote_ver = version_manager.get_remote_version_sync()
        if remote_ver:
            new_version = remote_ver.version
        logger.info("强制更新模式")
    
    # 检查 git 是否可用
    if not check_git_available():
        logger.error("未找到 git 命令，请先安装 git")
        if on_complete:
            on_complete(False)
        return False
    
    # 克隆仓库到临时目录
    source_repo = clone_repo_to_temp()
    if source_repo is None:
        logger.error("无法获取 osim-schema 仓库，更新失败")
        if on_complete:
            on_complete(False)
        return False
    
    try:
        # 更新本地 osim-schema 目录
        if not update_schemas(source_repo, new_version):
            logger.error("更新 osim-schema 失败")
            if on_complete:
                on_complete(False)
            return False
        
        # 验证更新结果
        if not verify_schemas():
            logger.error("验证 osim-schema 失败")
            if on_complete:
                on_complete(False)
            return False
        
        logger.info("OSIM Schema 更新完成！")
        if on_complete:
            on_complete(True)
        return True
    finally:
        # 清理临时目录
        temp_dir = source_repo.parent
        if temp_dir.exists():
            logger.info(f"清理临时目录: {temp_dir}")
            shutil.rmtree(temp_dir)


async def do_update_async(
    force: bool = False, 
    on_complete: Optional[Callable[[bool], None]] = None
) -> bool:
    """
    异步执行 schemas 更新（在线程池中运行同步更新）
    
    Args:
        force: 是否强制更新（忽略版本检查）
        on_complete: 更新完成后的回调函数
    
    Returns:
        是否更新成功
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, do_update, force, on_complete)


def main():
    """主函数"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 解析命令行参数
    force = "--force" in sys.argv or "-f" in sys.argv
    
    logger.info("开始更新 OSIM Schema...")
    logger.info(f"仓库: {SCHEMA_REPO}")
    logger.info(f"分支: {SCHEMA_BRANCH}")
    logger.info(f"目标目录: {LOCAL_OSIM_SCHEMA_DIR}")
    if force:
        logger.info("模式: 强制更新")
    
    success = do_update(force=force)
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
