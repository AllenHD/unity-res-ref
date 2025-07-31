"""文件扫描器集成测试

测试FileScanner在实际Unity项目结构中的表现。
"""

import pytest
import tempfile
from pathlib import Path
from typing import List

from src.core.scanner import FileScanner, create_file_scanner
from src.core.config import ScanConfig


class TestFileScannerIntegration:
    """文件扫描器集成测试"""
    
    @pytest.fixture
    def sample_unity_project(self):
        """创建样本Unity项目结构"""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # 创建Unity项目结构
            (project_path / "Assets").mkdir()
            (project_path / "Assets" / "Scripts").mkdir()
            (project_path / "Assets" / "Prefabs").mkdir()
            (project_path / "Assets" / "Scenes").mkdir()
            (project_path / "Assets" / "Materials").mkdir()
            (project_path / "Packages").mkdir()
            (project_path / "Library").mkdir()
            (project_path / "Temp").mkdir()
            (project_path / "ProjectSettings").mkdir()
            
            # 创建ProjectVersion.txt（Unity项目标识）
            project_version = project_path / "ProjectSettings" / "ProjectVersion.txt"
            project_version.write_text("m_EditorVersion: 2022.3.0f1")
            
            # 创建各种类型的Unity资源文件
            (project_path / "Assets" / "Scripts" / "PlayerController.cs").write_text(
                "using UnityEngine;\npublic class PlayerController : MonoBehaviour {}"
            )
            (project_path / "Assets" / "Prefabs" / "Player.prefab").write_text(
                "%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n--- !u!1 &1\nGameObject:\n  name: Player"
            )
            (project_path / "Assets" / "Scenes" / "MainScene.unity").write_text(
                "%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n--- !u!29 &1\nOcclusionCullingSettings:"
            )
            (project_path / "Assets" / "Materials" / "PlayerMaterial.mat").write_text(
                "%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n--- !u!21 &2100000\nMaterial:"
            )
            
            # 创建应该被排除的文件
            (project_path / "Library" / "metadata").mkdir()
            (project_path / "Library" / "metadata" / "cache.prefab").write_text("cache data")
            (project_path / "Temp" / "temp.scene").write_text("temp scene")
            
            # 创建隐藏文件
            (project_path / "Assets" / ".DS_Store").write_text("hidden file")
            
            # 创建日志文件
            (project_path / "Assets" / "build.log").write_text("build log content")
            
            yield project_path
    
    def test_full_project_scan(self, sample_unity_project):
        """测试完整项目扫描"""
        config = ScanConfig(
            paths=["Assets", "Packages"],
            file_extensions=[".prefab", ".unity", ".mat", ".asset"],
            exclude_paths=["Library/**", "Temp/**", "*.log"],
            max_file_size_mb=50,
            ignore_hidden_files=True
        )
        
        scanner = FileScanner(config)
        result = scanner.scan_project(sample_unity_project)
        
        # 验证扫描结果
        assert result.scanned_files > 0
        assert result.error_files == 0
        assert result.success_rate == 100.0
        assert result.duration is not None and result.duration > 0
        
        # 检查扫描到的文件
        file_names = [f.name for f in result.file_paths]
        assert "Player.prefab" in file_names
        assert "MainScene.unity" in file_names
        assert "PlayerMaterial.mat" in file_names
        
        # 确保排除了不应该扫描的文件
        assert "PlayerController.cs" not in file_names  # 不在扫描扩展名中
        assert "cache.prefab" not in file_names  # 在Library目录中
        assert "temp.scene" not in file_names  # 在Temp目录中
        assert ".DS_Store" not in file_names  # 隐藏文件
        assert "build.log" not in file_names  # 日志文件
        
        print(f"扫描结果: {result.to_dict()}")
    
    def test_progress_reporting(self, sample_unity_project):
        """测试进度报告功能"""
        config = ScanConfig(
            paths=["Assets"],
            file_extensions=[".prefab", ".unity", ".mat"],
            exclude_paths=["Library/**", "Temp/**"],
            max_file_size_mb=50,
            ignore_hidden_files=True
        )
        
        scanner = FileScanner(config)
        
        # 收集进度报告
        progress_reports = []
        def progress_callback(progress_info):
            progress_reports.append(progress_info)
        
        scanner.set_progress_callback(progress_callback)
        result = scanner.scan_project(sample_unity_project)
        
        # 验证进度报告
        assert len(progress_reports) > 0
        
        # 检查第一个报告
        first_report = progress_reports[0]
        assert first_report['processed_files'] == 0
        assert first_report['total_files'] > 0
        assert first_report['progress_percent'] == 0.0
        
        # 检查最后一个报告
        last_report = progress_reports[-1]
        assert last_report['finished'] is True
        assert last_report['progress_percent'] == 100.0
        assert last_report['processed_files'] == last_report['total_files']
        
        print(f"进度报告数量: {len(progress_reports)}")
        print(f"最终进度: {last_report}")
    
    def test_create_scanner_convenience_function(self):
        """测试便捷创建函数"""
        # 使用默认配置创建扫描器
        scanner = create_file_scanner()
        assert isinstance(scanner, FileScanner)
        assert scanner.config is not None
        
        # 使用自定义配置创建扫描器
        custom_config = ScanConfig(
            paths=["CustomAssets"],
            file_extensions=[".custom"],
            exclude_paths=["CustomExclude/**"],
            max_file_size_mb=100,
            ignore_hidden_files=False
        )
        
        custom_scanner = create_file_scanner(custom_config)
        assert custom_scanner.config == custom_config
        assert ".custom" in custom_scanner.file_extensions
    
    def test_scanner_stats(self, sample_unity_project):
        """测试扫描器统计信息"""
        config = ScanConfig(
            paths=["Assets", "Packages"],
            file_extensions=[".prefab", ".unity", ".mat"],
            exclude_paths=["Library/**", "Temp/**", "*.log"],
            max_file_size_mb=25,
            ignore_hidden_files=True
        )
        
        scanner = FileScanner(config)
        stats = scanner.get_scanner_stats()
        
        # 验证统计信息
        assert set(stats['file_extensions']) == {'.prefab', '.unity', '.mat'}
        assert stats['max_file_size_mb'] == 25
        assert stats['exclude_patterns'] == ["Library/**", "Temp/**", "*.log"]
        assert stats['ignore_hidden_files'] is True
        # 路径可能包含斜杠，只检查基本路径
        scan_paths_base = [p.rstrip('/') for p in stats['scan_paths']]
        assert set(scan_paths_base) == {"Assets", "Packages"}
    
    def test_different_path_configurations(self, sample_unity_project):
        """测试不同的路径配置"""
        # 只扫描Assets目录
        assets_only_config = ScanConfig(
            paths=["Assets"],
            file_extensions=[".prefab", ".unity"],
            exclude_paths=[],
            max_file_size_mb=50,
            ignore_hidden_files=True
        )
        
        scanner = FileScanner(assets_only_config)
        result = scanner.scan_project(sample_unity_project)
        
        # 验证只扫描了Assets目录
        for file_path in result.file_paths:
            assert "Assets" in str(file_path)
            assert "Packages" not in str(file_path)
        
        # 扫描多个目录
        multi_path_config = ScanConfig(
            paths=["Assets", "Packages"],
            file_extensions=[".prefab", ".unity"],
            exclude_paths=[],
            max_file_size_mb=50,
            ignore_hidden_files=True
        )
        
        multi_scanner = FileScanner(multi_path_config)
        multi_result = multi_scanner.scan_project(sample_unity_project)
        
        # 多路径扫描应该返回相同或更多的结果
        assert multi_result.scanned_files >= result.scanned_files
