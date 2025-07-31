"""Unity Meta文件解析器

专门处理Unity .meta文件的解析，提取GUID信息和各种导入设置。
"""

from typing import Dict, Any, Optional, List, Set
from pathlib import Path
import re
import logging
from enum import Enum

from .base_parser import BaseParser, ParseResult, ParseResultType
from ..utils.yaml_utils import YAMLParser

logger = logging.getLogger(__name__)


class ImporterType(Enum):
    """Unity导入器类型枚举"""
    TEXTURE_IMPORTER = "TextureImporter"
    MODEL_IMPORTER = "ModelImporter"
    AUDIO_IMPORTER = "AudioImporter"
    MONO_IMPORTER = "MonoImporter"
    NATIVE_FORMAT_IMPORTER = "NativeFormatImporter"
    DEFAULT_IMPORTER = "DefaultImporter"
    PLUGIN_IMPORTER = "PluginImporter"
    ASSEMBLY_DEFINITION_IMPORTER = "AssemblyDefinitionImporter"
    PACKAGE_MANIFEST_IMPORTER = "PackageManifestImporter"
    FONT_IMPORTER = "FontImporter"
    VIDEO_CLIP_IMPORTER = "VideoClipImporter"
    SHADER_IMPORTER = "ShaderImporter"
    COMPUTE_SHADER_IMPORTER = "ComputeShaderImporter"
    SPEED_TREE_IMPORTER = "SpeedTreeImporter"
    SUBSTANCE_IMPORTER = "SubstanceImporter"
    UNKNOWN = "Unknown"
    
    @classmethod
    def from_string(cls, importer_str: str) -> 'ImporterType':
        """从字符串创建导入器类型"""
        for importer_type in cls:
            if importer_type.value == importer_str:
                return importer_type
        return cls.UNKNOWN


class MetaFileInfo:
    """Meta文件信息类"""
    
    def __init__(
        self,
        guid: str,
        file_format_version: int,
        importer_type: ImporterType,
        importer_data: Dict[str, Any],
        user_data: Optional[str] = None,
        asset_bundle_name: Optional[str] = None,
        asset_bundle_variant: Optional[str] = None
    ):
        self.guid = guid
        self.file_format_version = file_format_version
        self.importer_type = importer_type
        self.importer_data = importer_data
        self.user_data = user_data
        self.asset_bundle_name = asset_bundle_name
        self.asset_bundle_variant = asset_bundle_variant
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "guid": self.guid,
            "file_format_version": self.file_format_version,
            "importer_type": self.importer_type.value,
            "importer_data": self.importer_data,
            "user_data": self.user_data,
            "asset_bundle_name": self.asset_bundle_name,
            "asset_bundle_variant": self.asset_bundle_variant
        }
    
    def get_asset_type(self) -> str:
        """根据导入器类型推断资源类型"""
        type_mapping = {
            ImporterType.TEXTURE_IMPORTER: "TEXTURE",
            ImporterType.MODEL_IMPORTER: "MODEL",
            ImporterType.AUDIO_IMPORTER: "AUDIO",
            ImporterType.MONO_IMPORTER: "SCRIPT",
            ImporterType.NATIVE_FORMAT_IMPORTER: "NATIVE_ASSET",
            ImporterType.FONT_IMPORTER: "FONT",
            ImporterType.VIDEO_CLIP_IMPORTER: "VIDEO",
            ImporterType.SHADER_IMPORTER: "SHADER",
            ImporterType.COMPUTE_SHADER_IMPORTER: "COMPUTE_SHADER",
            ImporterType.PLUGIN_IMPORTER: "PLUGIN",
            ImporterType.ASSEMBLY_DEFINITION_IMPORTER: "ASSEMBLY_DEFINITION",
            ImporterType.PACKAGE_MANIFEST_IMPORTER: "PACKAGE_MANIFEST",
            ImporterType.SPEED_TREE_IMPORTER: "SPEED_TREE",
            ImporterType.SUBSTANCE_IMPORTER: "SUBSTANCE"
        }
        return type_mapping.get(self.importer_type, "UNKNOWN")


