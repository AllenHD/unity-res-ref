"""文件扫描器测试

测试FileScanner和IncrementalFileScanner的功能。
"""

import pytest
import tempfile
from pathlib import Path
from typing import Dict, List
from unittest.mock import Mock, patch

from src.core.config import ScanConfig
from src.core.scanner import FileScanner, IncrementalFileScanner, ScanResult, ProgressReporter


class TestFileScanner:
    """FileScanner测试类"""
    
    @pytest.fixture
    def test_config(self):
        """测试配置"""
        return ScanConfig(
            paths=["Assets", "Packages"],
            file_extensions=[".prefab", ".scene", ".asset"],
            exclude_paths=["Library/**", "Temp/**", "*.log"],
            max_file_size_mb=50,
            ignore_hidden_files=True
        )
    
    @pytest.fixture
    def temp_unity_project(self):
        """创建临时Unity项目结构"""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # 创建Unity项目结构
            (project_path / "Assets").mkdir()
            (project_path / "Packages").mkdir()
            (project_path / "Library").mkdir()
            (project_path / "Temp").mkdir()
            (project_path / "ProjectSettings").mkdir()
            
            # 创建ProjectSettings/ProjectVersion.txt（Unity项目标识）
            project_version = project_path / "ProjectSettings" / "ProjectVersion.txt"
            project_version.write_text("m_EditorVersion: 2022.3.0f1")
            
            # 创建测试文件
            (project_path / "Assets" / "test.prefab").write_text("test prefab content")
            (project_path / "Assets" / "test.scene").write_text("test scene content")
            (project_path / "Assets" / "test.asset").write_text("test asset content")
            (project_path / "Assets" / "test.txt").write_text("text file content")
            
            # 创建子目录
            subdir = project_path / "Assets" / "Scripts"
            subdir.mkdir()
            (subdir / "script.prefab").write_text("script prefab content")
            
            # 创建隐藏文件
            (project_path / "Assets" / ".hidden.prefab").write_text("hidden prefab")
            
            # 创建需要排除的文件
            (project_path / "Library" / "excluded.prefab").write_text("excluded prefab")
            (project_path / "Temp" / "temp.prefab").write_text("temp prefab")
            
            yield project_path
    
    def test_scanner_initialization(self, test_config):
        """测试扫描器初始化"""
        scanner = FileScanner(test_config)
        
        assert scanner.config == test_config
        assert ".prefab" in scanner.file_extensions
        assert ".scene" in scanner.file_extensions
        assert ".asset" in scanner.file_extensions
        assert scanner.max_file_size == 50 * 1024 * 1024
    
    def test_should_scan_file(self, test_config, temp_unity_project):
        """测试文件过滤逻辑"""
        scanner = FileScanner(test_config)
        
        # 应该扫描的文件
        assert scanner._should_scan_file(temp_unity_project / "Assets" / "test.prefab")
        assert scanner._should_scan_file(temp_unity_project / "Assets" / "test.scene")
        assert scanner._should_scan_file(temp_unity_project / "Assets" / "test.asset")
        
        # 不应该扫描的文件
        assert not scanner._should_scan_file(temp_unity_project / "Assets" / "test.txt")
        
        # 隐藏文件
        if test_config.ignore_hidden_files:
            assert not scanner._should_scan_file(temp_unity_project / "Assets" / ".hidden.prefab")
    
    def test_should_exclude_path(self, test_config, temp_unity_project):
        """测试路径排除逻辑"""
        scanner = FileScanner(test_config)
        
        # 应该排除的路径
        assert scanner._should_exclude_path(
            temp_unity_project / "Library" / "excluded.prefab",
            temp_unity_project
        )
        assert scanner._should_exclude_path(
            temp_unity_project / "Temp" / "temp.prefab", 
            temp_unity_project
        )
        
        # 不应该排除的路径
        assert not scanner._should_exclude_path(
            temp_unity_project / "Assets" / "test.prefab",
            temp_unity_project
        )
    
    def test_scan_project(self, test_config, temp_unity_project):
        """测试Unity项目扫描"""
        scanner = FileScanner(test_config)
        result = scanner.scan_project(temp_unity_project)
        
        assert isinstance(result, ScanResult)
        # 使用resolve()来解决路径差异问题
        assert result.project_path.resolve() == temp_unity_project.resolve()
        assert result.scanned_files > 0
        assert result.end_time is not None
        assert result.duration is not None
        assert result.success_rate > 0
        
        # 检查扫描到的文件
        file_names = [f.name for f in result.file_paths]
        assert "test.prefab" in file_names
        assert "test.scene" in file_names
        assert "test.asset" in file_names
        assert "script.prefab" in file_names
        
        # 确保排除了不应该扫描的文件
        assert "test.txt" not in file_names
        assert ".hidden.prefab" not in file_names
        assert "excluded.prefab" not in file_names
        assert "temp.prefab" not in file_names
    
    def test_scan_project_invalid_path(self, test_config):
        """测试扫描无效项目路径"""
        scanner = FileScanner(test_config)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建非Unity项目目录
            invalid_path = Path(temp_dir)
            
            with pytest.raises(ValueError, match="不是有效的Unity项目"):
                scanner.scan_project(invalid_path)
    
    def test_progress_reporter(self, test_config, temp_unity_project):
        """测试进度报告功能"""
        scanner = FileScanner(test_config)
        
        # 记录进度报告
        progress_reports = []
        
        def progress_callback(progress_info: Dict):
            progress_reports.append(progress_info)
        
        scanner.set_progress_callback(progress_callback)
        result = scanner.scan_project(temp_unity_project)
        
        # 检查进度报告
        assert len(progress_reports) > 0
        
        # 检查第一个报告（开始）
        first_report = progress_reports[0]
        assert first_report['processed_files'] == 0
        assert first_report['total_files'] > 0
        assert first_report['progress_percent'] == 0.0
        assert not first_report['finished']
        
        # 检查最后一个报告（完成）
        last_report = progress_reports[-1]
        assert last_report['finished']
        assert last_report['progress_percent'] == 100.0
    
    def test_scan_paths(self, test_config, temp_unity_project):
        """测试指定路径扫描"""
        scanner = FileScanner(test_config)
        
        # 扫描特定路径
        scan_paths = [temp_unity_project / "Assets"]
        result = scanner.scan_paths(scan_paths)
        
        assert isinstance(result, ScanResult)
        assert result.scanned_files > 0
        
        # 检查所有文件都在Assets目录下，使用resolve()解决路径问题
        assets_path = (temp_unity_project / "Assets").resolve()
        for file_path in result.file_paths:
            assert str(file_path.resolve()).startswith(str(assets_path))
    
    def test_scanner_stats(self, test_config):
        """测试扫描器统计信息"""
        scanner = FileScanner(test_config)
        stats = scanner.get_scanner_stats()
        
        assert 'file_extensions' in stats
        assert 'max_file_size_mb' in stats
        assert 'exclude_patterns' in stats
        assert 'ignore_hidden_files' in stats
        assert 'scan_paths' in stats
        
        assert set(stats['file_extensions']) == {'.prefab', '.scene', '.asset'}
        assert stats['max_file_size_mb'] == 50


