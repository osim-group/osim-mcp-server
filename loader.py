"""
数据标准加载器，用于解析 schemas 目录下的 JSON 文件。
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SchemaInfo:
    """Schema 信息记录类"""
    group: str
    category: str
    title: str
    description: str
    label: str
    file_path: Path


class DataStandardLoader:
    """数据标准加载器，用于加载和解析 schemas 目录下的 JSON 文件"""
    
    def __init__(self, schemas_dir: Optional[Path] = None):
        """
        初始化数据标准加载器
        
        Args:
            schemas_dir: schemas 目录路径，默认为 osim-schema/schemas 目录
        """
        if schemas_dir is None:
            # 默认使用 osim-schema/schemas 目录
            self.schemas_dir = Path(__file__).parent / "osim-schema" / "schemas"
        else:
            self.schemas_dir = Path(schemas_dir)
        
        # 存储 schema 文件信息: {type_path: SchemaInfo}
        self.schema_files: Dict[str, SchemaInfo] = {}
        
        # 存储字段定义: {group: {title: definitions}}
        self.data: Dict[str, Dict[str, dict]] = {}
        
        # 存储 i18n 翻译数据: {locale: i18n_data}
        # 例如: {"zh_CN": {...}, "en_US": {...}}
        self.i18n_data: Dict[str, Dict[str, Any]] = {}
        
        self.loaded = False
    
    def reload(self) -> None:
        """
        重新加载所有 schema 文件。
        用于 schemas 更新后刷新内存中的数据。
        """
        logger.info("重新加载 schemas...")
        self.schema_files = {}
        self.data = {}
        self.i18n_data = {}
        self.loaded = False
        self.load_all()
        logger.info(f"重新加载完成，共 {len(self.schema_files)} 个 schema")
    
    def load_all(self) -> None:
        """
        加载所有 JSON schema 文件。
        
        文件夹结构：
        - 第一层：分组（group），例如：alert, asset, log, incident, device_detection
        - 第二层：分类（category），例如：network_attack, account_operation_audit
        - 文件名：{title}.json，例如：http_audit.json, account_change.json
        
        排除文件：
        - categories.json：分类元数据文件
        - groups.json：分组元数据文件
        """
        if self.loaded:
            return
        
        if not self.schemas_dir.exists():
            logger.warning(f"Schemas 目录不存在: {self.schemas_dir}")
            return
        
        schema_files_count = 0
        total_files = 0
        
        # 递归查找所有 JSON 文件
        for json_file in self.schemas_dir.rglob("*.json"):
            total_files += 1
            filename = json_file.name
            
            # 排除 categories.json 和 groups.json
            if filename in ("categories.json", "groups.json"):
                continue
            
            schema_files_count += 1
            try:
                self._load_json_file(json_file)
            except Exception as e:
                logger.error(f"加载JSON文件失败 {json_file}: {e}", exc_info=True)
        
        logger.info(f"找到 {schema_files_count} 个schema文件（共 {total_files} 个JSON文件）")
        logger.info(f"数据标准加载完成，共 {len(self.schema_files)} 个类型")
        
        self.loaded = True
    
    def _load_json_file(self, json_file: Path) -> None:
        """
        加载单个 JSON 文件。
        
        JSON格式：
        {
            "group": "log",
            "category": "network_session_audit",
            "title": "http_audit",
            "description": "...",
            "definitions": {
                "字段名": {
                    "label": "字段标签",
                    "requirement": "REQUIRED|RECOMMENDED|OPTIONAL",
                    "description": "字段描述",
                    "type": "字段类型",
                    "valid_type": "验证类型",
                    ...
                },
                ...
            }
        }
        """
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                content = json.load(f)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON文件格式不正确 {json_file}: {e}")
            return
        
        # 验证JSON结构
        if not isinstance(content, dict):
            logger.warning(f"JSON文件格式不正确 {json_file}: 根节点不是对象")
            return
        
        # 检查必需字段
        required_fields = ["group", "category", "title", "definitions"]
        missing_fields = [field for field in required_fields if field not in content]
        if missing_fields:
            logger.warning(f"JSON文件格式不正确 {json_file}: 缺少必需字段 {missing_fields}")
            return
        
        group = content["group"]
        category = content["category"]
        title = content["title"]
        definitions = content["definitions"]
        
        if not isinstance(definitions, dict):
            logger.warning(f"JSON文件格式不正确 {json_file}: definitions字段不是对象")
            return
        
        # 存储字段定义
        if group not in self.data:
            self.data[group] = {}
        self.data[group][title] = definitions
        
        # 存储 schema 文件信息
        type_path = f"data.{group}.{title}"
        description = content.get("description", "")
        label = content.get("label", "")
        schema_info = SchemaInfo(
            group=group,
            category=category,
            title=title,
            description=description,
            label=label,
            file_path=json_file
        )
        
        if type_path in self.schema_files:
            logger.warning(f"重复的schema定义 {json_file}: {type_path} 已存在")
        
        self.schema_files[type_path] = schema_info
        
        logger.debug(f"加载JSON文件成功: {json_file} -> {type_path}")
    
    def _load_i18n(self) -> None:
        """
        加载所有 i18n 翻译文件。
        扫描 i18n 目录下的所有 JSON 文件，动态加载。
        """
        if self.i18n_data:
            return
        
        # i18n 文件位于 osim-schema/i18n/ 目录
        i18n_dir = Path(__file__).parent / "osim-schema" / "i18n"
        
        if not i18n_dir.exists():
            logger.warning(f"i18n 目录不存在: {i18n_dir}")
            return
        
        # 扫描所有 JSON 文件
        for i18n_file in i18n_dir.glob("*.json"):
            # 从文件名提取 locale（例如：zh_CN.json -> zh_CN）
            locale = i18n_file.stem
            
            try:
                with open(i18n_file, 'r', encoding='utf-8') as f:
                    i18n_content = json.load(f)
                    self.i18n_data[locale] = i18n_content
                    logger.debug(f"成功加载 i18n 文件: {locale}")
            except json.JSONDecodeError as e:
                logger.error(f"i18n 文件 JSON 格式错误 {i18n_file}: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"读取 i18n 文件失败 {i18n_file}: {e}", exc_info=True)
    
    def _get_i18n_labels(self, schema_info: SchemaInfo) -> Dict[str, str]:
        """
        从所有 i18n 文件中获取 label 翻译。
        
        Args:
            schema_info: Schema 信息对象
        
        Returns:
            字典，key 为 locale（如 "zh_CN"），value 为对应语言的 label
        """
        self._load_i18n()
        
        result = {}
        
        if not self.i18n_data:
            return result
        
        # i18n 文件中的 key 基于文件名（去掉 .json 扩展名）
        # 例如：abnormal_behavior_access_anomaly.json -> abnormal_behavior_access_anomaly
        file_stem = schema_info.file_path.stem
        
        # 遍历所有已加载的 i18n 数据
        for locale, i18n_content in self.i18n_data.items():
            classes = i18n_content.get("classes", {})
            class_info = classes.get(file_stem, {})
            label = class_info.get("label", "")
            if label:
                result[locale] = label
        
        return result
    
    def list_schema_names(self) -> List[Dict[str, Any]]:
        """
        获取所有 schema 的名称列表，包含 title、label 和所有可用的 i18n 翻译。
        
        Returns:
            schema 信息列表，每个元素包含：
            - title: schema 名称，格式为 {group}.{category}.{title}
            - label: schema 的英文标签（来自 schema 文件）
            - label_{locale}: schema 的各语言标签（动态生成，如 label_zh_CN, label_en_US 等）
        """
        self.load_all()
        
        result = []
        for info in self.schema_files.values():
            title = f"{info.group}.{info.category}.{info.title}"
            label = info.label
            
            # 获取所有语言的翻译
            i18n_labels = self._get_i18n_labels(info)
            
            # 构建返回对象
            schema_item = {
                "title": title,
                "label": label
            }
            
            # 动态添加各语言的 label，key 格式为 label_{locale}
            for locale, translated_label in i18n_labels.items():
                schema_item[f"label_{locale}"] = translated_label
            
            result.append(schema_item)
        
        # 按 title 排序
        return sorted(result, key=lambda x: x["title"])
    
    def describe_schemas(self, schema_names: List[str]) -> Dict[str, str]:
        """
        获取指定 schema 名称列表的描述信息。
        
        Args:
            schema_names: schema 名称列表，格式为 {group}.{category}.{title}
        
        Returns:
            字典，key 为 {group}.{category}.{title}，value 为 description
        """
        self.load_all()
        
        result = {}
        for schema_name in schema_names:
            parts = schema_name.split(".")
            if len(parts) != 3:
                logger.warning(f"无效的 schema 名称格式: {schema_name}，应为 group.category.title")
                continue
            
            group, category, title = parts
            
            # 查找匹配的 schema
            for info in self.schema_files.values():
                if info.group == group and info.category == category and info.title == title:
                    result[schema_name] = info.description
                    break
        
        return result
    
    def get_schema(self, schema_path: str) -> Optional[Dict[str, any]]:
        """
        根据 schema 路径获取字段定义。
        
        Args:
            schema_path: schema 路径，格式为 {group}.{category}.{title}，例如 log.network_session_audit.http_audit
        
        Returns:
            字段定义，如果类型不存在则返回 None
        """
        self.load_all()
        
        parts = schema_path.split(".")
        if len(parts) != 3:
            logger.warning(f"无效的 schema 路径格式: {schema_path}，应为 group.category.title")
            return None
        
        group, category, title = parts
        
        # 查找匹配的 schema
        schema_info = None
        for info in self.schema_files.values():
            if info.group == group and info.category == category and info.title == title:
                schema_info = info
                break
        
        if schema_info is None:
            logger.warning(f"找不到匹配的 schema: {schema_path}")
            return None
        
        # 获取字段定义
        if group not in self.data:
            logger.warning(f"找不到分组: {group}")
            return None
        
        definitions = self.data[group].get(title)
        if definitions is None:
            logger.warning(f"找不到schema: {title} (分组: {group})")
            return None
        
        return definitions
    
    def get_schema_resource(self, group: str, category: str, title: str) -> str:
        """
        根据 group, category, title 获取 schema 资源内容。
        
        Args:
            group: 分组
            category: 分类
            title: 标题
        
        Returns:
            JSON 字符串内容，如果找不到则返回错误信息
        """
        self.load_all()
        
        # 查找匹配的 schema
        schema_info = None
        for info in self.schema_files.values():
            if info.group == group and info.category == category and info.title == title:
                schema_info = info
                break
        
        if schema_info is None:
            error_msg = json.dumps({"error": f"找不到 schema: {group}.{category}.{title}"}, ensure_ascii=False)
            return error_msg
        
        try:
            with open(schema_info.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            # 验证 JSON 格式
            json.loads(content)
            return content
        except Exception as e:
            logger.error(f"读取文件失败: {e}", exc_info=True)
            error_msg = json.dumps({"error": f"读取文件失败: {str(e)}"}, ensure_ascii=False)
            return error_msg
    
    def get_dictionaries(self) -> Dict[str, Any]:
        """
        获取 dictionaries.json 文件内容。
        
        Returns:
            字典内容，如果文件不存在或读取失败则返回包含错误信息的字典
        """
        # dictionaries.json 位于 osim-schema 根目录
        dictionaries_file = Path(__file__).parent / "osim-schema" / "dictionaries.json"
        
        if not dictionaries_file.exists():
            logger.warning(f"dictionaries.json 文件不存在: {dictionaries_file}")
            return {"error": f"dictionaries.json 文件不存在: {dictionaries_file}"}
        
        try:
            with open(dictionaries_file, 'r', encoding='utf-8') as f:
                content = json.load(f)
            logger.info(f"成功读取 dictionaries.json，包含 {len(content)} 个字典项")
            return content
        except json.JSONDecodeError as e:
            logger.error(f"dictionaries.json JSON 格式错误: {e}", exc_info=True)
            return {"error": f"dictionaries.json JSON 格式错误: {str(e)}"}
        except Exception as e:
            logger.error(f"读取 dictionaries.json 失败: {e}", exc_info=True)
            return {"error": f"读取 dictionaries.json 失败: {str(e)}"}


