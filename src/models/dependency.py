"""Unity Resource Reference Scanner - Dependency Data Model

依赖关系数据模型定义，用于存储Unity项目中资源之间的引用关系。
支持不同类型的依赖关系分析和图形化查询。
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Index, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from .asset import Base


class DependencyType(str, Enum):
    """依赖关系类型枚举"""
    DIRECT = "direct"           # 直接引用
    INDIRECT = "indirect"       # 间接引用
    SCRIPT = "script"           # 脚本引用
    MATERIAL = "material"       # 材质引用
    TEXTURE = "texture"         # 贴图引用
    MESH = "mesh"              # 网格引用
    AUDIO = "audio"            # 音频引用
    ANIMATION = "animation"     # 动画引用
    PREFAB = "prefab"          # 预制体引用
    SCENE = "scene"            # 场景引用
    SHADER = "shader"          # 着色器引用
    FONT = "font"              # 字体引用
    COMPONENT = "component"     # 组件引用
    PROPERTY = "property"       # 属性引用
    UNKNOWN = "unknown"         # 未知类型


class DependencyStrength(str, Enum):
    """依赖强度枚举"""
    CRITICAL = "critical"       # 关键依赖（必须）
    IMPORTANT = "important"     # 重要依赖
    OPTIONAL = "optional"       # 可选依赖
    WEAK = "weak"              # 弱依赖


class Dependency(Base):
    """Unity资源依赖关系数据模型
    
    存储资源之间的依赖关系信息，支持依赖类型分类、强度分析等功能。
    用于构建资源依赖图和进行依赖分析。
    """
    __tablename__ = "dependencies"

    # 主键：自增ID
    id = Column(Integer, primary_key=True, autoincrement=True, comment="依赖关系ID")
    
    # 依赖关系核心信息
    source_guid = Column(
        String(32), 
        ForeignKey('assets.guid', ondelete='CASCADE'),
        nullable=False, 
        comment="源资源GUID"
    )
    target_guid = Column(
        String(32), 
        ForeignKey('assets.guid', ondelete='CASCADE'),
        nullable=False, 
        comment="目标资源GUID"
    )
    
    # 依赖关系类型和强度
    dependency_type = Column(String(50), nullable=False, comment="依赖类型")
    dependency_strength = Column(String(20), default=DependencyStrength.IMPORTANT, comment="依赖强度")
    
    # 依赖上下文信息
    context_path = Column(String(512), nullable=True, comment="依赖上下文路径")
    component_type = Column(String(100), nullable=True, comment="组件类型")
    property_name = Column(String(100), nullable=True, comment="属性名称")
    
    # 时间戳信息
    created_at = Column(DateTime, default=datetime.utcnow, comment="记录创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="记录更新时间")
    
    # 依赖状态
    is_active = Column(Boolean, default=True, comment="依赖关系是否活跃")
    is_verified = Column(Boolean, default=False, comment="依赖关系是否已验证")
    
    # 扩展信息（JSON格式存储）
    dep_metadata = Column(JSON, nullable=True, comment="依赖关系元数据")
    analysis_info = Column(JSON, nullable=True, comment="分析信息")
    
    # 关联关系
    source_asset = relationship(
        "Asset",
        foreign_keys=[source_guid],
        back_populates="outgoing_dependencies"
    )
    
    target_asset = relationship(
        "Asset",
        foreign_keys=[target_guid],
        back_populates="incoming_dependencies"
    )

    # 数据库索引定义
    __table_args__ = (
        # 基础索引
        Index('idx_dependency_source_guid', 'source_guid'),
        Index('idx_dependency_target_guid', 'target_guid'),
        Index('idx_dependency_type', 'dependency_type'),
        Index('idx_dependency_strength', 'dependency_strength'),
        Index('idx_dependency_created_at', 'created_at'),
        Index('idx_dependency_active', 'is_active'),
        Index('idx_dependency_verified', 'is_verified'),
        
        # 复合索引用于常见查询
        Index('idx_dependency_source_type', 'source_guid', 'dependency_type'),
        Index('idx_dependency_target_type', 'target_guid', 'dependency_type'),
        Index('idx_dependency_source_target', 'source_guid', 'target_guid'),
        Index('idx_dependency_type_strength', 'dependency_type', 'dependency_strength'),
        Index('idx_dependency_active_type', 'is_active', 'dependency_type'),
        
        # 唯一约束：避免重复的依赖关系
        Index('idx_dependency_unique', 'source_guid', 'target_guid', 'dependency_type', 'context_path', unique=True),
    )

    def __init__(self, source_guid: str, target_guid: str, dependency_type: str, **kwargs):
        """初始化Dependency实例
        
        Args:
            source_guid: 源资源GUID  
            target_guid: 目标资源GUID
            dependency_type: 依赖类型
            **kwargs: 其他可选参数
        """
        self.source_guid = source_guid
        self.target_guid = target_guid
        self.dependency_type = dependency_type
        
        # 设置默认值
        self.dependency_strength = kwargs.get('dependency_strength', DependencyStrength.IMPORTANT.value)
        self.is_active = kwargs.get('is_active', True)
        self.is_verified = kwargs.get('is_verified', False)
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self.updated_at = kwargs.get('updated_at', datetime.utcnow())
        
        # 设置其他属性
        for key, value in kwargs.items():
            if hasattr(self, key) and key not in ['dependency_strength', 'is_active', 'is_verified', 'created_at', 'updated_at']:
                setattr(self, key, value)

    @classmethod
    def create_dependency(
        cls,
        source_guid: str,
        target_guid: str,
        dependency_type: DependencyType,
        dependency_strength: DependencyStrength = DependencyStrength.IMPORTANT,
        context_path: Optional[str] = None,
        component_type: Optional[str] = None,
        property_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "Dependency":
        """创建依赖关系实例的便捷方法
        
        Args:
            source_guid: 源资源GUID
            target_guid: 目标资源GUID
            dependency_type: 依赖类型
            dependency_strength: 依赖强度
            context_path: 上下文路径
            component_type: 组件类型
            property_name: 属性名称
            metadata: 元数据
            
        Returns:
            Dependency: 依赖关系实例
        """
        return cls(
            source_guid=source_guid,
            target_guid=target_guid,
            dependency_type=dependency_type.value,
            dependency_strength=dependency_strength.value,
            context_path=context_path,
            component_type=component_type,
            property_name=property_name,
            dep_metadata=metadata or {}
        )

    @property
    def is_circular(self) -> bool:
        """检查是否为循环依赖"""
        return str(self.source_guid) == str(self.target_guid)

    @property
    def dependency_path(self) -> str:
        """获取依赖路径描述"""
        parts = []
        context_path = getattr(self, 'context_path', None)
        component_type = getattr(self, 'component_type', None)
        property_name = getattr(self, 'property_name', None)
        
        if context_path:
            parts.append(context_path)
        if component_type:
            parts.append(f"Component:{component_type}")
        if property_name:
            parts.append(f"Property:{property_name}")
        
        return " -> ".join(parts) if parts else "Direct"

    def update_metadata(self, metadata: Dict[str, Any]) -> None:
        """更新依赖关系元数据
        
        Args:
            metadata: 元数据字典
        """
        if self.dep_metadata is None:
            self.dep_metadata = {}
        self.dep_metadata.update(metadata)
        self.updated_at = datetime.utcnow()

    def update_analysis_info(self, analysis_info: Dict[str, Any]) -> None:
        """更新分析信息
        
        Args:
            analysis_info: 分析信息字典
        """
        if self.analysis_info is None:
            self.analysis_info = {}
        self.analysis_info.update(analysis_info)
        self.updated_at = datetime.utcnow()

    def mark_as_verified(self) -> None:
        """标记依赖关系已验证"""
        self.is_verified = True
        self.updated_at = datetime.utcnow()

    def mark_as_inactive(self) -> None:
        """标记依赖关系为非活跃状态"""
        self.is_active = False
        self.updated_at = datetime.utcnow()

    def get_strength_priority(self) -> int:
        """获取依赖强度的优先级数值
        
        Returns:
            int: 优先级数值（数值越大优先级越高）
        """
        priority_map = {
            DependencyStrength.CRITICAL: 100,
            DependencyStrength.IMPORTANT: 75,
            DependencyStrength.OPTIONAL: 50,
            DependencyStrength.WEAK: 25,
        }
        return priority_map.get(DependencyStrength(self.dependency_strength), 0)

    def __repr__(self) -> str:
        """字符串表示"""
        return f"<Dependency(source='{self.source_guid}', target='{self.target_guid}', type='{self.dependency_type}')>"

    def __str__(self) -> str:
        """用户友好的字符串表示"""
        return f"{self.source_guid} -> {self.target_guid} ({self.dependency_type})"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式
        
        Returns:
            Dict[str, Any]: 依赖关系信息字典
        """
        created_at = getattr(self, 'created_at', None)
        updated_at = getattr(self, 'updated_at', None)
        
        return {
            'id': self.id,
            'source_guid': self.source_guid,
            'target_guid': self.target_guid,
            'dependency_type': self.dependency_type,
            'dependency_strength': self.dependency_strength,
            'context_path': getattr(self, 'context_path', None),
            'component_type': getattr(self, 'component_type', None),
            'property_name': getattr(self, 'property_name', None),
            'created_at': created_at.isoformat() if created_at else None,
            'updated_at': updated_at.isoformat() if updated_at else None,
            'is_active': getattr(self, 'is_active', True),
            'is_verified': getattr(self, 'is_verified', False),
            'dep_metadata': getattr(self, 'dep_metadata', None),
            'analysis_info': getattr(self, 'analysis_info', None),
            'dependency_path': self.dependency_path,
            'strength_priority': self.get_strength_priority(),
        }


