"""Unity Resource Reference Scanner - Database Tests

数据库模块的单元测试，包括模型测试、DAO测试和数据库管理器测试。
"""

import pytest
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.asset import Asset, AssetType, Base
from src.models.dependency import Dependency, DependencyType, DependencyStrength, DependencyGraph
from src.models.scan_result import ScanResult, ScanStatus, ScanType, ScanStatistics
from src.core.database import (
    DatabaseManager, AssetDAO, DependencyDAO, ScanResultDAO,
    get_database_manager, initialize_database, get_session
)
from src.core.config import DatabaseConfig, DatabaseType


class TestAssetModel:
    """Asset模型测试"""

    def test_asset_creation(self):
        """测试Asset创建"""
        asset = Asset(
            guid="test-guid-123",
            file_path="/path/to/asset.prefab",
            asset_type=AssetType.PREFAB.value
        )
        
        assert asset.guid == "test-guid-123"
        assert asset.file_path == "/path/to/asset.prefab"
        assert asset.asset_type == AssetType.PREFAB.value
        assert asset.is_active is True
        assert asset.is_analyzed is False

    def test_asset_properties(self):
        """测试Asset属性"""
        asset = Asset(
            guid="test-guid-123",
            file_path="/path/to/texture.png",
            asset_type=AssetType.TEXTURE.value
        )
        
        assert asset.name == "texture.png"
        assert asset.extension == ".png"
        assert asset.directory == "/path/to"
        assert str(asset.path) == "/path/to/texture.png"

    def test_detect_asset_type(self):
        """测试资源类型检测"""
        assert Asset.detect_asset_type("test.prefab") == AssetType.PREFAB
        assert Asset.detect_asset_type("test.scene") == AssetType.SCENE
        assert Asset.detect_asset_type("test.cs") == AssetType.SCRIPT
        assert Asset.detect_asset_type("test.png") == AssetType.TEXTURE
        assert Asset.detect_asset_type("test.mat") == AssetType.MATERIAL
        assert Asset.detect_asset_type("test.unknown") == AssetType.UNKNOWN

    def test_asset_metadata_operations(self):
        """测试Asset元数据操作"""
        asset = Asset(
            guid="test-guid-123",
            file_path="/path/to/asset.prefab",
            asset_type=AssetType.PREFAB.value
        )
        
        # 测试更新元数据
        asset.update_metadata({"width": 1024, "height": 768})
        assert asset.asset_metadata["width"] == 1024
        assert asset.asset_metadata["height"] == 768
        
        # 测试更新导入设置
        asset.update_import_settings({"compression": "high"})
        assert asset.import_settings["compression"] == "high"
        
        # 测试标记为已分析
        asset.mark_as_analyzed()
        assert asset.is_analyzed is True
        
        # 测试标记为非活跃
        asset.mark_as_inactive()
        assert asset.is_active is False

    def test_asset_to_dict(self):
        """测试Asset转换为字典"""
        asset = Asset(
            guid="test-guid-123",
            file_path="/path/to/asset.prefab",
            asset_type=AssetType.PREFAB.value,
            file_size=2048
        )
        
        asset_dict = asset.to_dict()
        assert asset_dict["guid"] == "test-guid-123"
        assert asset_dict["file_path"] == "/path/to/asset.prefab"
        assert asset_dict["asset_type"] == AssetType.PREFAB.value
        assert asset_dict["file_size"] == 2048
        assert asset_dict["is_active"] is True


