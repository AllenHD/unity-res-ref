"""Unity Resource Reference Scanner - Dependency Graph Core Module

依赖关系图核心模块，基于NetworkX提供完整的图管理和分析功能。
支持图构建、查询、更新和验证等核心操作。
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
        """查找循环依赖
        
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
            # 回退到DFS算法
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
        """获取指定资源的依赖深度
        
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


class DependencyQueryEngine(DependencyQueryMixin, ReferenceQueryMixin):
    """依赖查询引擎
    
    基于图遍历算法提供多种依赖查询模式，包括直接依赖、间接依赖、传递依赖等。
    支持查询深度限制、路径追踪、结果过滤等高级功能。
    
    通过多重继承组合正向和反向查询功能。
    """
    
    def __init__(self, graph: DependencyGraph, cache_ttl: int = 300):
        """初始化查询引擎
        
        Args:
            graph: 依赖关系图
            cache_ttl: 缓存TTL（秒）
        """
        self.graph = graph
        
        # 查询结果缓存
        self._cache: Dict[str, QueryResult] = {}
        self._cache_ttl = cache_ttl
        self._cache_timestamps: Dict[str, datetime] = {}
        self._cache_lock = threading.Lock()
        
        # 日志记录器
        self.logger = logging.getLogger(__name__)
    
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


# 保持向后兼容性的导出
__all__ = [
    'DependencyGraph',
    'DependencyQueryEngine',
    'DependencyGraphBuilder',
    'QueryOptions',
    'QueryResult'
]
