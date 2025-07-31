"""Unity Resource Reference Scanner - Reference Queries Module

反向依赖查询功能的实现，包括引用关系查询、影响分析和引用验证。
"""

from typing import Dict, List, Set, Optional, Any
from datetime import datetime
import logging
from collections import defaultdict

import networkx as nx

from .query_types import QueryOptions, QueryResult
from ..models.dependency import DependencyType, DependencyStrength


class ReferenceQueryMixin:
    """反向依赖查询混入类
    
    提供反向依赖查询的所有方法，包括引用关系查询、影响分析和引用验证。
    """
    
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
