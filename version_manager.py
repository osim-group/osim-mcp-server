"""
版本管理模块，用于管理 OSIM schemas 的版本信息。

功能：
- 从远程获取最新版本号
- 读取/保存本地版本号
- 版本比较
"""
import json
import logging
import re
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 远程版本号文件 URL
REMOTE_VERSION_URL = "https://raw.githubusercontent.com/osim-group/osim-schema/main/version.json"

# 本地版本号文件路径（与 schemas 目录同级）
LOCAL_VERSION_FILE = Path(__file__).parent / "schemas" / "version.json"


@dataclass
class VersionInfo:
    """版本信息"""
    version: str
    major: int = 0
    minor: int = 0
    patch: int = 0
    prerelease: str = ""
    
    @classmethod
    def parse(cls, version_str: str) -> "VersionInfo":
        """
        解析版本号字符串
        
        支持格式：
        - 1.0.0
        - 1.0.0-alpha
        - 1.0.0-beta.1
        - 1.1.0-test
        """
        # 匹配语义化版本号
        pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$'
        match = re.match(pattern, version_str.strip())
        
        if not match:
            logger.warning(f"无法解析版本号: {version_str}，使用默认值")
            return cls(version=version_str)
        
        major = int(match.group(1))
        minor = int(match.group(2))
        patch = int(match.group(3))
        prerelease = match.group(4) or ""
        
        return cls(
            version=version_str,
            major=major,
            minor=minor,
            patch=patch,
            prerelease=prerelease
        )
    
    def __gt__(self, other: "VersionInfo") -> bool:
        """版本比较：大于"""
        # 先比较主版本号
        if self.major != other.major:
            return self.major > other.major
        # 再比较次版本号
        if self.minor != other.minor:
            return self.minor > other.minor
        # 再比较补丁版本号
        if self.patch != other.patch:
            return self.patch > other.patch
        # 最后比较预发布版本（无预发布版本 > 有预发布版本）
        if not self.prerelease and other.prerelease:
            return True
        if self.prerelease and not other.prerelease:
            return False
        # 两者都有或都没有预发布版本，按字符串比较
        return self.prerelease > other.prerelease
    
    def __eq__(self, other: "VersionInfo") -> bool:
        """版本比较：等于"""
        return (
            self.major == other.major and
            self.minor == other.minor and
            self.patch == other.patch and
            self.prerelease == other.prerelease
        )
    
    def __ge__(self, other: "VersionInfo") -> bool:
        """版本比较：大于等于"""
        return self > other or self == other
    
    def __lt__(self, other: "VersionInfo") -> bool:
        """版本比较：小于"""
        return not self >= other
    
    def __le__(self, other: "VersionInfo") -> bool:
        """版本比较：小于等于"""
        return not self > other
    
    def __str__(self) -> str:
        return self.version