class TestDependencyModel:
    """Dependency模型测试"""

    def test_dependency_creation(self):
        """测试Dependency创建"""
        dependency = Dependency.create_dependency(
            source_guid="source-guid",
            target_guid="target-guid",
            dependency_type=DependencyType.MATERIAL,
            dependency_strength=DependencyStrength.CRITICAL
        )
        
        assert dependency.source_guid == "source-guid"
        assert dependency.target_guid == "target-guid"
        assert dependency.dependency_type == DependencyType.MATERIAL.value
        assert dependency.dependency_strength == DependencyStrength.CRITICAL.value
        assert dependency.is_active is True
        assert dependency.is_verified is False

    def test_dependency_properties(self):
        """测试Dependency属性"""
        # 测试循环依赖检测
        circular_dep = Dependency(
            source_guid="same-guid",
            target_guid="same-guid",
            dependency_type=DependencyType.DIRECT.value
        )
        assert circular_dep.is_circular is True
        
        # 测试非循环依赖
        normal_dep = Dependency(
            source_guid="source-guid",
            target_guid="target-guid",
            dependency_type=DependencyType.DIRECT.value
        )
        assert normal_dep.is_circular is False

    def test_dependency_path(self):
        """测试依赖路径描述"""
        dependency = Dependency(
            source_guid="source-guid",
            target_guid="target-guid",
            dependency_type=DependencyType.COMPONENT.value,
            context_path="GameObject/Transform",
            component_type="MeshRenderer",
            property_name="material"
        )
        
        path = dependency.dependency_path
        assert "GameObject/Transform" in path
        assert "Component:MeshRenderer" in path
        assert "Property:material" in path

    def test_dependency_strength_priority(self):
        """测试依赖强度优先级"""
        critical_dep = Dependency(
            source_guid="source",
            target_guid="target",
            dependency_type=DependencyType.DIRECT.value,
            dependency_strength=DependencyStrength.CRITICAL.value
        )
        
        weak_dep = Dependency(
            source_guid="source",
            target_guid="target", 
            dependency_type=DependencyType.DIRECT.value,
            dependency_strength=DependencyStrength.WEAK.value
        )
        
        assert critical_dep.get_strength_priority() > weak_dep.get_strength_priority()

    def test_dependency_graph_circular_detection(self):
        """测试依赖图循环检测"""
        # 创建循环依赖：A -> B -> C -> A
        dependencies = [
            Dependency(source_guid="A", target_guid="B", dependency_type=DependencyType.DIRECT.value),
            Dependency(source_guid="B", target_guid="C", dependency_type=DependencyType.DIRECT.value),
            Dependency(source_guid="C", target_guid="A", dependency_type=DependencyType.DIRECT.value),
        ]
        
        cycles = DependencyGraph.find_circular_dependencies(dependencies)
        assert len(cycles) > 0
        # 检查是否找到了包含A、B、C的循环

    def test_dependency_depth_calculation(self):
        """测试依赖深度计算"""
        # 创建依赖链：D -> C -> B -> A
        dependencies = [
            Dependency(source_guid="D", target_guid="C", dependency_type=DependencyType.DIRECT.value),
            Dependency(source_guid="C", target_guid="B", dependency_type=DependencyType.DIRECT.value),
            Dependency(source_guid="B", target_guid="A", dependency_type=DependencyType.DIRECT.value),
        ]
        
        depths = DependencyGraph.get_dependency_depth(dependencies, "A")
        assert depths["A"] == 0
        assert depths.get("B", -1) >= 1
        assert depths.get("C", -1) >= 2
        assert depths.get("D", -1) >= 3


