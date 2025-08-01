"""
!!! BACKUP FILE - 可忽略 !!!
此文件是dependency_graph.py的备份文件，用于代码重构前的安全备份。
实际使用的是重构后的dependency_graph.py文件。
此备份文件可以忽略或删除。

=== 原始文件说明 ===
Unity Resource Reference Scanner - Dependency Graph Core Module

依赖关系图核心模块，基于NetworkX提供完整的图管理和分析功能。
支持图构建、查询、更新和验证等核心操作。

!!! 此为备份文件，请使用重构后的新文件 !!!
"""

from typing import Dict, List, Set, Optional, Any, Tuple, Union, Callable
from datetime import datetime, timedelta
import json
from pathlib import Path
import logging
from collections import defaultdict
import threading

import networkx as nx
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from ..models.asset import Asset, AssetType
from ..models.dependency import Dependency, DependencyType, DependencyStrength
from .database import DatabaseManager, get_asset_dao, get_dependency_dao

# 导入拆分后的模块
from .query_types import QueryOptions, QueryResult
from .graph_builder import DependencyGraphBuilder
from .dependency_queries import DependencyQueryMixin
from .reference_queries import ReferenceQueryMixin


class DependencyGraph:
    """Unity项目依赖关系图核心类
    
    基于NetworkX DiGraph构建有向图数据结构，管理Unity项目中资源间的依赖关系。
    提供图的初始化、节点和边的管理、状态查询、验证等功能。
    """
    
    def __init__(self, directed: bool = True):
        """初始化依赖关系图
        
        Args:
            directed: 是否为有向图，默认为True
        """
        if directed:
            self._graph = nx.DiGraph()
        else:
            self._graph = nx.Graph()
        
        self._metadata = {
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'version': '1.0.0',
            'directed': directed
        }
        
        # 统计信息缓存
        self._stats_cache = {}
        self._cache_timestamp = None
        
    @property
    def graph(self) -> Union[nx.DiGraph, nx.Graph]:
        """获取底层NetworkX图对象"""
        return self._graph
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """获取图的元数据信息"""
        return self._metadata.copy()
    
    def is_empty(self) -> bool:
        """检查图是否为空
        
        Returns:
            bool: 图是否为空
        """
        return len(self._graph) == 0
    
    def get_node_count(self) -> int:
        """获取节点数量
        
        Returns:
            int: 节点数量  
        """
        return self._graph.number_of_nodes()
    
    def get_edge_count(self) -> int:
        """获取边数量
        
        Returns:
            int: 边数量
        """
        return self._graph.number_of_edges()
    
    def get_graph_stats(self) -> Dict[str, Any]:
        """获取图统计信息
        
        Returns:
            Dict[str, Any]: 包含各种统计信息的字典
        """
        # 检查缓存有效性
        current_time = datetime.utcnow()
        if (self._cache_timestamp and 
            (current_time - self._cache_timestamp).seconds < 60):  # 缓存1分钟
            return self._stats_cache.copy()
        
        stats = {
            'node_count': self.get_node_count(),
            'edge_count': self.get_edge_count(),
            'is_directed': isinstance(self._graph, nx.DiGraph),
            'is_empty': self.is_empty(),
            'density': nx.density(self._graph),
            'created_at': self._metadata['created_at'].isoformat(),
            'updated_at': self._metadata['updated_at'].isoformat()
        }
        
        if not self.is_empty():
            if isinstance(self._graph, nx.DiGraph):
                # 有向图特有统计
                try:
                    stats['is_dag'] = nx.is_directed_acyclic_graph(self._graph)
                    stats['strongly_connected_components'] = nx.number_strongly_connected_components(self._graph)
                    stats['weakly_connected_components'] = nx.number_weakly_connected_components(self._graph)
                except:
                    stats['is_dag'] = None
                    stats['strongly_connected_components'] = None
                    stats['weakly_connected_components'] = None
            else:
                # 无向图统计
                stats['connected_components'] = nx.number_connected_components(self._graph)
                
            # 计算度数统计
            degrees = dict(self._graph.degree())
            if degrees:
                degree_values = list(degrees.values())
                stats['avg_degree'] = sum(degree_values) / len(degree_values)
                stats['max_degree'] = max(degree_values)
                stats['min_degree'] = min(degree_values)
        
        # 更新缓存
        self._stats_cache = stats
        self._cache_timestamp = current_time
        
        return stats.copy()
    
    def add_asset_node(self, guid: str, asset_data: Optional[Dict[str, Any]] = None) -> bool:
        """添加资源节点
        
        Args:
            guid: 资源GUID
            asset_data: 资源数据字典，可选
            
        Returns:
            bool: 添加是否成功
        """
        try:
            if guid in self._graph:
                # 节点已存在，更新数据
                if asset_data:
                    self._graph.nodes[guid].update(asset_data)
                return True
            
            # 添加新节点
            node_data = asset_data or {}
            node_data.update({
                'added_at': datetime.utcnow().isoformat(),
                'node_type': 'asset'
            })
            
            self._graph.add_node(guid, **node_data)
            self._update_timestamp()
            self._invalidate_cache()
            
            return True
        except Exception as e:
            print(f"Error adding asset node {guid}: {e}")
            return False
    
    def remove_asset_node(self, guid: str) -> bool:
        """移除资源节点
        
        Args:
            guid: 资源GUID
            
        Returns:
            bool: 移除是否成功
        """
        try:
            if guid not in self._graph:
                return False
            
            self._graph.remove_node(guid)
            self._update_timestamp()
            self._invalidate_cache()
            
            return True
        except Exception as e:
            print(f"Error removing asset node {guid}: {e}")
            return False
    
    def update_asset_node(self, guid: str, asset_data: Dict[str, Any]) -> bool:
        """更新资源节点数据
        
        Args:
            guid: 资源GUID
            asset_data: 更新的资源数据
            
        Returns:
            bool: 更新是否成功
        """
        try:
            if guid not in self._graph:
                return False
            
            # 更新节点数据
            self._graph.nodes[guid].update(asset_data)
            self._graph.nodes[guid]['updated_at'] = datetime.utcnow().isoformat()
            
            self._update_timestamp()
            self._invalidate_cache()
            
            return True
        except Exception as e:
            print(f"Error updating asset node {guid}: {e}")
            return False
    
    def add_dependency_edge(
        self, 
        source_guid: str, 
        target_guid: str, 
        dependency_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """添加依赖关系边
        
        Args:
            source_guid: 源资源GUID
            target_guid: 目标资源GUID  
            dependency_data: 依赖关系数据，可选
            
        Returns:
            bool: 添加是否成功
        """
        try:
            # 确保节点存在
            if source_guid not in self._graph:
                self.add_asset_node(source_guid)
            if target_guid not in self._graph:
                self.add_asset_node(target_guid)
            
            # 构建边数据
            edge_data = dependency_data or {}
            edge_data.update({
                'added_at': datetime.utcnow().isoformat(),
                'edge_type': 'dependency'
            })
            
            self._graph.add_edge(source_guid, target_guid, **edge_data)
            self._update_timestamp()
            self._invalidate_cache()
            
            return True
        except Exception as e:
            print(f"Error adding dependency edge {source_guid} -> {target_guid}: {e}")
            return False
    
    def remove_dependency_edge(self, source_guid: str, target_guid: str) -> bool:
        """移除依赖关系边
        
        Args:
            source_guid: 源资源GUID
            target_guid: 目标资源GUID
            
        Returns:
            bool: 移除是否成功
        """
        try:
            if not self._graph.has_edge(source_guid, target_guid):
                return False
            
            self._graph.remove_edge(source_guid, target_guid)
            self._update_timestamp()
            self._invalidate_cache()
            
            return True
        except Exception as e:
            print(f"Error removing dependency edge {source_guid} -> {target_guid}: {e}")
            return False
    
    def update_dependency_edge(
        self, 
        source_guid: str, 
        target_guid: str, 
        dependency_data: Dict[str, Any]
    ) -> bool:
        """更新依赖关系边数据
        
        Args:
            source_guid: 源资源GUID
            target_guid: 目标资源GUID
            dependency_data: 更新的依赖关系数据
            
        Returns:
            bool: 更新是否成功
        """
        try:
            if not self._graph.has_edge(source_guid, target_guid):
                return False
            
            # 更新边数据
            self._graph.edges[source_guid, target_guid].update(dependency_data)
            self._graph.edges[source_guid, target_guid]['updated_at'] = datetime.utcnow().isoformat()
            
            self._update_timestamp()
            self._invalidate_cache()
            
            return True
        except Exception as e:
            print(f"Error updating dependency edge {source_guid} -> {target_guid}: {e}")
            return False
    
    def has_node(self, guid: str) -> bool:
        """检查节点是否存在
        
        Args:
            guid: 资源GUID
            
        Returns:
            bool: 节点是否存在
        """
        return guid in self._graph
    
    def has_edge(self, source_guid: str, target_guid: str) -> bool:
        """检查边是否存在
        
        Args:
            source_guid: 源资源GUID
            target_guid: 目标资源GUID
            
        Returns:
            bool: 边是否存在
        """
        return self._graph.has_edge(source_guid, target_guid)
    
    def get_node_data(self, guid: str) -> Optional[Dict[str, Any]]:
        """获取节点数据
        
        Args:
            guid: 资源GUID
            
        Returns:
            Optional[Dict[str, Any]]: 节点数据，如果节点不存在则返回None
        """
        if guid not in self._graph:
            return None
        return dict(self._graph.nodes[guid])
    
    def get_edge_data(self, source_guid: str, target_guid: str) -> Optional[Dict[str, Any]]:
        """获取边数据
        
        Args:
            source_guid: 源资源GUID
            target_guid: 目标资源GUID
            
        Returns:
            Optional[Dict[str, Any]]: 边数据，如果边不存在则返回None
        """
        if not self._graph.has_edge(source_guid, target_guid):
            return None
        return dict(self._graph.edges[source_guid, target_guid])
    
    def get_neighbors(self, guid: str) -> List[str]:
        """获取节点的邻居节点
        
        Args:
            guid: 资源GUID
            
        Returns:
            List[str]: 邻居节点GUID列表
        """
        if guid not in self._graph:
            return []
        return list(self._graph.neighbors(guid))
    
    def get_predecessors(self, guid: str) -> List[str]:
        """获取节点的前驱节点（仅有向图）
        
        Args:
            guid: 资源GUID
            
        Returns:
            List[str]: 前驱节点GUID列表
        """
        if not isinstance(self._graph, nx.DiGraph) or guid not in self._graph:
            return []
        return list(self._graph.predecessors(guid))
    
    def get_successors(self, guid: str) -> List[str]:
        """获取节点的后继节点（仅有向图）
        
        Args:
            guid: 资源GUID
            
        Returns:
            List[str]: 后继节点GUID列表
        """
        if not isinstance(self._graph, nx.DiGraph) or guid not in self._graph:
            return []
        return list(self._graph.successors(guid))
    
    def find_circular_dependencies(self) -> List[List[str]]:
        """查找循环依赖（集成现有算法）
        
        Returns:
            List[List[str]]: 循环依赖路径列表
        """
        if not isinstance(self._graph, nx.DiGraph):
            return []
        
        cycles = []
        try:
            # 使用NetworkX内置的强连通分量检测
            sccs = list(nx.strongly_connected_components(self._graph))
            
            for scc in sccs:
                if len(scc) > 1:  # 真正的循环
                    # 提取子图并找到具体的循环路径
                    subgraph = self._graph.subgraph(scc)
                    try:
                        # 尝试找到一个简单的循环
                        cycle = nx.find_cycle(subgraph, orientation='original')
                        cycle_nodes = [edge[0] for edge in cycle] + [cycle[-1][1]]
                        cycles.append(cycle_nodes)
                    except nx.NetworkXNoCycle:
                        # 如果没有找到标准循环，则记录强连通分量
                        cycles.append(list(scc))
                elif len(scc) == 1:
                    # 检查自循环
                    node = list(scc)[0]
                    if self._graph.has_edge(node, node):
                        cycles.append([node, node])
        
        except Exception as e:
            print(f"Error finding circular dependencies: {e}")
            # 回退到原始DFS算法
            cycles = self._find_cycles_dfs()
        
        return cycles
    
    def _find_cycles_dfs(self) -> List[List[str]]:
        """使用DFS查找循环依赖（回退方法）"""
        visited = set()
        rec_stack = set()
        cycles = []

        def dfs(node: str, path: List[str]) -> None:
            if node in rec_stack:
                # 找到循环
                try:
                    cycle_start = path.index(node)
                    cycles.append(path[cycle_start:] + [node])
                except ValueError:
                    cycles.append(path + [node])
                return
            
            if node in visited:
                return

            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self._graph.successors(node):
                dfs(neighbor, path[:])

            rec_stack.remove(node)

        for node in self._graph.nodes():
            if node not in visited:
                dfs(node, [])

        return cycles
    
    def get_dependency_depth(self, guid: str) -> Dict[str, int]:
        """获取指定资源的依赖深度（集成现有算法）
        
        Args:
            guid: 目标资源GUID
            
        Returns:
            Dict[str, int]: 依赖深度映射 {资源GUID: 深度}
        """
        if not isinstance(self._graph, nx.DiGraph) or guid not in self._graph:
            return {}
        
        # 使用BFS计算反向深度（被依赖深度）
        depths = {guid: 0}
        queue = [guid]
        
        while queue:
            current = queue.pop(0)
            current_depth = depths[current]
            
            # 获取所有依赖当前节点的节点
            for predecessor in self._graph.predecessors(current):
                if predecessor not in depths:
                    depths[predecessor] = current_depth + 1
                    queue.append(predecessor)
        
        return depths
    
    def validate_graph(self) -> Dict[str, Any]:
        """验证图的完整性和一致性
        
        Returns:
            Dict[str, Any]: 验证结果报告
        """
        report = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'statistics': self.get_graph_stats()
        }
        
        try:
            # 检查孤立节点
            isolated_nodes = list(nx.isolates(self._graph))
            if isolated_nodes:
                report['warnings'].append(f"Found {len(isolated_nodes)} isolated nodes")
            
            # 检查自循环
            self_loops = list(nx.selfloop_edges(self._graph))
            if self_loops:
                report['warnings'].append(f"Found {len(self_loops)} self-loop edges")
            
            # 对于有向图，检查循环依赖
            if isinstance(self._graph, nx.DiGraph):
                cycles = self.find_circular_dependencies()
                if cycles:
                    report['errors'].append(f"Found {len(cycles)} circular dependencies")
                    report['circular_dependencies'] = cycles
                    report['is_valid'] = False
            
            # 检查节点数据完整性
            nodes_without_type = []
            for node, data in self._graph.nodes(data=True):
                if 'node_type' not in data:
                    nodes_without_type.append(node)
            
            if nodes_without_type:
                report['warnings'].append(f"Found {len(nodes_without_type)} nodes without type information")
            
            # 检查边数据完整性
            edges_without_type = []
            for source, target, data in self._graph.edges(data=True):
                if 'edge_type' not in data:
                    edges_without_type.append((source, target))
            
            if edges_without_type:
                report['warnings'].append(f"Found {len(edges_without_type)} edges without type information")
        
        except Exception as e:
            report['errors'].append(f"Validation error: {str(e)}")
            report['is_valid'] = False
        
        return report
    
    def to_dict(self) -> Dict[str, Any]:
        """将图序列化为字典格式
        
        Returns:
            Dict[str, Any]: 图的字典表示
        """
        return {
            'metadata': self._metadata,
            'nodes': dict(self._graph.nodes(data=True)),
            'edges': [
                {
                    'source': source,
                    'target': target,
                    'data': data
                }
                for source, target, data in self._graph.edges(data=True)
            ],
            'statistics': self.get_graph_stats()
        }
    
    def to_json(self, file_path: Optional[Union[str, Path]] = None) -> str:
        """将图序列化为JSON格式
        
        Args:
            file_path: 可选的输出文件路径
            
        Returns:
            str: JSON字符串
        """
        graph_dict = self.to_dict()
        json_str = json.dumps(graph_dict, indent=2, default=str)
        
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(json_str)
        
        return json_str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DependencyGraph':
        """从字典数据恢复图对象
        
        Args:
            data: 包含图数据的字典
            
        Returns:
            DependencyGraph: 恢复的图对象
        """
        # 创建新图实例
        directed = data.get('metadata', {}).get('directed', True)
        graph = cls(directed=directed)
        
        # 恢复元数据
        if 'metadata' in data:
            metadata = data['metadata']
            # 处理时间戳字符串转换
            if 'created_at' in metadata and isinstance(metadata['created_at'], str):
                try:
                    from datetime import datetime
                    metadata['created_at'] = datetime.fromisoformat(metadata['created_at'])
                except:
                    metadata['created_at'] = datetime.utcnow()
            if 'updated_at' in metadata and isinstance(metadata['updated_at'], str):
                try:
                    metadata['updated_at'] = datetime.fromisoformat(metadata['updated_at'])
                except:
                    metadata['updated_at'] = datetime.utcnow()
            graph._metadata.update(metadata)
        
        # 恢复节点
        if 'nodes' in data:
            for node_id, node_data in data['nodes'].items():
                graph.add_asset_node(node_id, node_data)
        
        # 恢复边
        if 'edges' in data:
            for edge in data['edges']:
                graph.add_dependency_edge(
                    edge['source'], 
                    edge['target'], 
                    edge.get('data', {})
                )
        
        return graph
    
    @classmethod
    def from_json(cls, json_data: Union[str, Path]) -> 'DependencyGraph':
        """从JSON数据恢复图对象
        
        Args:
            json_data: JSON字符串或文件路径
            
        Returns:
            DependencyGraph: 恢复的图对象
        """
        # 判断是否为文件路径：检查是否为Path对象或不以'{'开头的字符串
        is_file_path = False
        if isinstance(json_data, Path):
            is_file_path = True
        elif isinstance(json_data, str) and not json_data.strip().startswith('{'):
            is_file_path = True
        
        if is_file_path and Path(json_data).exists():
            # 从文件读取
            with open(json_data, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            # 从字符串解析
            data = json.loads(str(json_data))
        
        return cls.from_dict(data)
    
    def clear(self) -> None:
        """清空图中的所有数据"""
        self._graph.clear()
        self._update_timestamp()
        self._invalidate_cache()
    
    def copy(self) -> 'DependencyGraph':
        """创建图的副本
        
        Returns:
            DependencyGraph: 图的副本
        """
        new_graph = DependencyGraph(directed=isinstance(self._graph, nx.DiGraph))
        new_graph._graph = self._graph.copy()
        new_graph._metadata = self._metadata.copy()
        return new_graph
    
    def _update_timestamp(self) -> None:
        """更新时间戳"""
        self._metadata['updated_at'] = datetime.utcnow()
    
    def _invalidate_cache(self) -> None:
        """清除统计缓存"""
        self._stats_cache.clear()
        self._cache_timestamp = None
    
    def __len__(self) -> int:
        """返回节点数量"""
        return len(self._graph)
    
    def __contains__(self, guid: str) -> bool:
        """检查节点是否存在"""
        return guid in self._graph
    
    def __repr__(self) -> str:
        """字符串表示"""
        graph_type = "DiGraph" if isinstance(self._graph, nx.DiGraph) else "Graph"
        return f"<DependencyGraph({graph_type}, nodes={self.get_node_count()}, edges={self.get_edge_count()})>"
    
    def __str__(self) -> str:
        """用户友好的字符串表示"""
        stats = self.get_graph_stats()
        return f"Unity Dependency Graph: {stats['node_count']} assets, {stats['edge_count']} dependencies"


class DependencyGraphBuilder:
    """依赖关系图构建器
    
    负责从数据库批量加载Asset和Dependency数据构建内存图的核心算法。
    提供高效的数据库查询、数据预处理、图构建等功能。
    """
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """初始化图构建器
        
        Args:
            db_manager: 数据库管理器，如果为None则使用全局实例
        """
        self.db_manager = db_manager or DatabaseManager()
        self.asset_dao = get_asset_dao()
        self.dependency_dao = get_dependency_dao()
        
        # 构建配置
        self.batch_size = 1000  # 批量处理大小
        self.memory_limit_mb = 512  # 内存限制（MB）
        
        # 统计信息
        self._build_stats = {}
        self._lock = threading.Lock()
        
        # 日志记录器
        self.logger = logging.getLogger(__name__)
    
    def build_from_database(
        self,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        asset_filter: Optional[Dict[str, Any]] = None,
        dependency_filter: Optional[Dict[str, Any]] = None
    ) -> DependencyGraph:
        """从数据库构建依赖关系图
        
        Args:
            progress_callback: 进度回调函数
            asset_filter: 资源过滤条件
            dependency_filter: 依赖关系过滤条件
            
        Returns:
            DependencyGraph: 构建的依赖关系图
        """
        self.logger.info("开始从数据库构建依赖关系图")
        start_time = datetime.utcnow()
        
        graph = DependencyGraph()
        
        try:
            with self.db_manager.get_session() as session:
                # 第一阶段：加载和构建节点
                self._build_nodes(session, graph, progress_callback, asset_filter)
                
                # 第二阶段：加载和构建边
                self._build_edges(session, graph, progress_callback, dependency_filter)
                
                # 第三阶段：验证和优化
                self._validate_and_optimize(graph, progress_callback)
        
        except Exception as e:
            self.logger.error(f"构建依赖关系图失败: {e}")
            raise
        
        # 生成构建统计
        build_time = (datetime.utcnow() - start_time).total_seconds()
        self._generate_build_stats(graph, build_time)
        
        if progress_callback:
            progress_callback({
                'stage': 'completed',
                'message': '依赖关系图构建完成',
                'stats': self._build_stats
            })
        
        self.logger.info(f"依赖关系图构建完成，耗时 {build_time:.2f} 秒")
        return graph
    
    def build_full_graph(
        self,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> DependencyGraph:
        """构建完整的依赖关系图（适合项目初始化）
        
        Args:
            progress_callback: 进度回调函数
            
        Returns:
            DependencyGraph: 完整的依赖关系图
        """
        self.logger.info("开始构建完整依赖关系图")
        
        # 不使用任何过滤条件，加载所有活跃的资源和依赖
        asset_filter = {'is_active': True}
        dependency_filter = {'is_active': True}
        
        return self.build_from_database(
            progress_callback=progress_callback,
            asset_filter=asset_filter,
            dependency_filter=dependency_filter
        )
    
    def build_incremental_graph(
        self,
        base_graph: Optional[DependencyGraph] = None,
        since_timestamp: Optional[datetime] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> DependencyGraph:
        """构建增量依赖关系图（基于时间戳）
        
        Args:
            base_graph: 基础图，如果为None则创建新图
            since_timestamp: 增量更新的起始时间戳
            progress_callback: 进度回调函数
            
        Returns:
            DependencyGraph: 更新后的依赖关系图
        """
        self.logger.info(f"开始构建增量依赖关系图，时间戳: {since_timestamp}")
        
        if base_graph is None:
            base_graph = DependencyGraph()
        
        if since_timestamp is None:
            # 如果没有指定时间戳，使用24小时前
            since_timestamp = datetime.utcnow() - timedelta(hours=24)
        
        # 增量过滤条件
        asset_filter = {
            'is_active': True,
            'updated_at_gte': since_timestamp
        }
        dependency_filter = {
            'is_active': True,
            'updated_at_gte': since_timestamp
        }
        
        # 构建增量图
        incremental_graph = self.build_from_database(
            progress_callback=progress_callback,
            asset_filter=asset_filter,
            dependency_filter=dependency_filter
        )
        
        # 合并到基础图
        self._merge_graphs(base_graph, incremental_graph)
        
        return base_graph
    
    def _build_nodes(
        self,
        session: Session,
        graph: DependencyGraph,
        progress_callback: Optional[Callable],
        asset_filter: Optional[Dict[str, Any]]
    ) -> None:
        """构建图节点"""
        self.logger.info("开始构建图节点")
        
        if progress_callback:
            progress_callback({'stage': 'nodes', 'message': '正在加载资源数据...', 'progress': 0})
        
        # 构建查询条件
        query = session.query(Asset)
        if asset_filter:
            query = self._apply_asset_filter(query, asset_filter)
        
        # 获取总数用于进度计算
        total_assets = query.count()
        self.logger.info(f"准备加载 {total_assets} 个资源节点")
        
        processed_count = 0
        batch_count = 0
        
        # 分批处理资源
        for batch_start in range(0, total_assets, self.batch_size):
            batch_assets = query.offset(batch_start).limit(self.batch_size).all()
            
            for asset in batch_assets:
                try:
                    # 构建节点数据
                    node_data = {
                        'asset_type': asset.asset_type,
                        'file_path': asset.file_path,
                        'file_size': asset.file_size,
                        'created_at': asset.created_at.isoformat() if asset.created_at else None,
                        'updated_at': asset.updated_at.isoformat() if asset.updated_at else None,
                        'file_modified_at': asset.file_modified_at.isoformat() if asset.file_modified_at else None,
                        'is_active': asset.is_active,
                        'is_analyzed': asset.is_analyzed,
                        'metadata': asset.asset_metadata or {}
                    }
                    
                    # 添加节点到图
                    graph.add_asset_node(asset.guid, node_data)
                    processed_count += 1
                    
                except Exception as e:
                    self.logger.warning(f"添加资源节点失败 {asset.guid}: {e}")
            
            batch_count += 1
            
            # 报告进度
            if progress_callback and batch_count % 10 == 0:
                progress = int((processed_count / total_assets) * 100)
                progress_callback({
                    'stage': 'nodes',
                    'message': f'已加载 {processed_count}/{total_assets} 个资源节点',
                    'progress': progress
                })
        
        self.logger.info(f"完成节点构建，共加载 {processed_count} 个节点")
    
    def _build_edges(
        self,
        session: Session,
        graph: DependencyGraph,
        progress_callback: Optional[Callable],
        dependency_filter: Optional[Dict[str, Any]]
    ) -> None:
        """构建图边"""
        self.logger.info("开始构建图边")
        
        if progress_callback:
            progress_callback({'stage': 'edges', 'message': '正在加载依赖关系数据...', 'progress': 0})
        
        # 构建查询条件
        query = session.query(Dependency)
        if dependency_filter:
            query = self._apply_dependency_filter(query, dependency_filter)
        
        # 获取总数用于进度计算
        total_dependencies = query.count()
        self.logger.info(f"准备加载 {total_dependencies} 个依赖关系")
        
        processed_count = 0
        skipped_count = 0
        batch_count = 0
        
        # 分批处理依赖关系
        for batch_start in range(0, total_dependencies, self.batch_size):
            batch_deps = query.offset(batch_start).limit(self.batch_size).all()
            
            for dep in batch_deps:
                try:
                    # 检查源节点和目标节点是否存在
                    if not graph.has_node(dep.source_guid) or not graph.has_node(dep.target_guid):
                        skipped_count += 1
                        continue
                    
                    # 构建边数据
                    edge_data = {
                        'dependency_type': dep.dependency_type,
                        'dependency_strength': dep.dependency_strength,
                        'context_path': dep.context_path,
                        'component_type': dep.component_type,
                        'property_name': dep.property_name,
                        'created_at': dep.created_at.isoformat() if dep.created_at else None,
                        'updated_at': dep.updated_at.isoformat() if dep.updated_at else None,
                        'is_active': dep.is_active,
                        'is_verified': dep.is_verified,
                        'metadata': dep.dep_metadata or {},
                        'analysis_info': dep.analysis_info or {}
                    }
                    
                    # 添加边到图
                    graph.add_dependency_edge(dep.source_guid, dep.target_guid, edge_data)
                    processed_count += 1
                    
                except Exception as e:
                    self.logger.warning(f"添加依赖关系边失败 {dep.source_guid}->{dep.target_guid}: {e}")
            
            batch_count += 1
            
            # 报告进度
            if progress_callback and batch_count % 10 == 0:
                progress = int((processed_count / total_dependencies) * 100) if total_dependencies > 0 else 100
                progress_callback({
                    'stage': 'edges',
                    'message': f'已加载 {processed_count}/{total_dependencies} 个依赖关系',
                    'progress': progress
                })
        
        if skipped_count > 0:
            self.logger.warning(f"跳过了 {skipped_count} 个依赖关系（缺少对应的资源节点）")
        
        self.logger.info(f"完成边构建，共加载 {processed_count} 个边")
    
    def _validate_and_optimize(
        self,
        graph: DependencyGraph,
        progress_callback: Optional[Callable]
    ) -> None:
        """验证和优化图结构"""
        self.logger.info("开始验证和优化图结构")
        
        if progress_callback:
            progress_callback({'stage': 'validation', 'message': '正在验证图结构...', 'progress': 0})
        
        # 执行图验证
        validation_result = graph.validate_graph()
        
        if not validation_result['is_valid']:
            self.logger.warning(f"图验证发现问题: {validation_result['errors']}")
        
        if validation_result['warnings']:
            self.logger.info(f"图验证警告: {validation_result['warnings']}")
        
        # 检测循环依赖
        if progress_callback:
            progress_callback({'stage': 'validation', 'message': '正在检测循环依赖...', 'progress': 50})
        
        cycles = graph.find_circular_dependencies()
        if cycles:
            self.logger.warning(f"发现 {len(cycles)} 个循环依赖")
        
        if progress_callback:
            progress_callback({'stage': 'validation', 'message': '验证完成', 'progress': 100})
        
        self.logger.info("图验证和优化完成")
    
    def _apply_asset_filter(self, query, asset_filter: Dict[str, Any]):
        """应用资源过滤条件"""
        for key, value in asset_filter.items():
            if key == 'is_active':
                query = query.filter(Asset.is_active == value)
            elif key == 'is_analyzed':
                query = query.filter(Asset.is_analyzed == value)
            elif key == 'asset_type':
                if isinstance(value, list):
                    query = query.filter(Asset.asset_type.in_(value))
                else:
                    query = query.filter(Asset.asset_type == value)
            elif key == 'updated_at_gte':
                query = query.filter(Asset.updated_at >= value)
            elif key == 'updated_at_lte':
                query = query.filter(Asset.updated_at <= value)
            # 可以根据需要添加更多过滤条件
        
        return query
    
    def _apply_dependency_filter(self, query, dependency_filter: Dict[str, Any]):
        """应用依赖关系过滤条件"""
        for key, value in dependency_filter.items():
            if key == 'is_active':
                query = query.filter(Dependency.is_active == value)
            elif key == 'is_verified':
                query = query.filter(Dependency.is_verified == value)
            elif key == 'dependency_type':
                if isinstance(value, list):
                    query = query.filter(Dependency.dependency_type.in_(value))
                else:
                    query = query.filter(Dependency.dependency_type == value)
            elif key == 'dependency_strength':
                if isinstance(value, list):
                    query = query.filter(Dependency.dependency_strength.in_(value))
                else:
                    query = query.filter(Dependency.dependency_strength == value)
            elif key == 'updated_at_gte':
                query = query.filter(Dependency.updated_at >= value)
            elif key == 'updated_at_lte':
                query = query.filter(Dependency.updated_at <= value)
            # 可以根据需要添加更多过滤条件
        
        return query
    
    def _merge_graphs(self, base_graph: DependencyGraph, incremental_graph: DependencyGraph) -> None:
        """合并增量图到基础图"""
        self.logger.info("开始合并增量图")
        
        # 合并节点
        for node_id in incremental_graph.graph.nodes():
            node_data = incremental_graph.get_node_data(node_id)
            if base_graph.has_node(node_id):
                # 更新现有节点
                base_graph.update_asset_node(node_id, node_data)
            else:
                # 添加新节点
                base_graph.add_asset_node(node_id, node_data)
        
        # 合并边
        for source, target in incremental_graph.graph.edges():
            edge_data = incremental_graph.get_edge_data(source, target)
            if base_graph.has_edge(source, target):
                # 更新现有边
                base_graph.update_dependency_edge(source, target, edge_data)
            else:
                # 添加新边
                base_graph.add_dependency_edge(source, target, edge_data)
        
        self.logger.info(f"增量图合并完成")
    
    def _generate_build_stats(self, graph: DependencyGraph, build_time: float) -> None:
        """生成构建统计信息"""
        stats = graph.get_graph_stats()
        
        self._build_stats = {
            'build_time_seconds': build_time,
            'node_count': stats['node_count'],
            'edge_count': stats['edge_count'],
            'graph_density': stats['density'],
            'is_dag': stats.get('is_dag', None),
            'memory_usage_estimate_mb': self._estimate_memory_usage(graph),
            'build_timestamp': datetime.utcnow().isoformat()
        }
        
        # 添加循环依赖统计
        cycles = graph.find_circular_dependencies()
        self._build_stats['circular_dependencies_count'] = len(cycles)
        
        # 计算性能指标
        if build_time > 0:
            self._build_stats['nodes_per_second'] = stats['node_count'] / build_time
            self._build_stats['edges_per_second'] = stats['edge_count'] / build_time
    
    def _estimate_memory_usage(self, graph: DependencyGraph) -> float:
        """估算图的内存使用量（MB）"""
        # 简单的内存使用估算
        node_count = graph.get_node_count()
        edge_count = graph.get_edge_count()
        
        # 估算每个节点和边的平均内存使用
        avg_node_size_bytes = 1024  # 1KB per node (估算)
        avg_edge_size_bytes = 512   # 0.5KB per edge (估算)
        
        total_bytes = (node_count * avg_node_size_bytes) + (edge_count * avg_edge_size_bytes)
        return total_bytes / (1024 * 1024)  # 转换为MB
    
    def get_build_stats(self) -> Dict[str, Any]:
        """获取最近一次构建的统计信息
        
        Returns:
            Dict[str, Any]: 构建统计信息
        """
        return self._build_stats.copy()
    
    def set_batch_size(self, batch_size: int) -> None:
        """设置批量处理大小
        
        Args:
            batch_size: 批量大小
        """
        if batch_size > 0:
            self.batch_size = batch_size
            self.logger.info(f"批量处理大小设置为: {batch_size}")
    
    def set_memory_limit(self, memory_limit_mb: int) -> None:
        """设置内存限制
        
        Args:
            memory_limit_mb: 内存限制（MB）
        """
        if memory_limit_mb > 0:
            self.memory_limit_mb = memory_limit_mb
            self.logger.info(f"内存限制设置为: {memory_limit_mb} MB")


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


class DependencyQueryEngine:
    """依赖查询引擎
    
    基于图遍历算法提供多种依赖查询模式，包括直接依赖、间接依赖、传递依赖等。
    支持查询深度限制、路径追踪、结果过滤等高级功能。
    """
    
    def __init__(self, graph: DependencyGraph):
        """初始化查询引擎
        
        Args:
            graph: 依赖关系图
        """
        self.graph = graph
        
        # 查询结果缓存
        self._cache: Dict[str, QueryResult] = {}
        self._cache_ttl = 300  # 缓存5分钟
        self._cache_timestamps: Dict[str, datetime] = {}
        self._cache_lock = threading.Lock()
        
        # 日志记录器
        self.logger = logging.getLogger(__name__)
    
    def get_direct_dependencies(
        self, 
        source_guid: str, 
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """获取资源的直接依赖
        
        Args:
            source_guid: 源资源GUID
            options: 查询选项
            
        Returns:
            QueryResult: 查询结果
        """
        self.logger.debug(f"查询直接依赖: {source_guid}")
        
        # 检查缓存
        cache_key = f"direct_{source_guid}_{hash(str(options.__dict__) if options else 'default')}"
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            return cached_result
        
        result = QueryResult('direct_dependencies', source_guid)
        options = options or QueryOptions()
        
        try:
            if not self.graph.has_node(source_guid):
                self.logger.warning(f"源资源不存在: {source_guid}")
                result.add_statistic('error', f'Source node {source_guid} not found')
                return result
            
            # 获取直接后继节点
            successors = self.graph.get_successors(source_guid)
            
            for successor in successors:
                edge_data = self.graph.get_edge_data(source_guid, successor)
                
                # 应用过滤条件
                if edge_data and options.should_include_edge(edge_data):
                    result.add_dependency(successor)
                    result.add_path([source_guid, successor])
            
            # 添加统计信息
            result.add_statistic('direct_count', len(result.dependencies))
            result.add_statistic('paths_count', len(result.paths))
            
            # 缓存结果
            self._cache_result(cache_key, result)
            
        except Exception as e:
            self.logger.error(f"查询直接依赖失败 {source_guid}: {e}")
            result.add_statistic('error', str(e))
        
        return result
    
    def get_all_dependencies(
        self,
        source_guid: str,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """获取资源的所有间接依赖（使用DFS遍历）
        
        Args:
            source_guid: 源资源GUID
            options: 查询选项
            
        Returns:
            QueryResult: 查询结果
        """
        self.logger.debug(f"查询所有依赖: {source_guid}")
        
        # 检查缓存
        cache_key = f"all_{source_guid}_{hash(str(options.__dict__) if options else 'default')}"
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            return cached_result
        
        result = QueryResult('all_dependencies', source_guid)
        options = options or QueryOptions()
        
        try:
            if not self.graph.has_node(source_guid):
                self.logger.warning(f"源资源不存在: {source_guid}")
                result.add_statistic('error', f'Source node {source_guid} not found')
                return result
            
            # 使用DFS遍历所有依赖
            visited = set()
            depth_map = {}
            
            def dfs(node: str, current_depth: int, path: List[str]) -> None:
                if options.max_depth and current_depth > options.max_depth:
                    return
                
                if node in visited:
                    return
                
                visited.add(node)
                depth_map[node] = current_depth
                
                if node != source_guid:
                    result.add_dependency(node)
                    result.add_path(path.copy())
                
                # 遍历后继节点
                for successor in self.graph.get_successors(node):
                    edge_data = self.graph.get_edge_data(node, successor)
                    
                    if edge_data and options.should_include_edge(edge_data):
                        new_path = path + [successor]
                        dfs(successor, current_depth + 1, new_path)
            
            # 开始DFS遍历
            dfs(source_guid, 0, [source_guid])
            
            # 添加统计信息
            result.add_statistic('total_count', len(result.dependencies))
            result.add_statistic('max_depth', max(depth_map.values()) if depth_map else 0)
            result.add_statistic('paths_count', len(result.paths))
            result.add_statistic('depth_distribution', self._calculate_depth_distribution(depth_map))
            
            # 缓存结果
            self._cache_result(cache_key, result)
            
        except Exception as e:
            self.logger.error(f"查询所有依赖失败 {source_guid}: {e}")
            result.add_statistic('error', str(e))
        
        return result
    
    def get_dependency_path(
        self,
        source_guid: str,
        target_guid: str,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """查找两个资源间的依赖路径
        
        Args:
            source_guid: 源资源GUID
            target_guid: 目标资源GUID
            options: 查询选项
            
        Returns:
            QueryResult: 查询结果
        """
        self.logger.debug(f"查询依赖路径: {source_guid} -> {target_guid}")
        
        result = QueryResult('dependency_path', source_guid, target_guid)
        options = options or QueryOptions()
        
        try:
            if not self.graph.has_node(source_guid) or not self.graph.has_node(target_guid):
                error_msg = f"节点不存在: source={source_guid}, target={target_guid}"
                self.logger.warning(error_msg)
                result.add_statistic('error', error_msg)
                return result
            
            # 使用NetworkX的shortest_path查找最短路径
            try:
                # 创建过滤后的子图
                filtered_edges = []
                for source, target, data in self.graph.graph.edges(data=True):
                    if options.should_include_edge(data):
                        filtered_edges.append((source, target))
                
                subgraph = self.graph.graph.edge_subgraph(filtered_edges)
                
                # 查找最短路径
                if nx.has_path(subgraph, source_guid, target_guid):
                    shortest_path = nx.shortest_path(subgraph, source_guid, target_guid)
                    result.add_path(shortest_path)
                    
                    # 查找所有简单路径（限制数量避免性能问题）
                    try:
                        all_paths = list(nx.all_simple_paths(
                            subgraph, 
                            source_guid, 
                            target_guid,
                            cutoff=options.max_depth or 10
                        ))
                        
                        # 限制路径数量
                        if len(all_paths) > 100:
                            all_paths = all_paths[:100]
                            result.add_statistic('paths_truncated', True)
                        
                        for path in all_paths:
                            result.add_path(path)
                    
                    except Exception as e:
                        self.logger.warning(f"查找所有路径失败: {e}")
                
                else:
                    result.add_statistic('path_exists', False)
            
            except nx.NetworkXNoPath:
                result.add_statistic('path_exists', False)
            
            # 添加统计信息
            result.add_statistic('paths_found', len(result.paths))
            if result.paths:
                path_lengths = [len(path) - 1 for path in result.paths]  # 减1因为路径长度是边数
                result.add_statistic('shortest_path_length', min(path_lengths))
                result.add_statistic('longest_path_length', max(path_lengths))
                result.add_statistic('average_path_length', sum(path_lengths) / len(path_lengths))
            
        except Exception as e:
            self.logger.error(f"查询依赖路径失败 {source_guid} -> {target_guid}: {e}")
            result.add_statistic('error', str(e))
        
        return result
    
    def build_dependency_tree(
        self,
        source_guid: str,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """构建依赖树结构
        
        Args:
            source_guid: 源资源GUID
            options: 查询选项
            
        Returns:
            QueryResult: 包含树结构的查询结果
        """
        self.logger.debug(f"构建依赖树: {source_guid}")
        
        result = QueryResult('dependency_tree', source_guid)
        options = options or QueryOptions()
        
        try:
            if not self.graph.has_node(source_guid):
                self.logger.warning(f"源资源不存在: {source_guid}")
                result.add_statistic('error', f'Source node {source_guid} not found')
                return result
            
            def build_tree_recursive(node: str, current_depth: int, visited: Set[str]) -> Dict[str, Any]:
                """递归构建树结构"""
                if options.max_depth and current_depth > options.max_depth:
                    return {'guid': node, 'children': [], 'truncated': True}
                
                if node in visited:
                    return {'guid': node, 'children': [], 'circular': True}
                
                visited_copy = visited.copy()
                visited_copy.add(node)
                
                # 获取节点数据
                node_data = self.graph.get_node_data(node) or {}
                
                tree_node = {
                    'guid': node,
                    'asset_type': node_data.get('asset_type'),
                    'file_path': node_data.get('file_path'),
                    'depth': current_depth,
                    'children': []
                }
                
                # 获取直接依赖
                for successor in self.graph.get_successors(node):
                    edge_data = self.graph.get_edge_data(node, successor)
                    
                    if edge_data and options.should_include_edge(edge_data):
                        child_tree = build_tree_recursive(successor, current_depth + 1, visited_copy)
                        
                        # 添加边信息
                        child_tree['edge_info'] = {
                            'dependency_type': edge_data.get('dependency_type'),
                            'dependency_strength': edge_data.get('dependency_strength'),
                            'context_path': edge_data.get('context_path')
                        }
                        
                        tree_node['children'].append(child_tree)
                
                return tree_node
            
            # 构建树
            tree = build_tree_recursive(source_guid, 0, set())
            result.set_tree(tree)
            
            # 计算统计信息
            def count_nodes(tree_node: Dict[str, Any]) -> Tuple[int, int]:
                """计算节点数和最大深度"""
                node_count = 1
                max_depth = tree_node.get('depth', 0)
                
                for child in tree_node.get('children', []):
                    child_count, child_depth = count_nodes(child)
                    node_count += child_count
                    max_depth = max(max_depth, child_depth)
                
                return node_count, max_depth
            
            total_nodes, max_depth = count_nodes(tree)
            result.add_statistic('total_nodes', total_nodes)
            result.add_statistic('max_depth', max_depth)
            result.add_statistic('direct_children', len(tree.get('children', [])))
            
        except Exception as e:
            self.logger.error(f"构建依赖树失败 {source_guid}: {e}")
            result.add_statistic('error', str(e))
        
        return result
    
    def batch_query_dependencies(
        self,
        source_guids: List[str],
        query_type: str = 'direct',
        options: Optional[QueryOptions] = None
    ) -> Dict[str, QueryResult]:
        """批量查询多个资源的依赖关系
        
        Args:
            source_guids: 源资源GUID列表
            query_type: 查询类型 ('direct', 'all', 'tree')
            options: 查询选项
            
        Returns:
            Dict[str, QueryResult]: 查询结果字典
        """
        self.logger.info(f"批量查询依赖: {len(source_guids)} 个资源, 类型: {query_type}")
        
        results = {}
        
        for guid in source_guids:
            try:
                if query_type == 'direct':
                    result = self.get_direct_dependencies(guid, options)
                elif query_type == 'all':
                    result = self.get_all_dependencies(guid, options)
                elif query_type == 'tree':
                    result = self.build_dependency_tree(guid, options)
                else:
                    result = QueryResult(f'unknown_{query_type}', guid)
                    result.add_statistic('error', f'Unknown query type: {query_type}')
                
                results[guid] = result
                
            except Exception as e:
                self.logger.error(f"批量查询失败 {guid}: {e}")
                error_result = QueryResult(f'batch_{query_type}', guid)
                error_result.add_statistic('error', str(e))
                results[guid] = error_result
        
        return results
    
    def _get_cached_result(self, cache_key: str) -> Optional[QueryResult]:
        """获取缓存结果
        
        Args:
            cache_key: 缓存键
            
        Returns:
            Optional[QueryResult]: 缓存的结果，如果不存在或过期则返回None
        """
        with self._cache_lock:
            if cache_key not in self._cache:
                return None
            
            # 检查缓存是否过期
            timestamp = self._cache_timestamps.get(cache_key)
            if timestamp and (datetime.utcnow() - timestamp).total_seconds() > self._cache_ttl:
                del self._cache[cache_key]
                del self._cache_timestamps[cache_key]
                return None
            
            return self._cache[cache_key]
    
    def _cache_result(self, cache_key: str, result: QueryResult) -> None:
        """缓存查询结果
        
        Args:
            cache_key: 缓存键
            result: 查询结果
        """
        with self._cache_lock:
            self._cache[cache_key] = result
            self._cache_timestamps[cache_key] = datetime.utcnow()
            
            # 清理过期缓存
            self._cleanup_expired_cache()
    
    def _cleanup_expired_cache(self) -> None:
        """清理过期的缓存项"""
        current_time = datetime.utcnow()
        expired_keys = []
        
        for key, timestamp in self._cache_timestamps.items():
            if (current_time - timestamp).total_seconds() > self._cache_ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            if key in self._cache:
                del self._cache[key]
            if key in self._cache_timestamps:
                del self._cache_timestamps[key]
    
    def _calculate_depth_distribution(self, depth_map: Dict[str, int]) -> Dict[int, int]:
        """计算深度分布
        
        Args:
            depth_map: 深度映射
            
        Returns:
            Dict[int, int]: 深度分布统计
        """
        distribution = defaultdict(int)
        for depth in depth_map.values():
            distribution[depth] += 1
        return dict(distribution)
    
    def clear_cache(self) -> None:
        """清空查询缓存"""
        with self._cache_lock:
            self._cache.clear()
            self._cache_timestamps.clear()
            self.logger.info("查询缓存已清空")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息
        
        Returns:
            Dict[str, Any]: 缓存统计
        """
        with self._cache_lock:
            return {
                'cache_size': len(self._cache),
                'cache_ttl_seconds': self._cache_ttl,
                'oldest_entry': min(self._cache_timestamps.values()) if self._cache_timestamps else None,
                'newest_entry': max(self._cache_timestamps.values()) if self._cache_timestamps else None
            }
    
    def set_cache_ttl(self, ttl_seconds: int) -> None:
        """设置缓存TTL
        
        Args:
            ttl_seconds: 缓存时间（秒）
        """
        if ttl_seconds > 0:
            self._cache_ttl = ttl_seconds
            self.logger.info(f"缓存TTL设置为: {ttl_seconds} 秒")
    
    # ===== 被引用关系查询功能 =====
    
    def get_direct_references(
        self,
        target_guid: str,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """获取直接引用指定资源的其他资源
        
        Args:
            target_guid: 目标资源GUID
            options: 查询选项
            
        Returns:
            QueryResult: 查询结果，包含引用该资源的资源列表
        """
        self.logger.debug(f"查询直接引用: {target_guid}")
        
        # 检查缓存
        cache_key = f"direct_ref_{target_guid}_{hash(str(options.__dict__) if options else 'default')}"
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            return cached_result
        
        result = QueryResult('direct_references', source_guid='', target_guid=target_guid)
        options = options or QueryOptions()
        
        try:
            if not self.graph.has_node(target_guid):
                self.logger.warning(f"目标资源不存在: {target_guid}")
                result.add_statistic('error', f'Target node {target_guid} not found')
                return result
                
            # 获取直接前驱节点（引用该资源的节点）
            predecessors = self.graph.get_predecessors(target_guid)
            
            for predecessor in predecessors:
                edge_data = self.graph.get_edge_data(predecessor, target_guid)
                
                # 应用过滤条件
                if edge_data and options.should_include_edge(edge_data):
                    result.add_dependency(predecessor)
                    result.add_path([predecessor, target_guid])
            
            # 添加统计信息
            result.add_statistic('direct_references_count', len(result.dependencies))
            result.add_statistic('reference_paths_count', len(result.paths))
            
            # 缓存结果
            self._cache_result(cache_key, result)
            
        except Exception as e:
            self.logger.error(f"查询直接引用失败 {target_guid}: {e}")
            result.add_statistic('error', str(e))
        
        return result
    
    def get_all_references(
        self,
        target_guid: str,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """获取所有引用指定资源的资源（直接和间接引用）
        
        Args:
            target_guid: 目标资源GUID
            options: 查询选项
            
        Returns:
            QueryResult: 查询结果，包含所有引用该资源的资源树
        """
        self.logger.debug(f"查询所有引用: {target_guid}")
        
        # 检查缓存
        cache_key = f"all_ref_{target_guid}_{hash(str(options.__dict__) if options else 'default')}"
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            return cached_result
        
        result = QueryResult('all_references', source_guid='', target_guid=target_guid)
        options = options or QueryOptions()
        
        try:
            if not self.graph.has_node(target_guid):
                self.logger.warning(f"目标资源不存在: {target_guid}")
                result.add_statistic('error', f'Target node {target_guid} not found')
                return result
            
            # 使用反向DFS遍历所有引用
            visited = set()
            depth_map = {}
            
            def reverse_dfs(node: str, current_depth: int) -> None:
                """反向深度优先搜索"""
                if node in visited:
                    return
                    
                if options.max_depth is not None and current_depth > options.max_depth:
                    return
                
                visited.add(node)
                depth_map[node] = current_depth
                
                # 获取前驱节点（引用当前节点的节点）
                for predecessor in self.graph.get_predecessors(node):
                    edge_data = self.graph.get_edge_data(predecessor, node)
                    
                    # 应用过滤条件
                    if edge_data and options.should_include_edge(edge_data):
                        if predecessor not in visited:
                            result.add_dependency(predecessor)
                        reverse_dfs(predecessor, current_depth + 1)
            
            # 从目标节点开始反向遍历
            reverse_dfs(target_guid, 0)
            
            # 移除目标节点本身
            if target_guid in result.dependencies:
                result.dependencies.remove(target_guid)
            
            # 添加统计信息
            result.add_statistic('total_references_count', len(result.dependencies))
            result.add_statistic('max_reference_depth', max(depth_map.values()) if depth_map else 0)
            result.add_statistic('depth_distribution', self._calculate_depth_distribution(depth_map))
            
            # 缓存结果
            self._cache_result(cache_key, result)
            
        except Exception as e:
            self.logger.error(f"查询所有引用失败 {target_guid}: {e}")
            result.add_statistic('error', str(e))
        
        return result
    
    def get_impact_analysis(
        self,
        target_guid: str,
        analysis_type: str = 'delete',
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """分析删除或修改资源的影响范围
        
        Args:
            target_guid: 目标资源GUID
            analysis_type: 分析类型 ('delete', 'modify', 'move')
            options: 查询选项
            
        Returns:
            QueryResult: 影响分析结果
        """
        self.logger.debug(f"影响范围分析: {target_guid}, 类型: {analysis_type}")
        
        result = QueryResult(f'impact_analysis_{analysis_type}', source_guid='', target_guid=target_guid)
        options = options or QueryOptions()
        
        try:
            if not self.graph.has_node(target_guid):
                self.logger.warning(f"目标资源不存在: {target_guid}")
                result.add_statistic('error', f'Target node {target_guid} not found')
                return result
            
            # 获取所有引用该资源的节点
            all_references = self.get_all_references(target_guid, options)
            
            # 根据分析类型计算影响
            if analysis_type == 'delete':
                # 删除影响：所有引用该资源的节点都会受到影响
                result.dependencies = all_references.dependencies.copy()
                result.add_statistic('affected_assets_count', len(result.dependencies))
                result.add_statistic('impact_severity', 'HIGH' if len(result.dependencies) > 10 else 'MEDIUM' if len(result.dependencies) > 0 else 'LOW')
                
            elif analysis_type == 'modify':
                # 修改影响：需要重新分析依赖强度
                strong_references = []
                weak_references = []
                
                for ref_guid in all_references.dependencies:
                    edge_data = self.graph.get_edge_data(ref_guid, target_guid)
                    if edge_data:
                        strength = edge_data.get('strength', DependencyStrength.WEAK)
                        if strength in [DependencyStrength.STRONG, DependencyStrength.CRITICAL]:
                            strong_references.append(ref_guid)
                        else:
                            weak_references.append(ref_guid)
                
                result.dependencies = strong_references + weak_references
                result.add_statistic('strong_references_count', len(strong_references))
                result.add_statistic('weak_references_count', len(weak_references))
                result.add_statistic('impact_severity', 'HIGH' if len(strong_references) > 5 else 'MEDIUM' if len(strong_references) > 0 else 'LOW')
                
            elif analysis_type == 'move':
                # 移动影响：分析路径依赖
                path_dependent = []
                guid_dependent = []
                
                for ref_guid in all_references.dependencies:
                    edge_data = self.graph.get_edge_data(ref_guid, target_guid)
                    if edge_data:
                        dep_type = edge_data.get('dependency_type', DependencyType.REFERENCE)
                        if dep_type in [DependencyType.PATH_REFERENCE, DependencyType.RESOURCE_PATH]:
                            path_dependent.append(ref_guid)
                        else:
                            guid_dependent.append(ref_guid)
                
                result.dependencies = path_dependent + guid_dependent
                result.add_statistic('path_dependent_count', len(path_dependent))
                result.add_statistic('guid_dependent_count', len(guid_dependent))
                result.add_statistic('impact_severity', 'HIGH' if len(path_dependent) > 0 else 'LOW')
            
            # 添加通用统计信息
            result.add_statistic('analysis_type', analysis_type)
            result.add_statistic('total_affected_count', len(result.dependencies))
            
        except Exception as e:
            self.logger.error(f"影响分析失败 {target_guid}: {e}")
            result.add_statistic('error', str(e))
        
        return result
    
    def build_reference_tree(
        self,
        target_guid: str,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """构建引用该资源的树形结构
        
        Args:
            target_guid: 目标资源GUID
            options: 查询选项
            
        Returns:
            QueryResult: 包含引用树结构的查询结果
        """
        self.logger.debug(f"构建引用树: {target_guid}")
        
        # 检查缓存
        cache_key = f"ref_tree_{target_guid}_{hash(str(options.__dict__) if options else 'default')}"
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            return cached_result
        
        result = QueryResult('reference_tree', source_guid='', target_guid=target_guid)
        options = options or QueryOptions()
        
        try:
            if not self.graph.has_node(target_guid):
                self.logger.warning(f"目标资源不存在: {target_guid}")
                result.add_statistic('error', f'Target node {target_guid} not found')
                return result
            
            # 构建引用树
            def build_tree_recursive(node: str, current_depth: int, visited: Set[str]) -> Dict[str, Any]:
                """递归构建引用树"""
                if node in visited or (options.max_depth is not None and current_depth > options.max_depth):
                    return {'guid': node, 'children': [], 'depth': current_depth, 'circular': node in visited}
                
                visited_copy = visited.copy()
                visited_copy.add(node)
                
                node_data = self.graph.get_node_data(node) or {}
                children = []
                
                # 获取引用该节点的前驱节点
                for predecessor in self.graph.get_predecessors(node):
                    edge_data = self.graph.get_edge_data(predecessor, node)
                    
                    if edge_data and options.should_include_edge(edge_data):
                        child_tree = build_tree_recursive(predecessor, current_depth + 1, visited_copy)
                        children.append(child_tree)
                
                return {
                    'guid': node,
                    'name': node_data.get('name', node),
                    'asset_type': node_data.get('asset_type', 'unknown'),
                    'children': children,
                    'depth': current_depth,
                    'child_count': len(children),
                    'circular': False
                }
            
            # 从目标节点开始构建引用树
            tree_data = build_tree_recursive(target_guid, 0, set())
            result.tree = tree_data
            
            # 计算统计信息
            def calculate_tree_stats(tree_node: Dict[str, Any]) -> Dict[str, int]:
                """计算树统计信息"""
                stats = {'total_nodes': 1, 'max_depth': tree_node['depth'], 'leaf_nodes': 0}
                
                if not tree_node['children']:
                    stats['leaf_nodes'] = 1
                else:
                    for child in tree_node['children']:
                        child_stats = calculate_tree_stats(child)
                        stats['total_nodes'] += child_stats['total_nodes']
                        stats['max_depth'] = max(stats['max_depth'], child_stats['max_depth'])
                        stats['leaf_nodes'] += child_stats['leaf_nodes']
                
                return stats
            
            tree_stats = calculate_tree_stats(tree_data)
            result.statistics.update(tree_stats)
            
            # 缓存结果
            self._cache_result(cache_key, result)
            
        except Exception as e:
            self.logger.error(f"构建引用树失败 {target_guid}: {e}")
            result.add_statistic('error', str(e))
        
        return result
    
    def get_reference_strength_analysis(
        self,
        target_guid: str,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """分析资源的引用强度分布
        
        Args:
            target_guid: 目标资源GUID
            options: 查询选项
            
        Returns:
            QueryResult: 引用强度分析结果
        """
        self.logger.debug(f"引用强度分析: {target_guid}")
        
        result = QueryResult('reference_strength_analysis', source_guid='', target_guid=target_guid)
        options = options or QueryOptions()
        
        try:
            if not self.graph.has_node(target_guid):
                self.logger.warning(f"目标资源不存在: {target_guid}")
                result.add_statistic('error', f'Target node {target_guid} not found')
                return result
            
            # 统计不同强度的引用
            strength_stats = defaultdict(int)
            type_stats = defaultdict(int)
            strength_by_type = defaultdict(lambda: defaultdict(int))
            
            for predecessor in self.graph.get_predecessors(target_guid):
                edge_data = self.graph.get_edge_data(predecessor, target_guid)
                
                if edge_data and options.should_include_edge(edge_data):
                    strength = edge_data.get('strength', DependencyStrength.WEAK)
                    dep_type = edge_data.get('dependency_type', DependencyType.REFERENCE)
                    
                    strength_stats[strength.value if hasattr(strength, 'value') else str(strength)] += 1
                    type_stats[dep_type.value if hasattr(dep_type, 'value') else str(dep_type)] += 1
                    strength_by_type[str(dep_type)][str(strength)] += 1
                    
                    result.add_dependency(predecessor)
            
            # 添加统计信息
            result.add_statistic('strength_distribution', dict(strength_stats))
            result.add_statistic('type_distribution', dict(type_stats))
            result.add_statistic('strength_by_type', dict(strength_by_type))
            result.add_statistic('total_references', len(result.dependencies))
            
            # 计算引用重要性评分
            importance_score = 0
            for strength, count in strength_stats.items():
                if 'CRITICAL' in str(strength).upper():
                    importance_score += count * 10
                elif 'STRONG' in str(strength).upper():
                    importance_score += count * 5
                elif 'MEDIUM' in str(strength).upper():
                    importance_score += count * 2
                else:
                    importance_score += count * 1
            
            result.add_statistic('importance_score', importance_score)
            result.add_statistic('importance_level', 
                'CRITICAL' if importance_score > 50 else 
                'HIGH' if importance_score > 20 else 
                'MEDIUM' if importance_score > 5 else 'LOW')
            
        except Exception as e:
            self.logger.error(f"引用强度分析失败 {target_guid}: {e}")
            result.add_statistic('error', str(e))
        
        return result
    
    def get_reference_path(
        self,
        source_guid: str,
        target_guid: str,
        find_all_paths: bool = False,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """查找从引用源到目标资源的引用路径
        
        Args:
            source_guid: 引用源资源GUID
            target_guid: 目标资源GUID
            find_all_paths: 是否查找所有路径
            options: 查询选项
            
        Returns:
            QueryResult: 引用路径查询结果
        """
        self.logger.debug(f"查询引用路径: {source_guid} -> {target_guid}")
        
        result = QueryResult('reference_path', source_guid, target_guid)
        options = options or QueryOptions()
        
        try:
            if not self.graph.has_node(source_guid) or not self.graph.has_node(target_guid):
                error_msg = f"节点不存在: source={source_guid}, target={target_guid}"
                self.logger.warning(error_msg)
                result.add_statistic('error', error_msg)
                return result
            
            # 使用NetworkX查找路径
            if find_all_paths:
                try:
                    paths = list(nx.all_simple_paths(self.graph._graph, source_guid, target_guid, 
                                                   cutoff=options.max_depth))
                    result.paths = paths
                    result.add_statistic('total_paths', len(paths))
                    result.add_statistic('shortest_path_length', min(len(p) for p in paths) if paths else 0)
                    result.add_statistic('longest_path_length', max(len(p) for p in paths) if paths else 0)
                except nx.NetworkXNoPath:
                    result.add_statistic('error', f'No path found from {source_guid} to {target_guid}')
            else:
                try:
                    shortest_path = nx.shortest_path(self.graph._graph, source_guid, target_guid)
                    result.paths = [shortest_path]
                    result.add_statistic('path_length', len(shortest_path))
                    result.add_statistic('path_found', True)
                except nx.NetworkXNoPath:
                    result.add_statistic('error', f'No path found from {source_guid} to {target_guid}')
                    result.add_statistic('path_found', False)
            
            # 添加路径详细信息
            if result.paths:
                path_details = []
                for path in result.paths:
                    path_info = {'nodes': path, 'edges': []}
                    for i in range(len(path) - 1):
                        edge_data = self.graph.get_edge_data(path[i], path[i + 1])
                        path_info['edges'].append({
                            'from': path[i],
                            'to': path[i + 1],
                            'data': edge_data
                        })
                    path_details.append(path_info)
                
                result.add_statistic('path_details', path_details)
            
        except Exception as e:
            self.logger.error(f"查询引用路径失败 {source_guid} -> {target_guid}: {e}")
            result.add_statistic('error', str(e))
        
        return result
    
    def validate_references(
        self,
        target_guid: str,
        options: Optional[QueryOptions] = None
    ) -> QueryResult:
        """验证引用关系的有效性和一致性
        
        Args:
            target_guid: 目标资源GUID
            options: 查询选项
            
        Returns:
            QueryResult: 引用验证结果
        """
        self.logger.debug(f"验证引用关系: {target_guid}")
        
        result = QueryResult('reference_validation', source_guid='', target_guid=target_guid)
        options = options or QueryOptions()
        
        try:
            if not self.graph.has_node(target_guid):
                result.add_statistic('error', f'Target node {target_guid} not found')
                return result
            
            validation_issues = []
            valid_references = []
            invalid_references = []
            
            # 检查所有引用该资源的节点
            for predecessor in self.graph.get_predecessors(target_guid):
                edge_data = self.graph.get_edge_data(predecessor, target_guid)
                
                if not edge_data:
                    validation_issues.append({
                        'type': 'missing_edge_data',
                        'source': predecessor,
                        'target': target_guid,
                        'severity': 'HIGH'
                    })
                    invalid_references.append(predecessor)
                    continue
                
                # 检查必要的边属性
                required_attrs = ['dependency_type', 'strength']
                missing_attrs = [attr for attr in required_attrs if attr not in edge_data]
                
                if missing_attrs:
                    validation_issues.append({
                        'type': 'missing_attributes',
                        'source': predecessor,
                        'target': target_guid,
                        'missing_attrs': missing_attrs,
                        'severity': 'MEDIUM'
                    })
                
                # 检查属性值的有效性
                if 'dependency_type' in edge_data:
                    dep_type = edge_data['dependency_type']
                    if not isinstance(dep_type, (DependencyType, str)):
                        validation_issues.append({
                            'type': 'invalid_dependency_type',
                            'source': predecessor,
                            'target': target_guid,
                            'value': dep_type,
                            'severity': 'MEDIUM'
                        })
                
                if 'strength' in edge_data:
                    strength = edge_data['strength']
                    if not isinstance(strength, (DependencyStrength, str, float, int)):
                        validation_issues.append({
                            'type': 'invalid_strength',
                            'source': predecessor,
                            'target': target_guid,
                            'value': strength,
                            'severity': 'MEDIUM'
                        })
                
                # 检查循环引用
                try:
                    if nx.has_path(self.graph._graph, target_guid, predecessor):
                        validation_issues.append({
                            'type': 'circular_reference',
                            'source': predecessor,
                            'target': target_guid,
                            'severity': 'HIGH'
                        })
                except:
                    pass
                
                if not validation_issues or validation_issues[-1]['source'] != predecessor:
                    valid_references.append(predecessor)
                else:
                    invalid_references.append(predecessor)
            
            # 添加验证结果
            result.dependencies = valid_references
            result.add_statistic('validation_issues', validation_issues)
            result.add_statistic('total_references', len(valid_references) + len(invalid_references))
            result.add_statistic('valid_references_count', len(valid_references))
            result.add_statistic('invalid_references_count', len(invalid_references))
            result.add_statistic('issues_count', len(validation_issues))
            
            # 计算验证评分
            total_refs = len(valid_references) + len(invalid_references)
            if total_refs > 0:
                validation_score = (len(valid_references) / total_refs) * 100
                result.add_statistic('validation_score', validation_score)
                result.add_statistic('validation_status', 
                    'EXCELLENT' if validation_score >= 95 else
                    'GOOD' if validation_score >= 80 else
                    'POOR' if validation_score >= 60 else 'CRITICAL')
            else:
                result.add_statistic('validation_score', 100)
                result.add_statistic('validation_status', 'NO_REFERENCES')
            
        except Exception as e:
            self.logger.error(f"引用验证失败 {target_guid}: {e}")
            result.add_statistic('error', str(e))
        
        return result
    
    def batch_reference_query(
        self,
        target_guids: List[str],
        query_type: str = 'direct_references',
        options: Optional[QueryOptions] = None
    ) -> Dict[str, QueryResult]:
        """批量查询多个资源的引用关系
        
        Args:
            target_guids: 目标资源GUID列表
            query_type: 查询类型 ('direct_references', 'all_references', 'impact_analysis', 'reference_tree')
            options: 查询选项
            
        Returns:
            Dict[str, QueryResult]: 批量查询结果字典
        """
        self.logger.debug(f"批量引用查询: {len(target_guids)} 个资源, 类型: {query_type}")
        
        results = {}
        
        try:
            for target_guid in target_guids:
                if query_type == 'direct_references':
                    results[target_guid] = self.get_direct_references(target_guid, options)
                elif query_type == 'all_references':
                    results[target_guid] = self.get_all_references(target_guid, options)
                elif query_type == 'impact_analysis':
                    results[target_guid] = self.get_impact_analysis(target_guid, 'delete', options)
                elif query_type == 'reference_tree':
                    results[target_guid] = self.build_reference_tree(target_guid, options)
                elif query_type == 'strength_analysis':
                    results[target_guid] = self.get_reference_strength_analysis(target_guid, options)
                elif query_type == 'validate_references':
                    results[target_guid] = self.validate_references(target_guid, options)
                else:
                    error_result = QueryResult(f'unsupported_{query_type}', source_guid='', target_guid=target_guid)
                    error_result.add_statistic('error', f'Unsupported query type: {query_type}')
                    results[target_guid] = error_result
            
            self.logger.info(f"批量引用查询完成: {len(results)} 个结果")
            
        except Exception as e:
            self.logger.error(f"批量引用查询失败: {e}")
            # 为剩余的GUID添加错误结果
            for target_guid in target_guids:
                if target_guid not in results:
                    error_result = QueryResult(f'batch_error_{query_type}', source_guid='', target_guid=target_guid)
                    error_result.add_statistic('error', str(e))
                    results[target_guid] = error_result
        
        return results
