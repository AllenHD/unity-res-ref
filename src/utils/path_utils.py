"""路径处理工具模块

提供路径匹配、过滤和规范化等实用功能。
"""

import os
import re
from pathlib import Path
from typing import List, Pattern, Union, Optional, Set
import fnmatch
import logging

logger = logging.getLogger(__name__)


class PathMatcher:
    """路径匹配器，支持glob模式和正则表达式"""
    
    def __init__(self, patterns: List[str], case_sensitive: bool = True):
        """初始化路径匹配器
        
        Args:
            patterns: 匹配模式列表，支持glob和正则表达式
            case_sensitive: 是否区分大小写
        """
        self.patterns = patterns
        self.case_sensitive = case_sensitive
        self.compiled_patterns: List[Pattern] = []
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """编译匹配模式"""
        self.compiled_patterns = []
        
        for pattern in self.patterns:
            try:
                # 尝试作为正则表达式编译
                if pattern.startswith('regex:'):
                    regex_pattern = pattern[6:]  # 移除'regex:'前缀
                    flags = 0 if self.case_sensitive else re.IGNORECASE
                    compiled = re.compile(regex_pattern, flags)
                    self.compiled_patterns.append(compiled)
                else:
                    # 作为glob模式处理
                    # 将glob模式转换为正则表达式
                    regex_pattern = self._glob_to_regex(pattern)
                    flags = 0 if self.case_sensitive else re.IGNORECASE
                    compiled = re.compile(regex_pattern, flags)
                    self.compiled_patterns.append(compiled)
                    
            except re.error as e:
                logger.warning(f"无效的匹配模式 '{pattern}': {e}")
                continue
    
    def _glob_to_regex(self, glob_pattern: str) -> str:
        """将glob模式转换为正则表达式
        
        Args:
            glob_pattern: glob模式字符串
            
        Returns:
            正则表达式字符串
        """
        # 转义特殊字符，但保留glob通配符
        pattern = re.escape(glob_pattern)
        
        # 替换转义的glob通配符
        pattern = pattern.replace(r'\*', '.*')      # * -> .*
        pattern = pattern.replace(r'\?', '.')       # ? -> .
        pattern = pattern.replace(r'\[', '[')       # [ -> [
        pattern = pattern.replace(r'\]', ']')       # ] -> ]
        
        # 处理路径分隔符
        pattern = pattern.replace(r'\/', '/')
        pattern = pattern.replace('/', r'[/\\]')    # 支持Windows和Unix路径分隔符
        
        # 添加行首行尾锚点
        return f'^{pattern}$'
    
    def matches(self, path: Union[str, Path]) -> bool:
        """检查路径是否匹配任何模式
        
        Args:
            path: 要检查的路径
            
        Returns:
            匹配返回True，否则返回False
        """
        path_str = str(path)
        
        # 标准化路径分隔符
        path_str = path_str.replace('\\', '/')
        
        for pattern in self.compiled_patterns:
            if pattern.match(path_str):
                return True
                
        return False
    
    def filter_paths(self, paths: List[Union[str, Path]]) -> List[Path]:
        """过滤路径列表，返回匹配的路径
        
        Args:
            paths: 路径列表
            
        Returns:
            匹配的路径列表
        """
        matched_paths = []
        
        for path in paths:
            if self.matches(path):
                matched_paths.append(Path(path))
                
        return matched_paths