class TestScanResultModel:
    """ScanResult模型测试"""

    def test_scan_result_creation(self):
        """测试ScanResult创建"""
        scan_result = ScanResult.create_scan_result(
            scan_id="scan-123",
            scan_type=ScanType.FULL,
            project_path="/path/to/project",
            scan_paths=["Assets/", "Packages/"],
            exclude_paths=["Library/", "Temp/"]
        )
        
        assert scan_result.scan_id == "scan-123"
        assert scan_result.scan_type == ScanType.FULL.value
        assert scan_result.project_path == "/path/to/project"
        assert scan_result.scan_status == ScanStatus.PENDING.value

    def test_scan_lifecycle(self):
        """测试扫描生命周期"""
        scan_result = ScanResult(
            scan_id="scan-123",
            scan_type=ScanType.FULL.value,
            project_path="/path/to/project"
        )
        
        # 开始扫描
        scan_result.start_scan()
        assert scan_result.scan_status == ScanStatus.RUNNING.value
        
        # 完成扫描
        scan_result.complete_scan(
            total_files_scanned=100,
            total_assets_found=50,
            total_dependencies_found=200
        )
        assert scan_result.scan_status == ScanStatus.COMPLETED.value
        assert scan_result.total_files_scanned == 100
        assert scan_result.is_completed is True
        assert scan_result.is_successful is True

    def test_scan_failure(self):
        """测试扫描失败处理"""
        scan_result = ScanResult(
            scan_id="scan-123",
            scan_type=ScanType.FULL.value,
            project_path="/path/to/project"
        )
        
        scan_result.start_scan()
        scan_result.fail_scan("Database connection failed")
        
        assert scan_result.scan_status == ScanStatus.FAILED.value
        assert scan_result.error_count == 1
        assert scan_result.is_completed is True
        assert scan_result.is_successful is False

    def test_scan_statistics(self):
        """测试扫描统计功能"""
        # 创建测试扫描结果，直接设置duration
        scan_results = []
        for i in range(5):
            scan_result = ScanResult(
                scan_id=f"scan-{i}",
                scan_type=ScanType.FULL.value,
                project_path="/path/to/project",
                scan_status=ScanStatus.COMPLETED.value,
                duration_seconds=10.0 + i  # 10-14秒
            )
            scan_results.append(scan_result)
        
        # 添加一个失败的扫描（没有duration）
        failed_scan = ScanResult(
            scan_id="scan-failed",
            scan_type=ScanType.FULL.value,
            project_path="/path/to/project",
            scan_status=ScanStatus.FAILED.value,
            duration_seconds=None
        )
        scan_results.append(failed_scan)
        
        # 测试统计计算
        avg_time = ScanStatistics.calculate_average_scan_time(scan_results)
        # 应该只计算有duration的5个扫描: (10+11+12+13+14)/5 = 12.0
        expected_avg = 12.0
        assert avg_time == expected_avg, f"Expected {expected_avg}, got {avg_time}"
        
        success_rate = ScanStatistics.get_scan_success_rate(scan_results)
        assert success_rate == 5/6  # 5成功，1失败


class TestDatabaseManager:
    """DatabaseManager测试"""

    def test_database_manager_initialization(self):
        """测试数据库管理器初始化"""
        # 使用临时文件作为SQLite数据库
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
            db_path = tmp_file.name
        
        try:
            config = DatabaseConfig(
                type=DatabaseType.SQLITE,
                path=db_path
            )
            
            db_manager = DatabaseManager(config)
            assert db_manager.config.type == DatabaseType.SQLITE
            assert db_manager.config.path == db_path
            
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_database_initialization(self):
        """测试数据库初始化"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
            db_path = tmp_file.name
        
        try:
            config = DatabaseConfig(
                type=DatabaseType.SQLITE,
                path=db_path
            )
            
            db_manager = DatabaseManager(config)
            db_manager.initialize_database()
            
            # 检查表是否创建
            health_info = db_manager.check_database_health()
            assert health_info['status'] == 'healthy'
            assert health_info['tables_exist'] is True
            
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_database_backup(self):
        """测试数据库备份"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
            db_path = tmp_file.name
        
        try:
            config = DatabaseConfig(
                type=DatabaseType.SQLITE,
                path=db_path
            )
            
            db_manager = DatabaseManager(config)
            db_manager.initialize_database()
            
            # 创建备份
            backup_path = db_manager.backup_database()
            assert backup_path is not None
            assert os.path.exists(backup_path)
            
            # 清理备份文件
            if backup_path and os.path.exists(backup_path):
                os.unlink(backup_path)
                
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


