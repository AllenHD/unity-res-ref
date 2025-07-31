"""Unity Resource Reference Scanner - Graph Builder Module

负责从数据库批量加载Asset和Dependency数据构建内存图的核心算法。
提供高效的数据库查询、数据预处理、图构建等功能。
"""

from typing import Dict, List, Set, Optional, Any, Tuple, Union, Callable
from datetime import datetime, timedelta
import threading
import logging
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from ..models.asset import Asset, AssetType
from ..models.dependency import Dependency, DependencyType, DependencyStrength
from .database import DatabaseManager, get_asset_dao, get_dependency_dao


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
    ) -> 'DependencyGraph':
        """从数据库构建依赖关系图
        
        Args:
            progress_callback: 进度回调函数
            asset_filter: 资源过滤条件
            dependency_filter: 依赖关系过滤条件
            
        Returns:
            DependencyGraph: 构建的依赖关系图
        """
        # 需要导入DependencyGraph，但为了避免循环导入，在方法内部导入
        from .dependency_graph import DependencyGraph
        
        self.logger.info("开始从数据库构建依赖关系图")
        start_time = datetime.utcnow()
        
        graph = DependencyGraph()
        
        try:
            with self.db_manager.get_session() as session:
                # 构建节点
                self._build_nodes(session, graph, progress_callback, asset_filter)
                
                # 构建边
                self._build_edges(session, graph, progress_callback, dependency_filter)
                
                # 验证和优化
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
    ) -> 'DependencyGraph':
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
        base_graph: Optional['DependencyGraph'] = None,
        since_timestamp: Optional[datetime] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> 'DependencyGraph':
        """构建增量依赖关系图（基于时间戳）
        
        Args:
            base_graph: 基础图，如果为None则创建新图
            since_timestamp: 增量更新的起始时间戳
            progress_callback: 进度回调函数
            
        Returns:
            DependencyGraph: 更新后的依赖关系图
        """
        from .dependency_graph import DependencyGraph
        
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
        graph: 'DependencyGraph',
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
                node_data = {
                    'name': asset.name,
                    'asset_type': asset.asset_type.value if asset.asset_type else 'unknown',
                    'file_path': asset.file_path,
                    'file_size': asset.file_size,
                    'is_active': asset.is_active,
                    'is_analyzed': asset.is_analyzed,
                    'created_at': asset.created_at.isoformat() if asset.created_at else None,
                    'updated_at': asset.updated_at.isoformat() if asset.updated_at else None
                }
                
                graph.add_asset_node(asset.guid, node_data)
                processed_count += 1
            
            batch_count += 1
            
            # 报告进度
            if progress_callback and batch_count % 10 == 0:
                progress = min(100, (processed_count / total_assets) * 100)
                progress_callback({
                    'stage': 'nodes',
                    'message': f'已加载 {processed_count}/{total_assets} 个资源节点',
                    'progress': progress
                })
        
        self.logger.info(f"完成节点构建，共加载 {processed_count} 个节点")
    
    def _build_edges(
        self,
        session: Session,
        graph: 'DependencyGraph',
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
                # 检查源节点和目标节点是否存在
                if not graph.has_node(dep.source_guid) or not graph.has_node(dep.target_guid):
                    skipped_count += 1
                    continue
                
                edge_data = {
                    'dependency_type': dep.dependency_type.value if dep.dependency_type else 'unknown',
                    'dependency_strength': dep.strength.value if dep.strength else 'weak',
                    'is_active': dep.is_active,
                    'is_verified': dep.is_verified,
                    'line_number': dep.line_number,
                    'context': dep.context,
                    'created_at': dep.created_at.isoformat() if dep.created_at else None,
                    'updated_at': dep.updated_at.isoformat() if dep.updated_at else None
                }
                
                graph.add_dependency_edge(dep.source_guid, dep.target_guid, edge_data)
                processed_count += 1
            
            batch_count += 1
            
            # 报告进度
            if progress_callback and batch_count % 10 == 0:
                progress = min(100, (processed_count / total_dependencies) * 100)
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
        graph: 'DependencyGraph',
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
                    query = query.filter(Dependency.strength.in_(value))
                else:
                    query = query.filter(Dependency.strength == value)
            elif key == 'updated_at_gte':
                query = query.filter(Dependency.updated_at >= value)
            elif key == 'updated_at_lte':
                query = query.filter(Dependency.updated_at <= value)
        
        return query
    
    def _merge_graphs(self, base_graph: 'DependencyGraph', incremental_graph: 'DependencyGraph') -> None:
        """合并增量图到基础图"""
        self.logger.info("开始合并增量图")
        
        # 合并节点
        for node_id in incremental_graph.graph.nodes():
            node_data = incremental_graph.get_node_data(node_id)
            if base_graph.has_node(node_id):
                base_graph.update_asset_node(node_id, node_data)
            else:
                base_graph.add_asset_node(node_id, node_data)
        
        # 合并边
        for source, target in incremental_graph.graph.edges():
            edge_data = incremental_graph.get_edge_data(source, target)
            if base_graph.has_edge(source, target):
                base_graph.update_dependency_edge(source, target, edge_data)
            else:
                base_graph.add_dependency_edge(source, target, edge_data)
        
        self.logger.info(f"增量图合并完成")
    
    def _generate_build_stats(self, graph: 'DependencyGraph', build_time: float) -> None:
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
    
    def _estimate_memory_usage(self, graph: 'DependencyGraph') -> float:
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
