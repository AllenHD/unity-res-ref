"""Unity Resource Reference Scanner - Graph Update Manager

图增量更新管理模块，提供高效的图更新功能，支持动态添加、删除、修改节点和边，
避免全量重建图结构。提供事务性更新、批量更新、冲突检测等机制。
"""

from typing import Dict, List, Set, Optional, Any, Tuple, Union, Callable
from datetime import datetime
import logging
from collections import defaultdict
from enum import Enum
from dataclasses import dataclass, field
import threading
from contextlib import contextmanager
import copy
from pathlib import Path

from ..models.asset import Asset, AssetType
from ..models.dependency import Dependency, DependencyType, DependencyStrength
from ..utils.file_watcher import FileChangeDetector


logger = logging.getLogger(__name__)


class UpdateOperationType(Enum):
    """更新操作类型"""
    ADD_NODE = "add_node"
    REMOVE_NODE = "remove_node"
    UPDATE_NODE = "update_node"
    ADD_EDGE = "add_edge"
    REMOVE_EDGE = "remove_edge"
    UPDATE_EDGE = "update_edge"


class UpdateStatus(Enum):
    """更新状态"""
    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class UpdateOperation:
    """更新操作记录"""
    operation_id: str
    operation_type: UpdateOperationType
    target_id: str  # 节点GUID或边ID
    data: Dict[str, Any]
    old_data: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    status: UpdateStatus = UpdateStatus.PENDING
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'operation_id': self.operation_id,
            'operation_type': self.operation_type.value,
            'target_id': self.target_id,
            'data': self.data,
            'old_data': self.old_data,
            'timestamp': self.timestamp.isoformat(),
            'status': self.status.value,
            'error_message': self.error_message
        }