class TestAssetDAO:
    """AssetDAO测试"""

    @pytest.fixture
    def test_database(self):
        """测试数据库fixture"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
            db_path = tmp_file.name
        
        config = DatabaseConfig(
            type=DatabaseType.SQLITE,
            path=db_path
        )
        
        db_manager = DatabaseManager(config)
        db_manager.initialize_database()
        
        yield db_manager
        
        # 清理
        if os.path.exists(db_path):
            os.unlink(db_path)

    def test_asset_crud_operations(self, test_database):
        """测试Asset CRUD操作"""
        asset_dao = AssetDAO(test_database)
        
        with test_database.get_session() as session:
            # 创建资源
            asset = asset_dao.create(
                session,
                guid="test-guid-123",
                file_path="/path/to/test.prefab",
                asset_type=AssetType.PREFAB.value,
                file_size=1024
            )
            
            assert asset.guid == "test-guid-123"
            assert asset.file_path == "/path/to/test.prefab"
            
            # 根据GUID查询
            found_asset = asset_dao.get_by_guid(session, "test-guid-123")
            assert found_asset is not None
            assert found_asset.guid == "test-guid-123"
            
            # 根据路径查询
            path_asset = asset_dao.get_by_path(session, "/path/to/test.prefab")
            assert path_asset is not None
            assert path_asset.guid == "test-guid-123"
            
            # 更新资源
            updated_asset = asset_dao.update(session, "test-guid-123", file_size=2048)
            assert updated_asset.file_size == 2048
            
            # 删除资源
            deleted = asset_dao.delete(session, "test-guid-123")
            assert deleted is True
            
            # 验证删除
            deleted_asset = asset_dao.get_by_guid(session, "test-guid-123")
            assert deleted_asset is None

    def test_asset_type_queries(self, test_database):
        """测试按类型查询资源"""
        asset_dao = AssetDAO(test_database)
        
        with test_database.get_session() as session:
            # 创建不同类型的资源
            asset_dao.create(
                session,
                guid="prefab-1",
                file_path="/path/to/prefab1.prefab",
                asset_type=AssetType.PREFAB.value
            )
            
            asset_dao.create(
                session,
                guid="prefab-2",
                file_path="/path/to/prefab2.prefab",
                asset_type=AssetType.PREFAB.value
            )
            
            asset_dao.create(
                session,
                guid="texture-1",
                file_path="/path/to/texture1.png",
                asset_type=AssetType.TEXTURE.value
            )
            
            # 查询Prefab类型资源
            prefabs = asset_dao.get_by_type(session, AssetType.PREFAB)
            assert len(prefabs) == 2
            
            # 查询Texture类型资源
            textures = asset_dao.get_by_type(session, AssetType.TEXTURE)
            assert len(textures) == 1

    def test_update_or_create(self, test_database):
        """测试更新或创建资源"""
        asset_dao = AssetDAO(test_database)
        
        with test_database.get_session() as session:
            # 第一次调用应该创建新资源
            asset1 = asset_dao.update_or_create(
                session,
                guid="test-guid",
                file_path="/path/to/test.prefab",
                asset_type=AssetType.PREFAB.value
            )
            assert asset1.guid == "test-guid"
            
            # 第二次调用应该更新现有资源
            asset2 = asset_dao.update_or_create(
                session,
                guid="test-guid",
                file_path="/path/to/updated.prefab",
                asset_type=AssetType.PREFAB.value
            )
            assert asset2.guid == "test-guid"
            assert asset2.file_path == "/path/to/updated.prefab"
            
            # 验证只有一个资源
            all_assets = asset_dao.get_all(session)
            assert len(all_assets) == 1


class TestDependencyDAO:
    """DependencyDAO测试"""

    @pytest.fixture
    def test_database_with_assets(self):
        """带有测试资源的数据库fixture"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
            db_path = tmp_file.name
        
        config = DatabaseConfig(
            type=DatabaseType.SQLITE,
            path=db_path
        )
        
        db_manager = DatabaseManager(config)
        db_manager.initialize_database()
        
        # 创建测试资源
        asset_dao = AssetDAO(db_manager)
        with db_manager.get_session() as session:
            asset_dao.create(
                session,
                guid="source-asset",
                file_path="/path/to/source.prefab",
                asset_type=AssetType.PREFAB.value
            )
            asset_dao.create(
                session,
                guid="target-asset",
                file_path="/path/to/target.mat",
                asset_type=AssetType.MATERIAL.value
            )
        
        yield db_manager
        
        # 清理
        if os.path.exists(db_path):
            os.unlink(db_path)

    def test_dependency_crud_operations(self, test_database_with_assets):
        """测试Dependency CRUD操作"""
        dependency_dao = DependencyDAO(test_database_with_assets)
        
        with test_database_with_assets.get_session() as session:
            # 创建依赖关系
            dependency = dependency_dao.create_or_update_dependency(
                session,
                source_guid="source-asset",
                target_guid="target-asset",
                dependency_type=DependencyType.MATERIAL
            )
            
            assert dependency.source_guid == "source-asset"
            assert dependency.target_guid == "target-asset"
            assert dependency.dependency_type == DependencyType.MATERIAL.value
            
            # 查询源资源的依赖
            source_deps = dependency_dao.get_by_source_guid(session, "source-asset")
            assert len(source_deps) == 1
            
            # 查询目标资源的被依赖
            target_deps = dependency_dao.get_by_target_guid(session, "target-asset")
            assert len(target_deps) == 1
            
            # 按类型查询
            material_deps = dependency_dao.get_by_type(session, DependencyType.MATERIAL)
            assert len(material_deps) == 1

    def test_create_or_update_dependency(self, test_database_with_assets):
        """测试创建或更新依赖关系"""
        dependency_dao = DependencyDAO(test_database_with_assets)
        
        with test_database_with_assets.get_session() as session:
            # 第一次调用应该创建新依赖
            dep1 = dependency_dao.create_or_update_dependency(
                session,
                source_guid="source-asset",
                target_guid="target-asset",
                dependency_type=DependencyType.MATERIAL,
                context_path="Material Slot 0"
            )
            
            # 第二次调用相同参数应该更新现有依赖
            dep2 = dependency_dao.create_or_update_dependency(
                session,
                source_guid="source-asset",
                target_guid="target-asset",
                dependency_type=DependencyType.MATERIAL,
                context_path="Material Slot 0",
                dependency_strength=DependencyStrength.CRITICAL.value
            )
            
            # 应该是同一个依赖关系
            assert dep1.id == dep2.id
            assert dep2.dependency_strength == DependencyStrength.CRITICAL.value
            
            # 验证数据库中只有一条记录
            all_deps = dependency_dao.get_all(session)
            assert len(all_deps) == 1


