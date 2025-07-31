"""解析器基类模块

定义所有解析器的通用接口和基础功能。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass
import logging
from enum import Enum
import re

logger = logging.getLogger(__name__)


class ParseResultType(Enum):
    """解析结果类型枚举"""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ParseResult:
    """解析结果数据类"""
    result_type: ParseResultType
    file_path: str
    guid: Optional[str] = None
    asset_type: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    warnings: Optional[List[str]] = None
    
    def __post_init__(self):
        """初始化后处理"""
        if self.warnings is None:
            self.warnings = []
    
    @property
    def is_success(self) -> bool:
        """判断解析是否成功"""
        return self.result_type == ParseResultType.SUCCESS
    
    @property
    def is_failed(self) -> bool:
        """判断解析是否失败"""
        return self.result_type == ParseResultType.FAILED
    
    @property
    def is_skipped(self) -> bool:
        """判断解析是否跳过"""
        return self.result_type == ParseResultType.SKIPPED
    
    def add_warning(self, warning: str) -> None:
        """添加警告信息"""
        if self.warnings is None:
            self.warnings = []
        self.warnings.append(warning)
        logger.warning(f"解析警告 [{self.file_path}]: {warning}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "result_type": self.result_type.value,
            "file_path": self.file_path,
            "guid": self.guid,
            "asset_type": self.asset_type,
            "data": self.data,
            "error_message": self.error_message,
            "warnings": self.warnings
        }


class BaseParser(ABC):
    """解析器基类
    
    定义所有解析器必须实现的通用接口。
    """
    
    def __init__(self, strict_mode: bool = False):
        """初始化解析器
        
        Args:
            strict_mode: 严格模式，遇到错误时立即失败
        """
        self.strict_mode = strict_mode
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def can_parse(self, file_path: Path) -> bool:
        """判断是否可以解析指定文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            可以解析返回True，否则返回False
        """
        pass
    
    @abstractmethod
    def parse(self, file_path: Path) -> ParseResult:
        """解析文件
        
        Args:
            file_path: 要解析的文件路径
            
        Returns:
            解析结果
        """
        pass
    
    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """获取支持的文件扩展名列表
        
        Returns:
            支持的扩展名列表，如['.meta', '.prefab']
        """
        pass
    
    def validate_file_path(self, file_path: Path) -> bool:
        """验证文件路径
        
        Args:
            file_path: 文件路径
            
        Returns:
            验证通过返回True，失败返回False
        """
        if not file_path.exists():
            self.logger.error(f"文件不存在: {file_path}")
            return False
            
        if not file_path.is_file():
            self.logger.error(f"路径不是文件: {file_path}")
            return False
            
        if file_path.suffix.lower() not in self.get_supported_extensions():
            self.logger.debug(f"不支持的文件扩展名: {file_path.suffix}")
            return False
            
        return True
    
    def create_success_result(
        self, 
        file_path: Path,
        guid: Optional[str] = None,
        asset_type: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> ParseResult:
        """创建成功的解析结果
        
        Args:
            file_path: 文件路径
            guid: 资源GUID
            asset_type: 资源类型
            data: 解析的数据
            
        Returns:
            解析结果
        """
        return ParseResult(
            result_type=ParseResultType.SUCCESS,
            file_path=str(file_path),
            guid=guid,
            asset_type=asset_type,
            data=data
        )
    
    def create_failed_result(
        self, 
        file_path: Path,
        error_message: str
    ) -> ParseResult:
        """创建失败的解析结果
        
        Args:
            file_path: 文件路径
            error_message: 错误信息
            
        Returns:
            解析结果
        """
        return ParseResult(
            result_type=ParseResultType.FAILED,
            file_path=str(file_path),
            error_message=error_message
        )
    
    def create_skipped_result(
        self, 
        file_path: Path,
        reason: str = "文件被跳过"
    ) -> ParseResult:
        """创建跳过的解析结果
        
        Args:
            file_path: 文件路径
            reason: 跳过原因
            
        Returns:
            解析结果
        """
        return ParseResult(
            result_type=ParseResultType.SKIPPED,
            file_path=str(file_path),
            error_message=reason
        )
    
    def parse_batch(self, file_paths: List[Path]) -> List[ParseResult]:
        """批量解析文件
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            解析结果列表
        """
        results = []
        for file_path in file_paths:
            try:
                result = self.parse(file_path)
                results.append(result)
            except Exception as e:
                self.logger.error(f"解析文件时发生异常 {file_path}: {e}")
                results.append(self.create_failed_result(file_path, str(e)))
                
                if self.strict_mode:
                    break
                    
        return results
    
    def get_parser_info(self) -> Dict[str, Any]:
        """获取解析器信息
        
        Returns:
            解析器信息字典
        """
        return {
            "name": self.__class__.__name__,
            "supported_extensions": self.get_supported_extensions(),
            "strict_mode": self.strict_mode
        }
    
    def _parse_unity_yaml(self, content: str) -> List[Dict[str, Any]]:
        """解析Unity YAML格式内容
        
        Unity使用特殊的YAML格式，包含文档分隔符和类型标识符。
        
        Args:
            content: YAML文件内容
            
        Returns:
            解析出的文档列表
        """
        documents = []
        
        # Unity YAML文档分隔符模式 - 匹配 "--- !u!123 &456"
        doc_pattern = r'--- !u!(\d+) &(\d+)'
        
        # 找到所有文档分隔符的位置
        lines = content.split('\n')
        doc_starts = []
        
        for i, line in enumerate(lines):
            if re.match(doc_pattern, line.strip()):
                match = re.match(doc_pattern, line.strip())
                if match:
                    doc_starts.append({
                        'line_index': i,
                        'class_id': match.group(1),
                        'file_id': match.group(2)
                    })
        
        # 解析每个文档
        for i, doc_start in enumerate(doc_starts):
            start_line = doc_start['line_index'] + 1  # 跳过分隔符行
            
            # 确定文档结束位置
            if i < len(doc_starts) - 1:
                end_line = doc_starts[i + 1]['line_index']
            else:
                end_line = len(lines)
            
            # 提取文档内容
            doc_lines = lines[start_line:end_line]
            doc_content = '\n'.join(doc_lines)
            
            # 解析文档内容
            doc_data = self._parse_yaml_content(doc_content)
            
            if doc_data:
                doc_data['_unity_class_id'] = doc_start['class_id']
                doc_data['_unity_file_id'] = doc_start['file_id']
                documents.append(doc_data)
        
        return documents
    
    def _parse_yaml_content(self, content: str) -> Optional[Dict[str, Any]]:
        """解析YAML内容为字典
        
        简化的YAML解析，主要用于提取键值对。
        
        Args:
            content: YAML内容
            
        Returns:
            解析的字典数据
        """
        try:
            data = {}
            lines = content.split('\n')
            current_key = None
            current_value = []
            indent_level = 0
            
            for line in lines:
                if not line.strip():
                    continue
                    
                # 检测缩进
                line_indent = len(line) - len(line.lstrip())
                
                # 简单的键值对匹配
                if ':' in line and not line.strip().startswith('-'):
                    if current_key and current_value:
                        data[current_key] = '\n'.join(current_value).strip()
                        current_value = []
                    
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if value:
                        data[key] = value
                    else:
                        current_key = key
                        indent_level = line_indent
                else:
                    if current_key:
                        current_value.append(line)
            
            # 处理最后一个键值对
            if current_key and current_value:
                data[current_key] = '\n'.join(current_value).strip()
            
            return data if data else None
            
        except Exception as e:
            logger.error(f"解析YAML内容时出错: {e}")
            return None