@dataclass  
class BatchUpdateTransaction:
    """批量更新事务"""
    transaction_id: str
    operations: List[UpdateOperation] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    status: UpdateStatus = UpdateStatus.PENDING
    applied_operations: List[str] = field(default_factory=list)  # 已应用的操作ID
    
    @property
    def duration(self) -> Optional[float]:
        """获取事务持续时间"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'transaction_id': self.transaction_id,
            'operations': [op.to_dict() for op in self.operations],
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'status': self.status.value,
            'applied_operations': self.applied_operations,
            'duration': self.duration
        }


class ConflictType(Enum):
    """冲突类型"""
    NODE_ALREADY_EXISTS = "node_already_exists"
    NODE_NOT_EXISTS = "node_not_exists"
    EDGE_ALREADY_EXISTS = "edge_already_exists"
    EDGE_NOT_EXISTS = "edge_not_exists"
    CIRCULAR_DEPENDENCY = "circular_dependency"
    DATA_INCONSISTENCY = "data_inconsistency"


@dataclass
class UpdateConflict:
    """更新冲突"""
    conflict_type: ConflictType
    operation_id: str
    target_id: str
    description: str
    suggested_resolution: Optional[str] = None


class GraphUpdateManager:
    """图增量更新管理器
    
    管理依赖关系图的增量更新，提供事务性、批量更新、冲突检测等功能
    """
    
    def __init__(self, dependency_graph):
        """初始化更新管理器
        
        Args:
            dependency_graph: 依赖关系图实例
        """
        self.graph = dependency_graph
        self.logger = logging.getLogger(__name__)
        
        # 更新历史记录
        self.update_history: List[UpdateOperation] = []
        self.transaction_history: List[BatchUpdateTransaction] = []
        
        # 冲突检测
        self.conflict_detectors: List[Callable] = []
        
        # 缓存失效管理
        self.cache_invalidation_callbacks: List[Callable] = []
        
        # 线程安全
        self._lock = threading.RLock()
        
        # 事务管理
        self._current_transaction: Optional[BatchUpdateTransaction] = None
        
        # 性能统计
        self.stats = {
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'transactions': 0,
            'conflicts_detected': 0,
            'cache_invalidations': 0
        }
        
        # 注册默认的冲突检测器
        self._register_default_conflict_detectors()
    
    def _register_default_conflict_detectors(self):
        """注册默认的冲突检测器"""
        self.conflict_detectors = [
            self._detect_node_existence_conflicts,
            self._detect_edge_existence_conflicts,
            self._detect_circular_dependency_conflicts,
            self._detect_data_consistency_conflicts
        ]
    
    def add_node(self, 
                 guid: str, 
                 asset_data: Optional[Dict[str, Any]] = None,
                 validate: bool = True) -> bool:
        """添加节点
        
        Args:
            guid: 资源GUID
            asset_data: 资源数据
            validate: 是否进行验证
            
        Returns:
            bool: 是否添加成功
        """
        operation = UpdateOperation(
            operation_id=self._generate_operation_id(),
            operation_type=UpdateOperationType.ADD_NODE,
            target_id=guid,
            data={'asset_data': asset_data or {}}
        )
        
        return self._execute_single_operation(operation, validate)
    
    def remove_node(self, guid: str, validate: bool = True) -> bool:
        """删除节点
        
        Args:
            guid: 资源GUID
            validate: 是否进行验证
            
        Returns:
            bool: 是否删除成功
        """
        # 保存旧数据用于回滚
        old_data = None
        if self.graph.has_asset_node(guid):
            old_data = {
                'asset_data': self.graph.get_node_data(guid),
                'edges': self._get_node_edges(guid)
            }
        
        operation = UpdateOperation(
            operation_id=self._generate_operation_id(),
            operation_type=UpdateOperationType.REMOVE_NODE,
            target_id=guid,
            data={},
            old_data=old_data
        )
        
        return self._execute_single_operation(operation, validate)
    
    def update_node(self, 
                    guid: str, 
                    asset_data: Dict[str, Any],
                    validate: bool = True) -> bool:
        """更新节点数据
        
        Args:
            guid: 资源GUID
            asset_data: 新的资源数据
            validate: 是否进行验证
            
        Returns:
            bool: 是否更新成功
        """
        # 保存旧数据
        old_data = None
        if self.graph.has_asset_node(guid):
            old_data = {'asset_data': self.graph.get_node_data(guid)}
        
        operation = UpdateOperation(
            operation_id=self._generate_operation_id(),
            operation_type=UpdateOperationType.UPDATE_NODE,
            target_id=guid,
            data={'asset_data': asset_data},
            old_data=old_data
        )
        
        return self._execute_single_operation(operation, validate)
    
    def add_edge(self,
                 source_guid: str,
                 target_guid: str,
                 dependency_data: Optional[Dict[str, Any]] = None,
                 validate: bool = True) -> bool:
        """添加边
        
        Args:
            source_guid: 源节点GUID
            target_guid: 目标节点GUID
            dependency_data: 依赖关系数据
            validate: 是否进行验证
            
        Returns:
            bool: 是否添加成功
        """
        edge_id = f"{source_guid}->{target_guid}"
        operation = UpdateOperation(
            operation_id=self._generate_operation_id(),
            operation_type=UpdateOperationType.ADD_EDGE,
            target_id=edge_id,
            data={
                'source_guid': source_guid,
                'target_guid': target_guid,
                'dependency_data': dependency_data or {}
            }
        )
        
        return self._execute_single_operation(operation, validate)
    
    def remove_edge(self, 
                   source_guid: str, 
                   target_guid: str,
                   validate: bool = True) -> bool:
        """删除边
        
        Args:
            source_guid: 源节点GUID
            target_guid: 目标节点GUID
            validate: 是否进行验证
            
        Returns:
            bool: 是否删除成功
        """
        edge_id = f"{source_guid}->{target_guid}"
        
        # 保存旧数据
        old_data = None
        if self.graph.has_edge(source_guid, target_guid):
            old_data = {
                'source_guid': source_guid,
                'target_guid': target_guid,
                'dependency_data': self.graph.get_edge_data(source_guid, target_guid)
            }
        
        operation = UpdateOperation(
            operation_id=self._generate_operation_id(),
            operation_type=UpdateOperationType.REMOVE_EDGE,
            target_id=edge_id,
            data={
                'source_guid': source_guid,
                'target_guid': target_guid
            },
            old_data=old_data
        )
        
        return self._execute_single_operation(operation, validate)
    
    def update_edge(self,
                   source_guid: str,
                   target_guid: str,
                   dependency_data: Dict[str, Any],
                   validate: bool = True) -> bool:
        """更新边数据
        
        Args:
            source_guid: 源节点GUID
            target_guid: 目标节点GUID
            dependency_data: 新的依赖关系数据
            validate: 是否进行验证
            
        Returns:
            bool: 是否更新成功
        """
        edge_id = f"{source_guid}->{target_guid}"
        
        # 保存旧数据
        old_data = None
        if self.graph.has_edge(source_guid, target_guid):
            old_data = {
                'source_guid': source_guid,
                'target_guid': target_guid,
                'dependency_data': self.graph.get_edge_data(source_guid, target_guid)
            }
        
        operation = UpdateOperation(
            operation_id=self._generate_operation_id(),
            operation_type=UpdateOperationType.UPDATE_EDGE,
            target_id=edge_id,
            data={
                'source_guid': source_guid,
                'target_guid': target_guid,
                'dependency_data': dependency_data
            },
            old_data=old_data
        )
        
        return self._execute_single_operation(operation, validate)
    
    @contextmanager
    def batch_update(self, transaction_id: Optional[str] = None):
        """批量更新上下文管理器
        
        Args:
            transaction_id: 事务ID，如果不指定则自动生成
            
        Usage:
            with update_manager.batch_update() as transaction:
                transaction.add_node(guid1, data1)
                transaction.add_edge(guid1, guid2, edge_data)
        """
        if transaction_id is None:
            transaction_id = self._generate_transaction_id()
        
        transaction = BatchUpdateTransaction(transaction_id=transaction_id)
        
        with self._lock:
            if self._current_transaction is not None:
                raise RuntimeError("嵌套事务不被支持")
            
            self._current_transaction = transaction
            
        try:
            yield self
            # 提交事务
            self._commit_transaction(transaction)
        except Exception as e:
            # 回滚事务
            self._rollback_transaction(transaction, str(e))
            raise
        finally:
            with self._lock:
                self._current_transaction = None
    
    def _execute_single_operation(self, 
                                operation: UpdateOperation, 
                                validate: bool = True) -> bool:
        """执行单个操作
        
        Args:
            operation: 更新操作
            validate: 是否进行验证
            
        Returns:
            bool: 是否执行成功
        """
        with self._lock:
            # 如果在事务中，添加到事务而不立即执行
            if self._current_transaction is not None:
                self._current_transaction.operations.append(operation)
                return True
            
            # 立即执行
            return self._apply_operation(operation, validate)
    
    def _apply_operation(self, 
                        operation: UpdateOperation, 
                        validate: bool = True) -> bool:
        """应用单个操作
        
        Args:
            operation: 更新操作
            validate: 是否进行验证
            
        Returns:
            bool: 是否应用成功
        """
        try:
            # 验证操作
            if validate:
                conflicts = self._detect_conflicts([operation])
                if conflicts:
                    operation.status = UpdateStatus.FAILED
                    operation.error_message = f"检测到冲突: {[c.description for c in conflicts]}"
                    self.logger.warning(f"操作 {operation.operation_id} 失败: {operation.error_message}")
                    self.stats['conflicts_detected'] += len(conflicts)
                    self.stats['failed_operations'] += 1
                    self.stats['total_operations'] += 1
                    # 即使失败也记录到历史
                    self.update_history.append(operation)
                    return False
            
            # 应用操作
            success = self._execute_operation(operation)
            
            if success:
                operation.status = UpdateStatus.APPLIED
                self.stats['successful_operations'] += 1
                
                # 触发缓存失效
                self._invalidate_caches(operation)
                
                # 记录到历史
                self.update_history.append(operation)
                
                self.logger.debug(f"操作 {operation.operation_id} 成功应用")
            else:
                operation.status = UpdateStatus.FAILED
                operation.error_message = "操作执行失败"
                self.stats['failed_operations'] += 1
                self.logger.warning(f"操作 {operation.operation_id} 执行失败")
            
            self.stats['total_operations'] += 1
            return success
            
        except Exception as e:
            operation.status = UpdateStatus.FAILED
            operation.error_message = str(e)
            self.stats['failed_operations'] += 1
            self.stats['total_operations'] += 1
            self.logger.error(f"操作 {operation.operation_id} 执行异常: {e}")
            return False
    
    def _execute_operation(self, operation: UpdateOperation) -> bool:
        """执行具体的操作
        
        Args:
            operation: 更新操作
            
        Returns:
            bool: 是否执行成功
        """
        try:
            if operation.operation_type == UpdateOperationType.ADD_NODE:
                return self.graph.add_asset_node(
                    operation.target_id,
                    operation.data.get('asset_data')
                )
            
            elif operation.operation_type == UpdateOperationType.REMOVE_NODE:
                return self.graph.remove_asset_node(operation.target_id)
            
            elif operation.operation_type == UpdateOperationType.UPDATE_NODE:
                # 更新节点数据
                if self.graph.has_asset_node(operation.target_id):
                    node_data = self.graph.get_node_data(operation.target_id) or {}
                    node_data.update(operation.data.get('asset_data', {}))
                    # NetworkX图直接更新节点属性
                    self.graph.graph.nodes[operation.target_id].update(node_data)
                    return True
                return False
            
            elif operation.operation_type == UpdateOperationType.ADD_EDGE:
                return self.graph.add_dependency_edge(
                    operation.data['source_guid'],
                    operation.data['target_guid'],
                    operation.data.get('dependency_data')
                )
            
            elif operation.operation_type == UpdateOperationType.REMOVE_EDGE:
                return self.graph.remove_dependency_edge(
                    operation.data['source_guid'],
                    operation.data['target_guid']
                )
            
            elif operation.operation_type == UpdateOperationType.UPDATE_EDGE:
                # 更新边数据
                source = operation.data['source_guid']
                target = operation.data['target_guid']
                if self.graph.has_edge(source, target):
                    edge_data = self.graph.get_edge_data(source, target) or {}
                    edge_data.update(operation.data.get('dependency_data', {}))
                    # NetworkX图直接更新边属性
                    self.graph.graph[source][target].update(edge_data)
                    return True
                return False
            
            else:
                self.logger.error(f"未知的操作类型: {operation.operation_type}")
                return False
                
        except Exception as e:
            self.logger.error(f"执行操作时发生异常: {e}")
            return False
    
    def _commit_transaction(self, transaction: BatchUpdateTransaction):
        """提交事务
        
        Args:
            transaction: 批量更新事务
        """
        self.logger.info(f"开始提交事务 {transaction.transaction_id}，包含 {len(transaction.operations)} 个操作")
        
        try:
            # 检测冲突
            conflicts = self._detect_conflicts(transaction.operations)
            if conflicts:
                error_msg = f"事务包含冲突: {[c.description for c in conflicts]}"
                raise RuntimeError(error_msg)
            
            # 应用所有操作
            for operation in transaction.operations:
                success = self._apply_operation(operation, validate=False)  # 已经验证过了
                if success:
                    transaction.applied_operations.append(operation.operation_id)
                else:
                    # 如果任何操作失败，回滚已应用的操作
                    self._rollback_applied_operations(transaction.applied_operations)
                    raise RuntimeError(f"操作 {operation.operation_id} 失败: {operation.error_message}")
            
            transaction.status = UpdateStatus.APPLIED
            transaction.end_time = datetime.utcnow()
            
            self.transaction_history.append(transaction)
            self.stats['transactions'] += 1
            
            self.logger.info(f"事务 {transaction.transaction_id} 成功提交，耗时 {transaction.duration:.3f} 秒")
            
        except Exception as e:
            transaction.status = UpdateStatus.FAILED
            transaction.end_time = datetime.utcnow()
            self.logger.error(f"事务 {transaction.transaction_id} 提交失败: {e}")
            raise
    
    def _rollback_transaction(self, 
                            transaction: BatchUpdateTransaction, 
                            error_message: str):
        """回滚事务
        
        Args:
            transaction: 批量更新事务
            error_message: 错误信息
        """
        self.logger.warning(f"开始回滚事务 {transaction.transaction_id}: {error_message}")
        
        try:
            self._rollback_applied_operations(transaction.applied_operations)
            transaction.status = UpdateStatus.ROLLED_BACK
            transaction.end_time = datetime.utcnow()
            
            self.transaction_history.append(transaction)
            
            self.logger.info(f"事务 {transaction.transaction_id} 已回滚")
            
        except Exception as e:
            self.logger.error(f"事务回滚失败: {e}")
    
    def _rollback_applied_operations(self, operation_ids: List[str]):
        """回滚已应用的操作
        
        Args:
            operation_ids: 需要回滚的操作ID列表
        """
        # 按照相反的顺序回滚操作
        for operation_id in reversed(operation_ids):
            operation = self._find_operation_by_id(operation_id)
            if operation and operation.status == UpdateStatus.APPLIED:
                try:
                    self._rollback_single_operation(operation)
                    operation.status = UpdateStatus.ROLLED_BACK
                except Exception as e:
                    self.logger.error(f"回滚操作 {operation_id} 失败: {e}")
    
    def _rollback_single_operation(self, operation: UpdateOperation):
        """回滚单个操作
        
        Args:
            operation: 需要回滚的操作
        """
        if operation.operation_type == UpdateOperationType.ADD_NODE:
            # 删除添加的节点
            self.graph.remove_asset_node(operation.target_id)
        
        elif operation.operation_type == UpdateOperationType.REMOVE_NODE:
            # 恢复删除的节点
            if operation.old_data:
                self.graph.add_asset_node(
                    operation.target_id,
                    operation.old_data.get('asset_data')
                )
                # 恢复边
                for edge in operation.old_data.get('edges', []):
                    self.graph.add_dependency_edge(
                        edge['source'],
                        edge['target'],
                        edge.get('data')
                    )
        
        elif operation.operation_type == UpdateOperationType.UPDATE_NODE:
            # 恢复旧的节点数据
            if operation.old_data and self.graph.has_asset_node(operation.target_id):
                self.graph.graph.nodes[operation.target_id].clear()
                self.graph.graph.nodes[operation.target_id].update(
                    operation.old_data.get('asset_data', {})
                )
        
        elif operation.operation_type == UpdateOperationType.ADD_EDGE:
            # 删除添加的边
            source = operation.data['source_guid']
            target = operation.data['target_guid']
            self.graph.remove_dependency_edge(source, target)
        
        elif operation.operation_type == UpdateOperationType.REMOVE_EDGE:
            # 恢复删除的边
            if operation.old_data:
                self.graph.add_dependency_edge(
                    operation.old_data['source_guid'],
                    operation.old_data['target_guid'],
                    operation.old_data.get('dependency_data')
                )
        
        elif operation.operation_type == UpdateOperationType.UPDATE_EDGE:
            # 恢复旧的边数据
            if operation.old_data:
                source = operation.old_data['source_guid']
                target = operation.old_data['target_guid']
                if self.graph.has_edge(source, target):
                    self.graph.graph[source][target].clear()
                    self.graph.graph[source][target].update(
                        operation.old_data.get('dependency_data', {})
                    )
    
    def _detect_conflicts(self, operations: List[UpdateOperation]) -> List[UpdateConflict]:
        """检测操作冲突
        
        Args:
            operations: 操作列表
            
        Returns:
            List[UpdateConflict]: 检测到的冲突列表
        """
        conflicts = []
        
        for detector in self.conflict_detectors:
            try:
                detected_conflicts = detector(operations)
                conflicts.extend(detected_conflicts)
            except Exception as e:
                self.logger.error(f"冲突检测器执行失败: {e}")
        
        return conflicts
    
    def _detect_node_existence_conflicts(self, 
                                       operations: List[UpdateOperation]) -> List[UpdateConflict]:
        """检测节点存在性冲突"""
        conflicts = []
        
        for operation in operations:
            if operation.operation_type == UpdateOperationType.ADD_NODE:
                if self.graph.has_asset_node(operation.target_id):
                    conflicts.append(UpdateConflict(
                        conflict_type=ConflictType.NODE_ALREADY_EXISTS,
                        operation_id=operation.operation_id,
                        target_id=operation.target_id,
                        description=f"节点 {operation.target_id} 已存在",
                        suggested_resolution="使用update_node()更新现有节点"
                    ))
            
            elif operation.operation_type in [UpdateOperationType.REMOVE_NODE, UpdateOperationType.UPDATE_NODE]:
                if not self.graph.has_asset_node(operation.target_id):
                    conflicts.append(UpdateConflict(
                        conflict_type=ConflictType.NODE_NOT_EXISTS,
                        operation_id=operation.operation_id,
                        target_id=operation.target_id,
                        description=f"节点 {operation.target_id} 不存在"
                    ))
        
        return conflicts
    
    def _detect_edge_existence_conflicts(self, 
                                       operations: List[UpdateOperation]) -> List[UpdateConflict]:
        """检测边存在性冲突"""
        conflicts = []
        
        for operation in operations:
            if operation.operation_type == UpdateOperationType.ADD_EDGE:
                source = operation.data['source_guid']
                target = operation.data['target_guid']
                if self.graph.has_edge(source, target):
                    conflicts.append(UpdateConflict(
                        conflict_type=ConflictType.EDGE_ALREADY_EXISTS,
                        operation_id=operation.operation_id,
                        target_id=operation.target_id,
                        description=f"边 {source}->{target} 已存在",
                        suggested_resolution="使用update_edge()更新现有边"
                    ))
            
            elif operation.operation_type in [UpdateOperationType.REMOVE_EDGE, UpdateOperationType.UPDATE_EDGE]:
                source = operation.data['source_guid']
                target = operation.data['target_guid']
                if not self.graph.has_edge(source, target):
                    conflicts.append(UpdateConflict(
                        conflict_type=ConflictType.EDGE_NOT_EXISTS,
                        operation_id=operation.operation_id,
                        target_id=operation.target_id,
                        description=f"边 {source}->{target} 不存在"
                    ))
        
        return conflicts
    
    def _detect_circular_dependency_conflicts(self, 
                                            operations: List[UpdateOperation]) -> List[UpdateConflict]:
        """检测循环依赖冲突"""
        conflicts = []
        
        # 创建图的副本用于模拟
        temp_graph = copy.deepcopy(self.graph)
        
        # 模拟应用操作
        for operation in operations:
            if operation.operation_type == UpdateOperationType.ADD_EDGE:
                source = operation.data['source_guid']
                target = operation.data['target_guid']
                
                # 添加边到临时图
                temp_graph.add_dependency_edge(source, target, operation.data.get('dependency_data'))
                
                # 检查是否产生循环依赖
                try:
                    cycles = temp_graph.find_circular_dependencies()
                    # 检查新边是否在循环中
                    for cycle in cycles:
                        if len(cycle) > 1 and source in cycle and target in cycle:
                            conflicts.append(UpdateConflict(
                                conflict_type=ConflictType.CIRCULAR_DEPENDENCY,
                                operation_id=operation.operation_id,
                                target_id=operation.target_id,
                                description=f"添加边 {source}->{target} 会产生循环依赖: {' -> '.join(cycle)}",
                                suggested_resolution="重新设计依赖关系避免循环"
                            ))
                            break
                except Exception as e:
                    self.logger.warning(f"循环依赖检测失败: {e}")
        
        return conflicts
    
    def _detect_data_consistency_conflicts(self, 
                                         operations: List[UpdateOperation]) -> List[UpdateConflict]:
        """检测数据一致性冲突"""
        conflicts = []
        
        # 检查同一个目标的多个操作
        target_operations = defaultdict(list)
        for operation in operations:
            target_operations[operation.target_id].append(operation)
        
        for target_id, ops in target_operations.items():
            if len(ops) > 1:
                # 检查是否有冲突的操作类型
                operation_types = [op.operation_type for op in ops]
                
                if (UpdateOperationType.ADD_NODE in operation_types and 
                    UpdateOperationType.REMOVE_NODE in operation_types):
                    conflicts.append(UpdateConflict(
                        conflict_type=ConflictType.DATA_INCONSISTENCY,
                        operation_id=ops[0].operation_id,
                        target_id=target_id,
                        description=f"对节点 {target_id} 同时有添加和删除操作"
                    ))
                
                if (UpdateOperationType.ADD_EDGE in operation_types and 
                    UpdateOperationType.REMOVE_EDGE in operation_types):
                    conflicts.append(UpdateConflict(
                        conflict_type=ConflictType.DATA_INCONSISTENCY,
                        operation_id=ops[0].operation_id,
                        target_id=target_id,
                        description=f"对边 {target_id} 同时有添加和删除操作"
                    ))
        
        return conflicts
    
    def _invalidate_caches(self, operation: UpdateOperation):
        """使缓存失效
        
        Args:
            operation: 更新操作
        """
        try:
            # 调用注册的缓存失效回调
            for callback in self.cache_invalidation_callbacks:
                callback(operation)
            
            # 清除图的统计缓存
            if hasattr(self.graph, '_stats_cache'):
                self.graph._stats_cache.clear()
            if hasattr(self.graph, '_cache_timestamp'):
                self.graph._cache_timestamp = None
            
            # 清除查询引擎的缓存
            if hasattr(self.graph, 'query_engine') and hasattr(self.graph.query_engine, 'clear_cache'):
                self.graph.query_engine.clear_cache()
            
            self.stats['cache_invalidations'] += 1
            
        except Exception as e:
            self.logger.warning(f"缓存失效处理失败: {e}")
    
    def _get_node_edges(self, guid: str) -> List[Dict[str, Any]]:
        """获取节点的所有边信息
        
        Args:
            guid: 节点GUID
            
        Returns:
            List[Dict[str, Any]]: 边信息列表
        """
        edges = []
        
        if not self.graph.has_asset_node(guid):
            return edges
        
        # 出边
        for target in self.graph.get_successors(guid):
            edge_data = self.graph.get_edge_data(guid, target)
            edges.append({
                'source': guid,
                'target': target,
                'data': edge_data
            })
        
        # 入边
        for source in self.graph.get_predecessors(guid):
            edge_data = self.graph.get_edge_data(source, guid)
            edges.append({
                'source': source,
                'target': guid,
                'data': edge_data
            })
        
        return edges
    
    def _generate_operation_id(self) -> str:
        """生成操作ID"""
        import uuid
        return f"op_{uuid.uuid4().hex[:8]}"
    
    def _generate_transaction_id(self) -> str:
        """生成事务ID"""
        import uuid
        return f"tx_{uuid.uuid4().hex[:8]}"
    
    def _find_operation_by_id(self, operation_id: str) -> Optional[UpdateOperation]:
        """根据ID查找操作
        
        Args:
            operation_id: 操作ID
            
        Returns:
            Optional[UpdateOperation]: 找到的操作，如果不存在返回None
        """
        for operation in self.update_history:
            if operation.operation_id == operation_id:
                return operation
        return None
    
    def register_cache_invalidation_callback(self, callback: Callable[[UpdateOperation], None]):
        """注册缓存失效回调
        
        Args:
            callback: 缓存失效回调函数
        """
        self.cache_invalidation_callbacks.append(callback)
    
    def register_conflict_detector(self, detector: Callable[[List[UpdateOperation]], List[UpdateConflict]]):
        """注册冲突检测器
        
        Args:
            detector: 冲突检测函数
        """
        self.conflict_detectors.append(detector)
    
    def get_update_history(self, 
                          limit: Optional[int] = None,
                          operation_type: Optional[UpdateOperationType] = None) -> List[UpdateOperation]:
        """获取更新历史
        
        Args:
            limit: 限制返回的数量
            operation_type: 过滤的操作类型
            
        Returns:
            List[UpdateOperation]: 更新历史列表
        """
        history = self.update_history
        
        if operation_type:
            history = [op for op in history if op.operation_type == operation_type]
        
        if limit:
            history = history[-limit:]
        
        return history
    
    def get_transaction_history(self, limit: Optional[int] = None) -> List[BatchUpdateTransaction]:
        """获取事务历史
        
        Args:
            limit: 限制返回的数量
            
        Returns:
            List[BatchUpdateTransaction]: 事务历史列表
        """
        if limit:
            return self.transaction_history[-limit:]
        return self.transaction_history
    
    def get_stats(self) -> Dict[str, Any]:
        """获取更新统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            **self.stats,
            'update_history_size': len(self.update_history),
            'transaction_history_size': len(self.transaction_history),
            'success_rate': (self.stats['successful_operations'] / max(1, self.stats['total_operations'])) * 100
        }
    
    def clear_history(self, keep_recent: int = 100):
        """清理历史记录
        
        Args:
            keep_recent: 保留最近的记录数量
        """
        with self._lock:
            if len(self.update_history) > keep_recent:
                self.update_history = self.update_history[-keep_recent:]
            
            if len(self.transaction_history) > keep_recent:
                self.transaction_history = self.transaction_history[-keep_recent:]
        
        self.logger.info(f"历史记录已清理，保留最近 {keep_recent} 条记录")


