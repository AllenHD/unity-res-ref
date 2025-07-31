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
