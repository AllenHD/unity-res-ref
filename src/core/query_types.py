"""Unity Resource Reference Scanner - Query Types Module

查询相关的数据结构和类型定义，包括查询选项和查询结果。
"""

from typing import Dict, List, Set, Optional, Any
from datetime import datetime
from collections import defaultdict


class QueryOptions:
    """查询选项配置类"""
    
    def __init__(
        self,
        max_depth: Optional[int] = None,
        dependency_types: Optional[List[str]] = None,
        strength_threshold: Optional[str] = None,
        include_inactive: bool = False,
        include_unverified: bool = True
    ):
        """初始化查询选项
        
        Args:
            max_depth: 最大查询深度，None表示无限制
            dependency_types: 依赖类型过滤列表
            strength_threshold: 依赖强度阈值
            include_inactive: 是否包含非活跃依赖
            include_unverified: 是否包含未验证依赖
        """
        self.max_depth = max_depth
        self.dependency_types = dependency_types or []
        self.strength_threshold = strength_threshold
        self.include_inactive = include_inactive
        self.include_unverified = include_unverified
    
    def should_include_edge(self, edge_data: Dict[str, Any]) -> bool:
        """判断边是否应该包含在查询结果中
        
        Args:
            edge_data: 边的数据
            
        Returns:
            bool: 是否包含
        """
        # 检查活跃状态
        if not self.include_inactive and not edge_data.get('is_active', True):
            return False
        
        # 检查验证状态
        if not self.include_unverified and not edge_data.get('is_verified', True):
            return False
        
        # 检查依赖类型
        if self.dependency_types:
            dep_type = edge_data.get('dependency_type')
            if dep_type not in self.dependency_types:
                return False
        
        # 检查依赖强度
        if self.strength_threshold:
            strength = edge_data.get('dependency_strength', 'optional')
            strength_order = {
                'weak': 0,
                'optional': 1,
                'important': 2,
                'critical': 3
            }
            
            current_level = strength_order.get(strength, 0)
            threshold_level = strength_order.get(self.strength_threshold, 0)
            
            if current_level < threshold_level:
                return False
        
        return True


class QueryResult:
    """查询结果数据结构"""
    
    def __init__(self, query_type: str, source_guid: str, target_guid: Optional[str] = None):
        """初始化查询结果
        
        Args:
            query_type: 查询类型
            source_guid: 源资源GUID
            target_guid: 目标资源GUID（可选）
        """
        self.query_type = query_type
        self.source_guid = source_guid
        self.target_guid = target_guid
        self.timestamp = datetime.utcnow()
        
        # 查询结果数据
        self.dependencies: List[str] = []
        self.paths: List[List[str]] = []
        self.tree: Optional[Dict[str, Any]] = None
        self.statistics: Dict[str, Any] = {}
        
        # 元数据
        self.metadata: Dict[str, Any] = {}
    
    def add_dependency(self, guid: str) -> None:
        """添加依赖资源
        
        Args:
            guid: 资源GUID
        """
        if guid not in self.dependencies:
            self.dependencies.append(guid)
    
    def add_path(self, path: List[str]) -> None:
        """添加依赖路径
        
        Args:
            path: 依赖路径
        """
        if path not in self.paths:
            self.paths.append(path)
    
    def set_tree(self, tree: Dict[str, Any]) -> None:
        """设置依赖树
        
        Args:
            tree: 依赖树结构
        """
        self.tree = tree
    
    def add_statistic(self, key: str, value: Any) -> None:
        """添加统计信息
        
        Args:
            key: 统计键
            value: 统计值
        """
        self.statistics[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式
        
        Returns:
            Dict[str, Any]: 结果字典
        """
        return {
            'query_type': self.query_type,
            'source_guid': self.source_guid,
            'target_guid': self.target_guid,
            'timestamp': self.timestamp.isoformat(),
            'dependencies': self.dependencies,
            'paths': self.paths,
            'tree': self.tree,
            'statistics': self.statistics,
            'metadata': self.metadata
        }