class VersionManager:
    """版本管理器"""
    
    def __init__(self, local_version_file: Optional[Path] = None):
        """
        初始化版本管理器
        
        Args:
            local_version_file: 本地版本号文件路径，默认为 schemas/version.json
        """
        self.local_version_file = local_version_file or LOCAL_VERSION_FILE
        self.remote_version_url = REMOTE_VERSION_URL
    
    def get_local_version(self) -> Optional[VersionInfo]:
        """
        获取本地版本号
        
        Returns:
            本地版本信息，如果文件不存在或解析失败则返回 None
        """
        try:
            if not self.local_version_file.exists():
                logger.info(f"本地版本文件不存在: {self.local_version_file}")
                return None
            
            with open(self.local_version_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            version_str = data.get("version", "")
            if not version_str:
                logger.warning("本地版本文件中没有 version 字段")
                return None
            
            return VersionInfo.parse(version_str)
        except Exception as e:
            logger.error(f"读取本地版本文件失败: {e}")
            return None
    
    def save_local_version(self, version: str) -> bool:
        """
        保存本地版本号
        
        Args:
            version: 版本号字符串
        
        Returns:
            是否保存成功
        """
        try:
            # 确保目录存在
            self.local_version_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.local_version_file, 'w', encoding='utf-8') as f:
                json.dump({"version": version}, f, indent=2)
            
            logger.info(f"保存本地版本号: {version}")
            return True
        except Exception as e:
            logger.error(f"保存本地版本文件失败: {e}")
            return False
    
    async def get_remote_version(self, timeout: float = 10.0) -> Optional[VersionInfo]:
        """
        异步获取远程版本号
        
        Args:
            timeout: 请求超时时间（秒）
        
        Returns:
            远程版本信息，如果获取失败则返回 None
        """
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.remote_version_url,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status != 200:
                        logger.warning(f"获取远程版本失败，HTTP 状态码: {response.status}")
                        return None
                    
                    # GitHub raw 返回 text/plain，需要手动解析 JSON
                    text = await response.text()
                    data = json.loads(text)
                    version_str = data.get("version", "")
                    
                    if not version_str:
                        logger.warning("远程版本文件中没有 version 字段")
                        return None
                    
                    logger.info(f"获取远程版本号: {version_str}")
                    return VersionInfo.parse(version_str)
        except ImportError:
            logger.error("需要安装 aiohttp 库: pip install aiohttp")
            return None
        except Exception as e:
            logger.error(f"获取远程版本失败: {e}")
            return None
    
    def get_remote_version_sync(self, timeout: float = 10.0) -> Optional[VersionInfo]:
        """
        同步获取远程版本号（用于非异步环境）
        
        Args:
            timeout: 请求超时时间（秒）
        
        Returns:
            远程版本信息，如果获取失败则返回 None
        """
        try:
            import urllib.request
            import urllib.error
            
            req = urllib.request.Request(
                self.remote_version_url,
                headers={'User-Agent': 'OSIM-MCP-Server'}
            )
            
            with urllib.request.urlopen(req, timeout=timeout) as response:
                data = json.loads(response.read().decode('utf-8'))
                version_str = data.get("version", "")
                
                if not version_str:
                    logger.warning("远程版本文件中没有 version 字段")
                    return None
                
                logger.info(f"获取远程版本号: {version_str}")
                return VersionInfo.parse(version_str)
        except Exception as e:
            logger.error(f"获取远程版本失败: {e}")
            return None
    
    async def check_update_available(self, timeout: float = 10.0) -> Tuple[bool, Optional[VersionInfo], Optional[VersionInfo]]:
        """
        检查是否有可用更新
        
        Args:
            timeout: 请求超时时间（秒）
        
        Returns:
            (是否有更新, 本地版本, 远程版本)
        """
        local_version = self.get_local_version()
        remote_version = await self.get_remote_version(timeout)
        
        if remote_version is None:
            logger.warning("无法获取远程版本，跳过更新检查")
            return False, local_version, None
        
        if local_version is None:
            logger.info("本地版本不存在，需要更新")
            return True, None, remote_version
        
        if remote_version > local_version:
            logger.info(f"发现新版本: {local_version} -> {remote_version}")
            return True, local_version, remote_version
        
        logger.info(f"已是最新版本: {local_version}")
        return False, local_version, remote_version
    
    def check_update_available_sync(self, timeout: float = 10.0) -> Tuple[bool, Optional[VersionInfo], Optional[VersionInfo]]:
        """
        同步检查是否有可用更新（用于非异步环境）
        
        Args:
            timeout: 请求超时时间（秒）
        
        Returns:
            (是否有更新, 本地版本, 远程版本)
        """
        local_version = self.get_local_version()
        remote_version = self.get_remote_version_sync(timeout)
        
        if remote_version is None:
            logger.warning("无法获取远程版本，跳过更新检查")
            return False, local_version, None
        
        if local_version is None:
            logger.info("本地版本不存在，需要更新")
            return True, None, remote_version
        
        if remote_version > local_version:
            logger.info(f"发现新版本: {local_version} -> {remote_version}")
            return True, local_version, remote_version
        
        logger.info(f"已是最新版本: {local_version}")
        return False, local_version, remote_version