class FileChangeGraphUpdater:
    """基于文件变更的图更新器
    
    集成文件变更检测，自动触发图更新
    """
    
    def __init__(self, 
                 update_manager: GraphUpdateManager,
                 file_change_detector: Optional[FileChangeDetector] = None):
        """初始化文件变更图更新器
        
        Args:
            update_manager: 图更新管理器
            file_change_detector: 文件变更检测器
        """
        self.update_manager = update_manager
        self.file_change_detector = file_change_detector
        self.logger = logging.getLogger(__name__)
        
        # 文件变更处理器映射
        self.change_handlers = {
            'new': self._handle_new_files,
            'modified': self._handle_modified_files,
            'deleted': self._handle_deleted_files
        }
        
        # 统计信息
        self.processing_stats = {
            'processed_changes': 0,
            'successful_updates': 0,
            'failed_updates': 0
        }
    
    def process_file_changes(self, changes: Dict[str, List[Path]]) -> Dict[str, Any]:
        """处理文件变更
        
        Args:
            changes: 文件变更信息，包含'new'、'modified'、'deleted'键
            
        Returns:
            Dict[str, Any]: 处理结果统计
        """
        self.logger.info(f"开始处理文件变更: 新增 {len(changes.get('new', []))} 个，"
                        f"修改 {len(changes.get('modified', []))} 个，"
                        f"删除 {len(changes.get('deleted', []))} 个文件")
        
        results = {
            'new': {'processed': 0, 'successful': 0, 'failed': 0},
            'modified': {'processed': 0, 'successful': 0, 'failed': 0},
            'deleted': {'processed': 0, 'successful': 0, 'failed': 0}
        }
        
        # 使用批量更新处理所有变更
        try:
            with self.update_manager.batch_update() as batch:
                for change_type, file_paths in changes.items():
                    if change_type in self.change_handlers:
                        handler_results = self.change_handlers[change_type](file_paths, batch)
                        results[change_type] = handler_results
                        self.processing_stats['processed_changes'] += handler_results['processed']
                        self.processing_stats['successful_updates'] += handler_results['successful']
                        self.processing_stats['failed_updates'] += handler_results['failed']
            
            self.logger.info("文件变更处理完成")
            
        except Exception as e:
            self.logger.error(f"文件变更处理失败: {e}")
            results['error'] = str(e)
        
        return results
    
    def _handle_new_files(self, 
                         file_paths: List[Path], 
                         batch_manager) -> Dict[str, int]:
        """处理新增文件"""
        processed = 0
        successful = 0
        failed = 0
        
        for file_path in file_paths:
            try:
                # 解析文件获取GUID和依赖信息
                asset_info = self._parse_asset_file(file_path)
                if asset_info:
                    # 添加节点
                    if batch_manager.add_node(asset_info['guid'], asset_info['data']):
                        successful += 1
                        
                        # 添加依赖边
                        for dependency in asset_info.get('dependencies', []):
                            batch_manager.add_edge(
                                asset_info['guid'],
                                dependency['target_guid'],
                                dependency['data']
                            )
                    else:
                        failed += 1
                
                processed += 1
                
            except Exception as e:
                self.logger.error(f"处理新文件 {file_path} 失败: {e}")
                failed += 1
                processed += 1
        
        return {'processed': processed, 'successful': successful, 'failed': failed}
    
    def _handle_modified_files(self, 
                              file_paths: List[Path], 
                              batch_manager) -> Dict[str, int]:
        """处理修改文件"""
        processed = 0
        successful = 0
        failed = 0
        
        for file_path in file_paths:
            try:
                # 解析文件获取新的信息
                asset_info = self._parse_asset_file(file_path)
                if asset_info:
                    guid = asset_info['guid']
                    
                    # 更新节点数据
                    if batch_manager.update_node(guid, asset_info['data']):
                        successful += 1
                        
                        # 更新依赖关系（简化处理：移除旧的，添加新的）
                        # 在实际实现中，可能需要更精细的差异计算
                        
                        # 移除现有的依赖边
                        if self.update_manager.graph.has_asset_node(guid):
                            for target in list(self.update_manager.graph.get_successors(guid)):
                                batch_manager.remove_edge(guid, target)
                        
                        # 添加新的依赖边
                        for dependency in asset_info.get('dependencies', []):
                            batch_manager.add_edge(
                                guid,
                                dependency['target_guid'],
                                dependency['data']
                            )
                    else:
                        failed += 1
                
                processed += 1
                
            except Exception as e:
                self.logger.error(f"处理修改文件 {file_path} 失败: {e}")
                failed += 1
                processed += 1
        
        return {'processed': processed, 'successful': successful, 'failed': failed}
    
    def _handle_deleted_files(self, 
                             file_paths: List[Path], 
                             batch_manager) -> Dict[str, int]:
        """处理删除文件"""
        processed = 0
        successful = 0
        failed = 0
        
        for file_path in file_paths:
            try:
                # 根据文件路径找到对应的GUID
                guid = self._find_guid_by_path(file_path)
                if guid and self.update_manager.graph.has_asset_node(guid):
                    if batch_manager.remove_node(guid):
                        successful += 1
                    else:
                        failed += 1
                
                processed += 1
                
            except Exception as e:
                self.logger.error(f"处理删除文件 {file_path} 失败: {e}")
                failed += 1
                processed += 1
        
        return {'processed': processed, 'successful': successful, 'failed': failed}
    
    def _parse_asset_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """解析资源文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            Optional[Dict[str, Any]]: 解析后的资源信息
        """
        try:
            # 这里应该调用相应的解析器
            # 这是一个简化的实现
            
            if file_path.suffix == '.meta':
                # 解析.meta文件
                from ..parsers.meta_parser import MetaParser
                parser = MetaParser()
                meta_data = parser.parse_file(file_path)
                
                if meta_data and meta_data.guid:
                    return {
                        'guid': meta_data.guid,
                        'data': {
                            'asset_type': meta_data.asset_type,
                            'file_path': str(file_path),
                            'file_id': meta_data.file_id,
                            'import_settings': meta_data.import_settings
                        },
                        'dependencies': []  # Meta文件通常不包含依赖信息
                    }
            
            elif file_path.suffix in ['.prefab', '.unity']:
                # 解析prefab或scene文件
                # 这里需要实现具体的解析逻辑
                pass
            
            return None
            
        except Exception as e:
            self.logger.error(f"解析文件 {file_path} 失败: {e}")
            return None
    
    def _find_guid_by_path(self, file_path: Path) -> Optional[str]:
        """根据文件路径查找GUID
        
        Args:
            file_path: 文件路径
            
        Returns:
            Optional[str]: 找到的GUID
        """
        try:
            # 查找图中所有节点，匹配文件路径
            for node_id in self.update_manager.graph.graph.nodes():
                node_data = self.update_manager.graph.get_node_data(node_id)
                if node_data and node_data.get('file_path') == str(file_path):
                    return node_id
            
            return None
            
        except Exception as e:
            self.logger.error(f"查找GUID失败 {file_path}: {e}")
            return None
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """获取处理统计信息
        
        Returns:
            Dict[str, Any]: 处理统计信息
        """
        return self.processing_stats.copy()
