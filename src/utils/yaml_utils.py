"""YAML处理工具模块

提供YAML文件的读取、解析和验证功能，针对Unity文件格式进行优化。
"""

from typing import Dict, Any, Optional, Union
from pathlib import Path
import logging
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

logger = logging.getLogger(__name__)


class YAMLParser:
    """YAML解析器类，专门处理Unity格式的YAML文件"""
    
    def __init__(self, preserve_quotes: bool = True):
        """初始化YAML解析器
        
        Args:
            preserve_quotes: 是否保持引号格式，默认True
        """
        self.yaml = YAML()
        self.yaml.preserve_quotes = preserve_quotes
        self.yaml.default_flow_style = False
        self.yaml.width = 4096  # 避免长行被折断
        
    def load_from_file(self, file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """从文件加载YAML内容
        
        Args:
            file_path: YAML文件路径
            
        Returns:
            解析后的字典数据，失败时返回None
        """
        try:
            path = Path(file_path)
            if not path.exists():
                logger.error(f"YAML文件不存在: {file_path}")
                return None
                
            if not path.is_file():
                logger.error(f"路径不是文件: {file_path}")
                return None
                
            with open(path, 'r', encoding='utf-8') as file:
                data = self.yaml.load(file)
                logger.debug(f"成功解析YAML文件: {file_path}")
                return data
                
        except UnicodeDecodeError as e:
            logger.error(f"YAML文件编码错误 {file_path}: {e}")
            return None
        except YAMLError as e:
            logger.error(f"YAML解析错误 {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"读取YAML文件时发生未知错误 {file_path}: {e}")
            return None
    
    def load_from_string(self, yaml_string: str) -> Optional[Dict[str, Any]]:
        """从字符串加载YAML内容
        
        Args:
            yaml_string: YAML格式字符串
            
        Returns:
            解析后的字典数据，失败时返回None
        """
        try:
            if not yaml_string or not yaml_string.strip():
                logger.warning("YAML字符串为空")
                return None
                
            data = self.yaml.load(yaml_string)
            logger.debug("成功解析YAML字符串")
            return data
            
        except YAMLError as e:
            logger.error(f"YAML字符串解析错误: {e}")
            return None
        except Exception as e:
            logger.error(f"解析YAML字符串时发生未知错误: {e}")
            return None
    
    def save_to_file(self, data: Dict[str, Any], file_path: Union[str, Path]) -> bool:
        """将数据保存为YAML文件
        
        Args:
            data: 要保存的字典数据
            file_path: 输出文件路径
            
        Returns:
            保存成功返回True，失败返回False
        """
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as file:
                self.yaml.dump(data, file)
                logger.debug(f"成功保存YAML文件: {file_path}")
                return True
                
        except Exception as e:
            logger.error(f"保存YAML文件时发生错误 {file_path}: {e}")
            return False
    
    def validate_structure(self, data: Dict[str, Any], required_keys: list) -> bool:
        """验证YAML数据结构
        
        Args:
            data: 要验证的数据
            required_keys: 必需的键列表
            
        Returns:
            验证通过返回True，失败返回False
        """
        if not isinstance(data, dict):
            logger.error("YAML数据不是字典格式")
            return False
            
        missing_keys = [key for key in required_keys if key not in data]
        if missing_keys:
            logger.error(f"YAML数据缺少必需的键: {missing_keys}")
            return False
            
        return True


def load_yaml_file(file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
    """便捷函数：加载YAML文件
    
    Args:
        file_path: YAML文件路径
        
    Returns:
        解析后的字典数据，失败时返回None
    """
    parser = YAMLParser()
    return parser.load_from_file(file_path)


def validate_yaml_keys(data: Dict[str, Any], required_keys: list) -> bool:
    """便捷函数：验证YAML数据键
    
    Args:
        data: 要验证的数据
        required_keys: 必需的键列表
        
    Returns:
        验证通过返回True，失败返回False
    """
    parser = YAMLParser()
    return parser.validate_structure(data, required_keys)