class TestProgressReporter:
    """ProgressReporter测试类"""
    
    def test_progress_reporter_basic(self):
        """测试基本进度报告功能"""
        reports = []
        
        def callback(progress_info):
            reports.append(progress_info)
        
        reporter = ProgressReporter(callback)
        
        # 开始报告
        reporter.start(total_files=100)
        assert len(reports) == 1
        assert reports[0]['total_files'] == 100
        assert reports[0]['processed_files'] == 0
        
        # 更新进度
        reporter.update(processed_files=50)
        assert len(reports) >= 1
        
        # 完成报告
        reporter.finish()
        final_report = reports[-1]
        assert final_report['finished']
    
    def test_progress_reporter_no_callback(self):
        """测试无回调函数的进度报告器"""
        reporter = ProgressReporter(None)
        
        # 不应该抛出异常
        reporter.start(100)
        reporter.update(50)
        reporter.finish()


class TestIncrementalFileScanner:
    """IncrementalFileScanner测试类"""
    
    @pytest.fixture
    def test_config(self):
        """测试配置"""
        return ScanConfig(
            paths=["Assets"],
            file_extensions=[".prefab", ".scene"],
            exclude_paths=["Library/**"],
            max_file_size_mb=50,
            ignore_hidden_files=True
        )
    
    @pytest.fixture
    def temp_unity_project(self):
        """创建临时Unity项目"""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # 创建Unity项目结构
            (project_path / "Assets").mkdir()
            (project_path / "ProjectSettings").mkdir()
            
            # 创建ProjectSettings/ProjectVersion.txt
            project_version = project_path / "ProjectSettings" / "ProjectVersion.txt"
            project_version.write_text("m_EditorVersion: 2022.3.0f1")
            
            # 创建测试文件
            (project_path / "Assets" / "test1.prefab").write_text("test1 content")
            (project_path / "Assets" / "test2.scene").write_text("test2 content")
            
            yield project_path
    
    def test_incremental_scanner_initialization(self, test_config):
        """测试增量扫描器初始化"""
        with tempfile.NamedTemporaryFile(delete=False) as cache_file:
            cache_path = Path(cache_file.name)
        
        try:
            scanner = IncrementalFileScanner(
                test_config, 
                cache_file=cache_path,
                enable_checksum=True
            )
            
            assert scanner.config == test_config
            assert scanner.change_detector is not None
            assert scanner.file_scanner is not None
        finally:
            cache_path.unlink(missing_ok=True)
    
    def test_full_scan(self, test_config, temp_unity_project):
        """测试完全扫描"""
        with tempfile.NamedTemporaryFile(delete=False) as cache_file:
            cache_path = Path(cache_file.name)
        
        try:
            scanner = IncrementalFileScanner(test_config, cache_file=cache_path)
            result = scanner.full_scan(temp_unity_project)
            
            assert isinstance(result, ScanResult)
            assert result.scanned_files > 0
            
            # 检查缓存统计
            cache_stats = scanner.get_cache_stats()
            assert cache_stats['total_files'] > 0
        finally:
            cache_path.unlink(missing_ok=True)
    
    @patch('src.utils.file_watcher.IncrementalScanner')
    def test_incremental_scan(self, mock_incremental_scanner, test_config, temp_unity_project):
        """测试增量扫描"""
        # 模拟增量扫描器
        mock_scanner_instance = Mock()
        mock_scanner_instance.start_scan_session.return_value = "test_session"
        mock_scanner_instance.scan_for_changes.return_value = {
            'modified': [Path("test1.prefab")],
            'new': [Path("test2.scene")], 
            'deleted': []
        }
        mock_incremental_scanner.return_value = mock_scanner_instance
        
        with tempfile.NamedTemporaryFile(delete=False) as cache_file:
            cache_path = Path(cache_file.name)
        
        try:
            scanner = IncrementalFileScanner(test_config, cache_file=cache_path)
            changes = scanner.incremental_scan(temp_unity_project)
            
            assert 'modified' in changes
            assert 'new' in changes
            assert 'deleted' in changes
            
            assert len(changes['modified']) == 1
            assert len(changes['new']) == 1
            assert len(changes['deleted']) == 0
        finally:
            cache_path.unlink(missing_ok=True)


class TestScanResult:
    """ScanResult测试类"""
    
    def test_scan_result_properties(self):
        """测试ScanResult属性计算"""
        from datetime import datetime, timezone
        
        start_time = datetime.now(timezone.utc)
        end_time = datetime.now(timezone.utc)
        
        result = ScanResult(
            session_id="test_session",
            project_path=Path("/test/project"),
            total_files=100,
            scanned_files=90,
            error_files=5,
            start_time=start_time,
            end_time=end_time
        )
        
        # 测试持续时间
        assert result.duration is not None
        assert result.duration >= 0
        
        # 测试成功率
        assert result.success_rate == 85.0  # (90-5)/100*100
        
        # 测试字典转换
        result_dict = result.to_dict()
        assert result_dict['session_id'] == "test_session"
        assert result_dict['total_files'] == 100
        assert result_dict['success_rate'] == 85.0
    
    def test_scan_result_no_times(self):
        """测试没有时间信息的ScanResult"""
        result = ScanResult(
            session_id="test_session",
            project_path=Path("/test/project")
        )
        
        assert result.duration is None
        assert result.success_rate == 0.0