class TestScanResultDAO:
    """ScanResultDAO测试"""

    @pytest.fixture
    def test_database(self):
        """测试数据库fixture"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
            db_path = tmp_file.name
        
        config = DatabaseConfig(
            type=DatabaseType.SQLITE,
            path=db_path
        )
        
        db_manager = DatabaseManager(config)
        db_manager.initialize_database()
        
        yield db_manager
        
        # 清理
        if os.path.exists(db_path):
            os.unlink(db_path)

    def test_scan_result_operations(self, test_database):
        """测试ScanResult操作"""
        scan_dao = ScanResultDAO(test_database)
        
        with test_database.get_session() as session:
            # 创建扫描结果
            scan_result = scan_dao.create(
                session,
                scan_id="test-scan-123",
                scan_type=ScanType.FULL.value,
                project_path="/path/to/project"
            )
            
            assert scan_result.scan_id == "test-scan-123"
            
            # 根据scan_id查询
            found_scan = scan_dao.get_by_scan_id(session, "test-scan-123")
            assert found_scan is not None
            assert found_scan.scan_id == "test-scan-123"

    def test_recent_scans_query(self, test_database):
        """测试最近扫描查询"""
        scan_dao = ScanResultDAO(test_database)
        
        with test_database.get_session() as session:
            # 创建多个扫描结果
            for i in range(5):
                scan_dao.create(
                    session,
                    scan_id=f"scan-{i}",
                    scan_type=ScanType.FULL.value,
                    project_path="/path/to/project"
                )
            
            # 查询最近3次扫描
            recent_scans = scan_dao.get_recent_scans(session, limit=3)
            assert len(recent_scans) == 3

    def test_cleanup_old_scans(self, test_database):
        """测试清理旧扫描记录"""
        scan_dao = ScanResultDAO(test_database)
        
        with test_database.get_session() as session:
            # 创建旧的扫描记录
            old_scan = scan_dao.create(
                session,
                scan_id="old-scan",
                scan_type=ScanType.FULL.value,
                project_path="/path/to/project"
            )
            old_scan.started_at = datetime.utcnow() - timedelta(days=40)
            old_scan.scan_status = ScanStatus.COMPLETED.value
            
            # 创建新的扫描记录
            new_scan = scan_dao.create(
                session,
                scan_id="new-scan",
                scan_type=ScanType.FULL.value,
                project_path="/path/to/project"
            )
            new_scan.scan_status = ScanStatus.COMPLETED.value
            
            session.commit()
            
            # 清理30天前的记录
            deleted_count = scan_dao.cleanup_old_scans(session, keep_days=30)
            assert deleted_count == 1
            
            # 验证只剩下新记录
            remaining_scans = scan_dao.get_all(session)
            assert len(remaining_scans) == 1
            assert remaining_scans[0].scan_id == "new-scan"


@pytest.mark.integration
class TestDatabaseIntegration:
    """数据库集成测试"""

    def test_full_database_workflow(self):
        """测试完整的数据库工作流"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
            db_path = tmp_file.name
        
        try:
            # 配置数据库
            config = DatabaseConfig(
                type=DatabaseType.SQLITE,
                path=db_path
            )
            
            with patch('src.core.config.get_config') as mock_config:
                mock_config.return_value.database = config
                
                # 初始化数据库
                initialize_database()
                
                # 获取DAO实例
                from src.core.database import get_asset_dao, get_dependency_dao, get_scan_result_dao
                
                asset_dao = get_asset_dao()
                dependency_dao = get_dependency_dao()
                scan_dao = get_scan_result_dao()
                
                # 执行完整工作流
                with get_session() as session:
                    # 1. 创建资源
                    prefab = asset_dao.create(
                        session,
                        guid="prefab-guid",
                        file_path="/Assets/Player.prefab",
                        asset_type=AssetType.PREFAB.value
                    )
                    
                    material = asset_dao.create(
                        session,
                        guid="material-guid",
                        file_path="/Assets/Materials/Player.mat",
                        asset_type=AssetType.MATERIAL.value
                    )
                    
                    # 2. 创建依赖关系
                    dependency = dependency_dao.create_or_update_dependency(
                        session,
                        source_guid="prefab-guid",
                        target_guid="material-guid",
                        dependency_type=DependencyType.MATERIAL,
                        context_path="MeshRenderer.material"
                    )
                    
                    # 3. 创建扫描结果
                    scan_result = scan_dao.create(
                        session,
                        scan_id="integration-test-scan",
                        scan_type=ScanType.FULL.value,
                        project_path="/path/to/project",
                        total_assets_found=2,
                        total_dependencies_found=1
                    )
                    
                    # 验证数据完整性
                    assert asset_dao.count(session) == 2
                    assert dependency_dao.count(session) == 1
                    assert scan_dao.count(session) == 1
                    
                    # 验证关联关系
                    prefab_deps = dependency_dao.get_by_source_guid(session, "prefab-guid")
                    assert len(prefab_deps) == 1
                    assert prefab_deps[0].target_guid == "material-guid"
                    
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
