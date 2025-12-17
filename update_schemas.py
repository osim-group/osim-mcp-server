#!/usr/bin/env python3
"""
从 GitHub 仓库同步最新的 OSIM schemas

使用方法:
    python update_schemas.py

或者直接运行:
    ./update_schemas.py
"""
import json
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# GitHub 仓库配置
SCHEMA_REPO = "osim-group/osim-schema"
SCHEMA_BRANCH = "main"
SCHEMA_PATH = "schemas"
SCHEMA_REPO_URL = f"https://github.com/{SCHEMA_REPO}.git"

# 本地 schemas 目录
LOCAL_SCHEMAS_DIR = Path(__file__).parent / "schemas"


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


def clone_schemas_to_temp() -> Optional[Path]:
    """克隆仓库到临时目录并返回 schemas 路径"""
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
        
        schemas_path = repo_dir / SCHEMA_PATH
        if not schemas_path.exists():
            logger.error(f"仓库中找不到 schemas 目录: {schemas_path}")
            return None
        
        return schemas_path
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


def backup_existing_schemas() -> Optional[Path]:
    """备份现有的 schemas 目录"""
    if not LOCAL_SCHEMAS_DIR.exists():
        return None
    
    backup_dir = LOCAL_SCHEMAS_DIR.parent / f"schemas.backup"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    
    logger.info(f"备份现有 schemas 到 {backup_dir}...")
    shutil.copytree(LOCAL_SCHEMAS_DIR, backup_dir)
    return backup_dir


def update_schemas(source_schemas: Path) -> bool:
    """更新本地 schemas 目录"""
    try:
        # 备份现有 schemas
        backup_dir = backup_existing_schemas()
        
        # 删除现有 schemas 目录
        if LOCAL_SCHEMAS_DIR.exists():
            logger.info(f"删除现有 schemas 目录: {LOCAL_SCHEMAS_DIR}")
            shutil.rmtree(LOCAL_SCHEMAS_DIR)
        
        # 复制新的 schemas
        logger.info(f"复制新的 schemas 从 {source_schemas} 到 {LOCAL_SCHEMAS_DIR}...")
        shutil.copytree(source_schemas, LOCAL_SCHEMAS_DIR)
        
        # 删除备份（如果更新成功）
        if backup_dir and backup_dir.exists():
            logger.info(f"删除备份目录: {backup_dir}")
            shutil.rmtree(backup_dir)
        
        logger.info("Schemas 更新成功！")
        return True
    except Exception as e:
        logger.error(f"更新 schemas 失败: {e}", exc_info=True)
        # 尝试恢复备份
        if backup_dir and backup_dir.exists() and not LOCAL_SCHEMAS_DIR.exists():
            logger.info("尝试恢复备份...")
            shutil.copytree(backup_dir, LOCAL_SCHEMAS_DIR)
        return False


def verify_schemas() -> bool:
    """验证 schemas 目录是否有效"""
    if not LOCAL_SCHEMAS_DIR.exists():
        logger.error(f"Schemas 目录不存在: {LOCAL_SCHEMAS_DIR}")
        return False
    
    # 检查是否有 JSON 文件
    json_files = list(LOCAL_SCHEMAS_DIR.rglob("*.json"))
    if not json_files:
        logger.error("Schemas 目录中没有找到 JSON 文件")
        return False
    
    logger.info(f"找到 {len(json_files)} 个 JSON 文件")
    
    # 检查是否有 groups.json
    groups_file = LOCAL_SCHEMAS_DIR / "groups.json"
    if not groups_file.exists():
        logger.warning("未找到 groups.json 文件")
    
    return True


def main():
    """主函数"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("开始更新 OSIM schemas...")
    logger.info(f"仓库: {SCHEMA_REPO}")
    logger.info(f"分支: {SCHEMA_BRANCH}")
    logger.info(f"路径: {SCHEMA_PATH}")
    logger.info(f"目标目录: {LOCAL_SCHEMAS_DIR}")
    
    # 检查 git 是否可用
    if not check_git_available():
        logger.error("未找到 git 命令，请先安装 git")
        sys.exit(1)
    
    # 克隆仓库到临时目录
    source_schemas = clone_schemas_to_temp()
    if source_schemas is None:
        logger.error("无法获取 schemas，更新失败")
        sys.exit(1)
    
    try:
        # 更新本地 schemas
        if not update_schemas(source_schemas):
            logger.error("更新 schemas 失败")
            sys.exit(1)
        
        # 验证更新结果
        if not verify_schemas():
            logger.error("验证 schemas 失败")
            sys.exit(1)
        
        logger.info("Schemas 更新完成！")
    finally:
        # 清理临时目录
        temp_dir = source_schemas.parent.parent
        if temp_dir.exists():
            logger.info(f"清理临时目录: {temp_dir}")
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main()