class PathUtils:
    """路径处理实用工具类"""
    
    @staticmethod
    def normalize_path(path: Union[str, Path]) -> Path:
        """规范化路径
        
        Args:
            path: 输入路径
            
        Returns:
            规范化后的Path对象
        """
        return Path(path).resolve()
    
    @staticmethod  
    def is_subpath(path: Union[str, Path], parent: Union[str, Path]) -> bool:
        """检查path是否是parent的子路径
        
        Args:
            path: 要检查的路径
            parent: 父路径
            
        Returns:
            是子路径返回True，否则返回False
        """
        try:
            Path(path).resolve().relative_to(Path(parent).resolve())
            return True
        except ValueError:
            return False
    
    @staticmethod
    def get_relative_path(path: Union[str, Path], base: Union[str, Path]) -> Optional[Path]:
        """获取相对于base的相对路径
        
        Args:
            path: 目标路径
            base: 基准路径
            
        Returns:
            相对路径，无法计算时返回None
        """
        try:
            return Path(path).resolve().relative_to(Path(base).resolve())
        except ValueError:
            return None
    
    @staticmethod
    def ensure_path_exists(path: Union[str, Path], is_file: bool = False) -> Path:
        """确保路径存在，如果不存在则创建
        
        Args:
            path: 目标路径
            is_file: 是否为文件路径（如果是，创建其父目录）
            
        Returns:
            路径对象
        """
        path_obj = Path(path)
        
        if is_file:
            path_obj.parent.mkdir(parents=True, exist_ok=True)
        else:
            path_obj.mkdir(parents=True, exist_ok=True)
            
        return path_obj
    
    @staticmethod
    def safe_path_join(*parts: Union[str, Path]) -> Path:
        """安全地连接路径部分，防止路径遍历攻击
        
        Args:
            *parts: 路径部分
            
        Returns:
            连接后的路径
        """
        result = Path()
        
        for part in parts:
            part_str = str(part)
            
            # 检查恶意路径
            if '..' in part_str or part_str.startswith('/'):
                logger.warning(f"检测到潜在的不安全路径: {part_str}")
                continue
                
            result = result / part_str
            
        return result
    
    @staticmethod
    def get_path_stats(path: Union[str, Path]) -> Optional[dict]:
        """获取路径统计信息
        
        Args:
            path: 目标路径
            
        Returns:
            包含统计信息的字典，失败时返回None
        """
        try:
            path_obj = Path(path)
            if not path_obj.exists():
                return None
                
            stat = path_obj.stat()
            
            return {
                'size': stat.st_size,
                'mtime': stat.st_mtime,
                'ctime': stat.st_ctime,
                'atime': stat.st_atime,
                'is_file': path_obj.is_file(),
                'is_dir': path_obj.is_dir(),
                'is_symlink': path_obj.is_symlink(),
                'permissions': oct(stat.st_mode)[-3:]
            }
            
        except OSError as e:
            logger.error(f"获取路径统计信息失败 {path}: {e}")
            return None
    
    @staticmethod
    def find_files_by_extension(
        directory: Union[str, Path], 
        extensions: List[str],
        recursive: bool = True
    ) -> List[Path]:
        """根据扩展名查找文件
        
        Args:
            directory: 搜索目录
            extensions: 文件扩展名列表
            recursive: 是否递归搜索子目录
            
        Returns:
            匹配的文件路径列表
        """
        directory = Path(directory)
        if not directory.exists() or not directory.is_dir():
            return []
        
        # 标准化扩展名（确保以.开头）
        normalized_extensions = set()
        for ext in extensions:
            if not ext.startswith('.'):
                ext = '.' + ext
            normalized_extensions.add(ext.lower())
        
        matched_files = []
        
        try:
            pattern = '**/*' if recursive else '*'
            for file_path in directory.glob(pattern):
                if file_path.is_file():
                    file_ext = file_path.suffix.lower()
                    if file_ext in normalized_extensions:
                        matched_files.append(file_path)
                        
        except OSError as e:
            logger.error(f"搜索文件时发生错误 {directory}: {e}")
            
        return matched_files
    
    @staticmethod
    def filter_hidden_files(paths: List[Path], exclude_hidden: bool = True) -> List[Path]:
        """过滤隐藏文件
        
        Args:
            paths: 文件路径列表
            exclude_hidden: 是否排除隐藏文件
            
        Returns:
            过滤后的路径列表
        """
        if not exclude_hidden:
            return paths
            
        filtered_paths = []
        
        for path in paths:
            # 检查文件名是否以.开头（Unix隐藏文件）
            if path.name.startswith('.'):
                continue
                
            # 检查路径中是否包含隐藏目录
            if any(part.startswith('.') for part in path.parts):
                continue
                
            # Windows隐藏文件检查
            if os.name == 'nt':
                try:
                    import stat
                    if path.exists() and path.stat().st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN:
                        continue
                except (AttributeError, OSError):
                    pass  # 忽略Windows特定的错误
                    
            filtered_paths.append(path)
            
        return filtered_paths
    
    @staticmethod
    def calculate_directory_size(directory: Union[str, Path]) -> int:
        """计算目录总大小
        
        Args:
            directory: 目录路径
            
        Returns:
            目录大小（字节）
        """
        directory = Path(directory)
        if not directory.exists() or not directory.is_dir():
            return 0
            
        total_size = 0
        
        try:
            for file_path in directory.rglob('*'):
                if file_path.is_file():
                    try:
                        total_size += file_path.stat().st_size
                    except OSError:
                        continue  # 跳过无法访问的文件
                        
        except OSError as e:
            logger.error(f"计算目录大小时发生错误 {directory}: {e}")
            
        return total_size


def create_path_matcher(patterns: List[str], case_sensitive: bool = True) -> PathMatcher:
    """创建路径匹配器的便捷函数
    
    Args:
        patterns: 匹配模式列表
        case_sensitive: 是否区分大小写
        
    Returns:
        PathMatcher实例
    """
    return PathMatcher(patterns, case_sensitive)


def is_unity_project_directory(path: Union[str, Path]) -> bool:
    """检查是否为Unity项目目录
    
    Args:
        path: 要检查的路径
        
    Returns:
        是Unity项目目录返回True，否则返回False
    """
    path = Path(path)
    
    # 检查Unity项目的标志性文件/目录
    unity_indicators = [
        'Assets',
        'ProjectSettings', 
        'Packages',
        'UserSettings'
    ]
    
    found_indicators = 0
    for indicator in unity_indicators:
        if (path / indicator).exists():
            found_indicators += 1
    
    # 至少需要找到2个指示器才认为是Unity项目
    return found_indicators >= 2