class MetaParser(BaseParser):
    """Unity Meta文件解析器"""
    
    # GUID格式验证正则表达式（32位十六进制字符）
    GUID_PATTERN = re.compile(r'^[0-9a-fA-F]{32}$')
    
    # 必需的Meta文件字段
    REQUIRED_FIELDS = ['fileFormatVersion', 'guid']
    
    def __init__(self, strict_mode: bool = False):
        """初始化Meta解析器
        
        Args:
            strict_mode: 严格模式，遇到错误时立即失败
        """
        super().__init__(strict_mode)
        self.yaml_parser = YAMLParser(preserve_quotes=True)
        
        # 支持的导入器类型
        self.supported_importers: Set[str] = {
            importer_type.value for importer_type in ImporterType 
            if importer_type != ImporterType.UNKNOWN
        }
    
    def can_parse(self, file_path: Path) -> bool:
        """判断是否可以解析指定文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            可以解析返回True，否则返回False
        """
        return (
            file_path.suffix.lower() == '.meta' and
            self.validate_file_path(file_path)
        )
    
    def get_supported_extensions(self) -> List[str]:
        """获取支持的文件扩展名列表
        
        Returns:
            支持的扩展名列表
        """
        return ['.meta']
    
    def parse(self, file_path: Path) -> ParseResult:
        """解析Meta文件
        
        Args:
            file_path: Meta文件路径
            
        Returns:
            解析结果
        """
        if not self.can_parse(file_path):
            return self.create_skipped_result(file_path, "不支持的文件类型或文件不存在")
        
        try:
            # 加载YAML数据
            yaml_data = self.yaml_parser.load_from_file(file_path)
            if yaml_data is None:
                return self.create_failed_result(file_path, "无法解析YAML内容")
            
            # 验证必需字段
            validation_result = self._validate_meta_structure(yaml_data)
            if not validation_result[0]:
                return self.create_failed_result(file_path, validation_result[1])
            
            # 解析Meta信息
            meta_info = self._parse_meta_info(yaml_data)
            if meta_info is None:
                return self.create_failed_result(file_path, "无法解析Meta信息")
            
            # 创建成功结果
            result = self.create_success_result(
                file_path=file_path,
                guid=meta_info.guid,
                asset_type=meta_info.get_asset_type(),
                data=meta_info.to_dict()
            )
            
            # 添加警告信息
            warnings = self._check_potential_issues(meta_info, yaml_data)
            for warning in warnings:
                result.add_warning(warning)
            
            self.logger.debug(f"成功解析Meta文件: {file_path}, GUID: {meta_info.guid}")
            return result
            
        except Exception as e:
            error_msg = f"解析Meta文件时发生异常: {e}"
            self.logger.error(f"{error_msg} - 文件: {file_path}")
            return self.create_failed_result(file_path, error_msg)
    
    def _validate_meta_structure(self, data: Dict[str, Any]) -> tuple[bool, str]:
        """验证Meta文件结构
        
        Args:
            data: YAML解析后的数据
            
        Returns:
            (是否有效, 错误信息)
        """
        if not isinstance(data, dict):
            return False, "Meta文件内容不是有效的字典格式"
        
        # 检查必需字段
        missing_fields = [field for field in self.REQUIRED_FIELDS if field not in data]
        if missing_fields:
            return False, f"缺少必需字段: {', '.join(missing_fields)}"
        
        # 验证GUID格式
        guid = data.get('guid')
        if not self._validate_guid(guid):
            return False, f"无效的GUID格式: {guid}"
        
        # 验证文件格式版本
        file_format_version = data.get('fileFormatVersion')
        if not isinstance(file_format_version, int) or file_format_version < 1:
            return False, f"无效的文件格式版本: {file_format_version}"
        
        return True, ""
    
    def _validate_guid(self, guid: Any) -> bool:
        """验证GUID格式
        
        Args:
            guid: 要验证的GUID
            
        Returns:
            GUID格式有效返回True，否则返回False
        """
        if not isinstance(guid, str):
            return False
        return bool(self.GUID_PATTERN.match(guid))
    
    def _parse_meta_info(self, data: Dict[str, Any]) -> Optional[MetaFileInfo]:
        """解析Meta文件信息
        
        Args:
            data: YAML解析后的数据
            
        Returns:
            Meta文件信息对象，解析失败返回None
        """
        try:
            guid = data['guid']
            file_format_version = data['fileFormatVersion']
            
            # 检测导入器类型
            importer_type, importer_data = self._detect_importer_type(data)
            
            # 提取其他信息
            user_data = data.get('userData')
            asset_bundle_name = data.get('assetBundleName')
            asset_bundle_variant = data.get('assetBundleVariant')
            
            return MetaFileInfo(
                guid=guid,
                file_format_version=file_format_version,
                importer_type=importer_type,
                importer_data=importer_data,
                user_data=user_data,
                asset_bundle_name=asset_bundle_name,
                asset_bundle_variant=asset_bundle_variant
            )
            
        except Exception as e:
            self.logger.error(f"解析Meta信息时发生错误: {e}")
            return None
    
    def _detect_importer_type(self, data: Dict[str, Any]) -> tuple[ImporterType, Dict[str, Any]]:
        """检测导入器类型
        
        Args:
            data: YAML解析后的数据
            
        Returns:
            (导入器类型, 导入器数据)
        """
        importer_data = {}
        
        # 检查已知的导入器类型
        for key, value in data.items():
            if key in self.supported_importers and isinstance(value, dict):
                importer_type = ImporterType.from_string(key)
                importer_data = value
                self.logger.debug(f"检测到导入器类型: {key}")
                return importer_type, importer_data
        
        # 如果没有找到已知导入器，返回未知类型
        self.logger.warning("未能检测到已知的导入器类型")
        return ImporterType.UNKNOWN, {}
    
    def _check_potential_issues(
        self, 
        meta_info: MetaFileInfo, 
        raw_data: Dict[str, Any]
    ) -> List[str]:
        """检查潜在问题
        
        Args:
            meta_info: Meta文件信息
            raw_data: 原始YAML数据
            
        Returns:
            警告信息列表
        """
        warnings = []
        
        # 检查未知导入器类型
        if meta_info.importer_type == ImporterType.UNKNOWN:
            warnings.append("未能识别导入器类型")
        
        # 检查空的导入器数据
        if not meta_info.importer_data:
            warnings.append("导入器数据为空")
        
        # 检查旧版本文件格式
        if meta_info.file_format_version < 2:
            warnings.append(f"文件格式版本较旧: {meta_info.file_format_version}")
        
        # 检查是否有未处理的字段
        known_fields = {
            'fileFormatVersion', 'guid', 'userData', 
            'assetBundleName', 'assetBundleVariant'
        }
        known_fields.update(self.supported_importers)
        
        unknown_fields = set(raw_data.keys()) - known_fields
        if unknown_fields:
            warnings.append(f"发现未知字段: {', '.join(unknown_fields)}")
        
        return warnings
    
    def extract_guid_only(self, file_path: Path) -> Optional[str]:
        """快速提取GUID（不进行完整解析）
        
        Args:
            file_path: Meta文件路径
            
        Returns:
            GUID字符串，失败时返回None
        """
        try:
            if not self.validate_file_path(file_path):
                return None
            
            with open(file_path, 'r', encoding='utf-8') as file:
                for line in file:
                    line = line.strip()
                    if line.startswith('guid:'):
                        guid = line.split(':', 1)[1].strip()
                        if self._validate_guid(guid):
                            return guid
                        break
                        
            return None
            
        except Exception as e:
            self.logger.error(f"快速提取GUID时发生错误 {file_path}: {e}")
            return None
    
    def get_parser_stats(self) -> Dict[str, Any]:
        """获取解析器统计信息
        
        Returns:
            统计信息字典
        """
        stats = self.get_parser_info()
        stats.update({
            "supported_importers": len(self.supported_importers),
            "guid_pattern": self.GUID_PATTERN.pattern,
            "required_fields": self.REQUIRED_FIELDS
        })
        return stats
