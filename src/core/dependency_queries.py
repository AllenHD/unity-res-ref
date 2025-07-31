"""Unity Resource Reference Scanner - Dependency Queries Module

正向依赖查询功能的实现，包括直接依赖、间接依赖、路径查询和树构建。
"""

from typing import Dict, List, Set, Optional, Any, Tuple
from datetime import datetime
import logging
from collections import defaultdict

import networkx as nx

from .query_types import QueryOptions, QueryResult


class DependencyQueryMixin:
    """正向依赖查询混入类
    
    提供正向依赖查询的所有方法，包括直接依赖、间接依赖、路径查询和树构建。
    """
    
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
                """深度优先搜索遍历依赖"""
                if node in visited:
                    return
                
                if options.max_depth is not None and current_depth > options.max_depth:
                    return
                
                visited.add(node)
                depth_map[node] = current_depth
                
                if node != source_guid:
                    result.add_dependency(node)
                    if len(path) > 1:
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
                shortest_path = nx.shortest_path(self.graph._graph, source_guid, target_guid)
                result.add_path(shortest_path)
                result.add_statistic('path_found', True)
                result.add_statistic('path_length', len(shortest_path) - 1)
            except nx.NetworkXNoPath:
                result.add_statistic('error', f'No path found from {source_guid} to {target_guid}')
                result.add_statistic('path_found', False)
            
            # 添加统计信息
            result.add_statistic('paths_found', len(result.paths))
            if result.paths:
                result.add_statistic('shortest_path_length', min(len(p) - 1 for p in result.paths))
                result.add_statistic('longest_path_length', max(len(p) - 1 for p in result.paths))
            
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
                """递归构建依赖树"""
                if node in visited or (options.max_depth is not None and current_depth > options.max_depth):
                    return {
                        'guid': node,
                        'children': [],
                        'depth': current_depth,
                        'circular': node in visited
                    }
                
                visited_copy = visited.copy()
                visited_copy.add(node)
                
                node_data = self.graph.get_node_data(node) or {}
                children = []
                
                # 获取后继节点
                for successor in self.graph.get_successors(node):
                    edge_data = self.graph.get_edge_data(node, successor)
                    
                    if edge_data and options.should_include_edge(edge_data):
                        child_tree = build_tree_recursive(successor, current_depth + 1, visited_copy)
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
            
            # 构建树
            tree = build_tree_recursive(source_guid, 0, set())
            result.set_tree(tree)
            
            # 计算统计信息
            def count_nodes(tree_node: Dict[str, Any]) -> Tuple[int, int]:
                """计算树节点数和最大深度"""
                node_count = 1
                max_depth = tree_node['depth']
                
                for child in tree_node.get('children', []):
                    child_count, child_max_depth = count_nodes(child)
                    node_count += child_count
                    max_depth = max(max_depth, child_max_depth)
                
                return node_count, max_depth
            
            total_nodes, max_depth = count_nodes(tree)
            result.add_statistic('total_nodes', total_nodes)
            result.add_statistic('max_depth', max_depth)
            result.add_statistic('direct_children', len(tree.get('children', [])))
            
        except Exception as e:
            self.logger.error(f"构建依赖树失败 {source_guid}: {e}")
            result.add_statistic('error', str(e))
        
        return result
    
    def batch_dependency_query(
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
                    results[guid] = self.get_direct_dependencies(guid, options)
                elif query_type == 'all':
                    results[guid] = self.get_all_dependencies(guid, options)
                elif query_type == 'tree':
                    results[guid] = self.build_dependency_tree(guid, options)
                else:
                    error_result = QueryResult(f'unsupported_{query_type}', guid)
                    error_result.add_statistic('error', f'Unsupported query type: {query_type}')
                    results[guid] = error_result
                    
            except Exception as e:
                error_result = QueryResult(f'batch_error_{query_type}', guid)
                error_result.add_statistic('error', str(e))
                results[guid] = error_result
        
        return results
    
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
