"""测试图增量更新管理器功能"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import networkx as nx
from datetime import datetime
from pathlib import Path

from src.core.graph_update_manager import (
    GraphUpdateManager,
    FileChangeGraphUpdater,
    UpdateOperation,
    UpdateOperationType,
    UpdateStatus,
    BatchUpdateTransaction,
    ConflictType,
    UpdateConflict
)


class TestGraphUpdateManager:
    """图更新管理器测试"""
    
    def setup_method(self):
        """测试设置"""
        # 模拟依赖图
        self.mock_graph = Mock()
        self.mock_graph.graph = nx.DiGraph()
        
        # 添加一些测试节点和边
        self.mock_graph.graph.add_node('node1', asset_type='prefab')
        self.mock_graph.graph.add_node('node2', asset_type='script')
        self.mock_graph.graph.add_edge('node1', 'node2', dependency_type='component')
        
        # 模拟图方法
        self.mock_graph.has_asset_node = Mock(side_effect=lambda guid: guid in self.mock_graph.graph.nodes)
        self.mock_graph.add_asset_node = Mock(return_value=True)
        self.mock_graph.remove_asset_node = Mock(return_value=True)
        self.mock_graph.add_dependency_edge = Mock(return_value=True)
        self.mock_graph.remove_dependency_edge = Mock(return_value=True)
        self.mock_graph.has_edge = Mock(side_effect=lambda s, t: self.mock_graph.graph.has_edge(s, t))
        self.mock_graph.get_node_data = Mock(side_effect=lambda n: self.mock_graph.graph.nodes[n] if n in self.mock_graph.graph.nodes else None)
        self.mock_graph.get_edge_data = Mock(side_effect=lambda s, t: self.mock_graph.graph[s][t] if self.mock_graph.graph.has_edge(s, t) else None)
        self.mock_graph.get_predecessors = Mock(side_effect=lambda n: list(self.mock_graph.graph.predecessors(n)))
        self.mock_graph.get_successors = Mock(side_effect=lambda n: list(self.mock_graph.graph.successors(n)))
        self.mock_graph.find_circular_dependencies = Mock(return_value=[])
        
        self.update_manager = GraphUpdateManager(self.mock_graph)
    
    def test_add_node_success(self):
        """测试成功添加节点"""
        result = self.update_manager.add_node('new_node', {'asset_type': 'texture'})
        
        assert result is True
        assert len(self.update_manager.update_history) == 1
        
        operation = self.update_manager.update_history[0]
        assert operation.operation_type == UpdateOperationType.ADD_NODE
        assert operation.target_id == 'new_node'
        assert operation.status == UpdateStatus.APPLIED
    
    def test_add_existing_node_conflict(self):
        """测试添加已存在节点的冲突"""
        # 清空之前的操作历史和统计
        self.update_manager.update_history.clear()
        self.update_manager.stats['conflicts_detected'] = 0
        self.update_manager.stats['failed_operations'] = 0
        
        # 先确保节点存在
        self.mock_graph.has_asset_node.return_value = True
        
        result = self.update_manager.add_node('node1', {'asset_type': 'material'})
        
        assert result is False
        assert len(self.update_manager.update_history) == 1
        
        operation = self.update_manager.update_history[0]
        assert operation.status == UpdateStatus.FAILED
        assert "检测到冲突" in operation.error_message
    
    def test_remove_node_success(self):
        """测试成功删除节点"""
        result = self.update_manager.remove_node('node1')
        
        assert result is True
        assert len(self.update_manager.update_history) == 1
        
        operation = self.update_manager.update_history[0]
        assert operation.operation_type == UpdateOperationType.REMOVE_NODE
        assert operation.target_id == 'node1'
        assert operation.status == UpdateStatus.APPLIED
    
    def test_remove_nonexistent_node_conflict(self):
        """测试删除不存在节点的冲突"""
        result = self.update_manager.remove_node('nonexistent_node')
        
        assert result is False
        assert len(self.update_manager.update_history) == 1
        
        operation = self.update_manager.update_history[0]
        assert operation.status == UpdateStatus.FAILED
    
    def test_update_node_success(self):
        """测试成功更新节点"""
        result = self.update_manager.update_node('node1', {'asset_type': 'updated_prefab'})
        
        assert result is True
        assert len(self.update_manager.update_history) == 1
        
        operation = self.update_manager.update_history[0]
        assert operation.operation_type == UpdateOperationType.UPDATE_NODE
        assert operation.target_id == 'node1'
        assert operation.status == UpdateStatus.APPLIED
    
    def test_add_edge_success(self):
        """测试成功添加边"""
        result = self.update_manager.add_edge('node2', 'node1', {'dependency_type': 'reference'})
        
        assert result is True
        assert len(self.update_manager.update_history) == 1
        
        operation = self.update_manager.update_history[0]
        assert operation.operation_type == UpdateOperationType.ADD_EDGE
        assert operation.target_id == 'node2->node1'
        assert operation.status == UpdateStatus.APPLIED
    
    def test_add_existing_edge_conflict(self):
        """测试添加已存在边的冲突"""
        result = self.update_manager.add_edge('node1', 'node2', {'dependency_type': 'duplicate'})
        
        assert result is False
        assert len(self.update_manager.update_history) == 1
        
        operation = self.update_manager.update_history[0]
        assert operation.status == UpdateStatus.FAILED
    
    def test_remove_edge_success(self):
        """测试成功删除边"""
        result = self.update_manager.remove_edge('node1', 'node2')
        
        assert result is True
        assert len(self.update_manager.update_history) == 1
        
        operation = self.update_manager.update_history[0]
        assert operation.operation_type == UpdateOperationType.REMOVE_EDGE
        assert operation.target_id == 'node1->node2'
        assert operation.status == UpdateStatus.APPLIED
    
    def test_batch_update_success(self):
        """测试成功的批量更新"""
        with self.update_manager.batch_update() as batch:
            batch.add_node('batch_node1', {'asset_type': 'material'})
            batch.add_node('batch_node2', {'asset_type': 'shader'})
            batch.add_edge('batch_node1', 'batch_node2', {'dependency_type': 'material'})
        
        assert len(self.update_manager.transaction_history) == 1
        
        transaction = self.update_manager.transaction_history[0]
        assert transaction.status == UpdateStatus.APPLIED
        assert len(transaction.operations) == 3
        assert len(transaction.applied_operations) == 3
    
    def test_batch_update_rollback(self):
        """测试批量更新回滚"""
        # 模拟操作失败
        self.mock_graph.add_asset_node.side_effect = [True, False, True]  # 第二个操作失败
        
        with pytest.raises(RuntimeError):
            with self.update_manager.batch_update() as batch:
                batch.add_node('batch_node1', {'asset_type': 'material'})
                batch.add_node('batch_node2', {'asset_type': 'shader'})  # 这个会失败
                batch.add_edge('batch_node1', 'batch_node2', {'dependency_type': 'material'})
        
        assert len(self.update_manager.transaction_history) == 1
        
        transaction = self.update_manager.transaction_history[0]
        assert transaction.status == UpdateStatus.ROLLED_BACK
    
    def test_circular_dependency_detection(self):
        """测试循环依赖检测"""
        # 设置模拟返回循环依赖
        self.mock_graph.find_circular_dependencies.return_value = [['node2', 'node1', 'node2']]
        
        result = self.update_manager.add_edge('node2', 'node1', {'dependency_type': 'circular'})
        
        assert result is False
        
        operation = self.update_manager.update_history[0]
        assert operation.status == UpdateStatus.FAILED
        assert "循环依赖" in operation.error_message
    
    def test_stats_tracking(self):
        """测试统计信息跟踪"""
        # 重置统计
        self.update_manager.stats = {
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'transactions': 0,
            'conflicts_detected': 0,
            'cache_invalidations': 0
        }
        self.update_manager.update_history.clear()
        
        # 执行一些操作
        self.mock_graph.has_asset_node.return_value = False
        self.update_manager.add_node('stat_node1', {'asset_type': 'texture'})
        
        # 设置特定节点的返回值来产生冲突
        def mock_has_node(guid):
            if guid == 'existing_node':
                return True
            return False
        
        self.mock_graph.has_asset_node.side_effect = mock_has_node
        self.update_manager.add_node('existing_node', {'asset_type': 'material'})  # 会失败，因为冲突
        
        self.mock_graph.has_asset_node.return_value = False
        self.mock_graph.has_edge.return_value = False
        self.update_manager.add_edge('stat_node1', 'node1', {'dependency_type': 'reference'})
        
        stats = self.update_manager.get_stats()
        
        assert stats['total_operations'] == 3
        assert stats['successful_operations'] == 2
        assert stats['failed_operations'] == 1
        assert stats['success_rate'] == (2/3) * 100
    
    def test_update_history(self):
        """测试更新历史记录"""
        # 执行一些操作
        self.update_manager.add_node('history_node1', {'asset_type': 'texture'})
        self.update_manager.add_edge('history_node1', 'node1', {'dependency_type': 'reference'})
        self.update_manager.update_node('node1', {'asset_type': 'updated_prefab'})
        
        # 获取所有历史
        all_history = self.update_manager.get_update_history()
        assert len(all_history) == 3
        
        # 获取限制数量的历史
        limited_history = self.update_manager.get_update_history(limit=2)
        assert len(limited_history) == 2
        
        # 按类型过滤历史
        node_operations = self.update_manager.get_update_history(
            operation_type=UpdateOperationType.ADD_NODE
        )
        assert len(node_operations) == 1
        assert node_operations[0].operation_type == UpdateOperationType.ADD_NODE


class TestFileChangeGraphUpdater:
    """文件变更图更新器测试"""
    
    def setup_method(self):
        """测试设置"""
        # 模拟依赖图
        self.mock_graph = Mock()
        self.mock_graph.graph = nx.DiGraph()
        self.mock_graph.has_asset_node = Mock(return_value=False)
        self.mock_graph.add_asset_node = Mock(return_value=True)
        self.mock_graph.remove_asset_node = Mock(return_value=True)
        self.mock_graph.add_dependency_edge = Mock(return_value=True)
        self.mock_graph.remove_dependency_edge = Mock(return_value=True)
        self.mock_graph.has_edge = Mock(return_value=False)
        self.mock_graph.get_node_data = Mock(return_value={})
        self.mock_graph.get_edge_data = Mock(return_value={})
        self.mock_graph.get_predecessors = Mock(return_value=[])
        self.mock_graph.get_successors = Mock(return_value=[])
        self.mock_graph.find_circular_dependencies = Mock(return_value=[])
        
        self.update_manager = GraphUpdateManager(self.mock_graph)
        self.file_updater = FileChangeGraphUpdater(self.update_manager)
    
    @patch('src.parsers.meta_parser.MetaParser')
    def test_process_new_files(self, mock_parser_class):
        """测试处理新文件"""
        # 模拟解析器
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        
        mock_meta_data = Mock()
        mock_meta_data.guid = 'test_guid_123'
        mock_meta_data.asset_type = 'texture'
        mock_meta_data.file_id = 12345
        mock_meta_data.import_settings = {}
        
        mock_parser.parse_file.return_value = mock_meta_data
        
        # 处理新文件
        changes = {
            'new': [Path('/project/Assets/test.png.meta')],
            'modified': [],
            'deleted': []
        }
        
        result = self.file_updater.process_file_changes(changes)
        
        assert 'new' in result
        assert result['new']['processed'] == 1
        assert result['new']['successful'] == 1
        assert result['new']['failed'] == 0
    
    def test_process_deleted_files(self):
        """测试处理删除文件"""
        # 模拟查找GUID
        self.file_updater._find_guid_by_path = Mock(return_value='deleted_guid_123')
        self.mock_graph.has_asset_node.return_value = True
        
        changes = {
            'new': [],
            'modified': [],
            'deleted': [Path('/project/Assets/deleted.png')]
        }
        
        result = self.file_updater.process_file_changes(changes)
        
        assert 'deleted' in result
        assert result['deleted']['processed'] == 1
        assert result['deleted']['successful'] == 1
        assert result['deleted']['failed'] == 0
    
    def test_find_guid_by_path(self):
        """测试根据路径查找GUID"""
        # 设置图中有节点
        test_path = '/project/Assets/test.png'
        self.mock_graph.graph.add_node('test_guid', file_path=test_path)
        self.mock_graph.get_node_data.return_value = {'file_path': test_path}
        
        guid = self.file_updater._find_guid_by_path(Path(test_path))
        
        assert guid == 'test_guid'
    
    def test_processing_stats(self):
        """测试处理统计信息"""
        stats = self.file_updater.get_processing_stats()
        
        assert 'processed_changes' in stats
        assert 'successful_updates' in stats
        assert 'failed_updates' in stats


if __name__ == "__main__":
    # 运行简单的测试
    test_manager = TestGraphUpdateManager()
    test_manager.setup_method()
    
    print("运行图增量更新管理器测试...")
    
    # 基本功能测试
    try:
        test_manager.test_add_node_success()
        print("✓ 添加节点测试通过")
    except Exception as e:
        print(f"✗ 添加节点测试失败: {e}")
    
    try:
        test_manager.test_add_existing_node_conflict()
        print("✓ 节点冲突检测测试通过")
    except AssertionError as e:
        print(f"✗ 节点冲突检测测试失败: {e}")
    except Exception as e:
        print(f"✗ 节点冲突检测测试异常: {e}")
    
    try:
        test_manager.test_batch_update_success()
        print("✓ 批量更新测试通过")
    except Exception as e:
        print(f"✗ 批量更新测试失败: {e}")
    
    try:
        test_manager.test_stats_tracking()
        print("✓ 统计信息跟踪测试通过")
    except AssertionError as e:
        print(f"✗ 统计信息跟踪测试失败: {e}")
    except Exception as e:
        print(f"✗ 统计信息跟踪测试异常: {e}")
    
    # 文件变更更新器测试
    test_file_updater = TestFileChangeGraphUpdater()
    test_file_updater.setup_method()
    
    try:
        test_file_updater.test_find_guid_by_path()
        print("✓ GUID查找测试通过")
    except Exception as e:
        print(f"✗ GUID查找测试失败: {e}")
    
    try:
        test_file_updater.test_processing_stats()
        print("✓ 处理统计信息测试通过")
    except Exception as e:
        print(f"✗ 处理统计信息测试失败: {e}")
    
    print("测试完成!")