class DependencyGraph:
    """依赖关系图辅助类
    
    提供依赖关系图的构建、查询和分析功能。
    """

    @staticmethod
    def find_circular_dependencies(dependencies: List[Dependency]) -> List[List[str]]:
        """查找循环依赖
        
        Args:
            dependencies: 依赖关系列表
            
        Returns:
            List[List[str]]: 循环依赖路径列表
        """
        # 构建邻接表
        graph = {}
        for dep in dependencies:
            is_active = getattr(dep, 'is_active', True)
            if not is_active:
                continue
            source_guid = getattr(dep, 'source_guid', '')
            target_guid = getattr(dep, 'target_guid', '')
            if source_guid not in graph:
                graph[source_guid] = []
            graph[source_guid].append(target_guid)

        # DFS查找循环
        visited = set()
        rec_stack = set()
        cycles = []

        def dfs(node: str, path: List[str]) -> None:
            if node in rec_stack:
                # 找到循环
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return
            
            if node in visited:
                return

            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                dfs(neighbor, path[:])

            rec_stack.remove(node)

        for node in graph:
            if node not in visited:
                dfs(node, [])

        return cycles

    @staticmethod
    def get_dependency_depth(dependencies: List[Dependency], guid: str) -> Dict[str, int]:
        """获取指定资源的依赖深度
        
        Args:
            dependencies: 依赖关系列表
            guid: 目标资源GUID
            
        Returns:
            Dict[str, int]: 依赖深度映射
        """
        # 构建反向邻接表（被依赖图）
        reverse_graph = {}
        for dep in dependencies:
            is_active = getattr(dep, 'is_active', True)
            if not is_active:
                continue
            source_guid = getattr(dep, 'source_guid', '')
            target_guid = getattr(dep, 'target_guid', '')
            if target_guid not in reverse_graph:
                reverse_graph[target_guid] = []
            reverse_graph[target_guid].append(source_guid)

        # BFS计算深度
        from collections import deque
        
        depths = {guid: 0}
        queue = deque([guid])
        
        while queue:
            current = queue.popleft()
            current_depth = depths[current]
            
            for dependent in reverse_graph.get(current, []):
                if dependent not in depths:
                    depths[dependent] = current_depth + 1
                    queue.append(dependent)
        
        return depths
