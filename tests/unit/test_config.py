"""Unity Resource Reference Scanner - Configuration System Unit Tests

配置系统的单元测试，验证配置加载、验证、环境变量覆盖等功能。
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from pydantic import ValidationError

from src.core.config import (
    AppConfig,
    ProjectConfig,
    ScanConfig,
    DatabaseConfig,
    PerformanceConfig,
    OutputConfig,
    FeaturesConfig,
    ConfigManager,
    get_config_manager,
    get_config,
    LogLevel,
    DatabaseType,
    ExportFormat,
)


class TestConfigModels:
    """配置模型测试"""

    def test_project_config_defaults(self):
        """测试项目配置默认值"""
        config = ProjectConfig()
        assert config.name == "Unity Project Scanner"
        assert config.unity_project_path == Path(".")
        assert config.unity_version is None

    def test_project_config_validation(self):
        """测试项目配置验证"""
        # 有效的Unity版本
        config = ProjectConfig(unity_version="2021.3.15f1")
        assert config.unity_version == "2021.3.15f1"
        
        config = ProjectConfig(unity_version="2022.1")
        assert config.unity_version == "2022.1"
        
        # 无效的Unity版本应该抛出异常
        with pytest.raises(ValidationError):
            ProjectConfig(unity_version="invalid.version")

    def test_scan_config_defaults(self):
        """测试扫描配置默认值"""
        config = ScanConfig()
        assert "Assets/" in config.paths
        assert "Packages/" in config.paths
        assert ".prefab" in config.file_extensions
        assert config.max_file_size_mb == 50
        assert config.ignore_hidden_files is True

    def test_scan_config_path_validation(self):
        """测试扫描路径验证"""
        # 路径应该以/结尾
        config = ScanConfig(paths=["Assets", "Packages"])
        assert all(path.endswith('/') for path in config.paths)
        
        # 空路径应该被过滤
        config = ScanConfig(paths=["Assets/", "", "  ", "Packages/"])
        assert len(config.paths) == 2

    def test_scan_config_extension_validation(self):
        """测试文件扩展名验证"""
        # 扩展名应该以.开头并转换为小写
        config = ScanConfig(file_extensions=["prefab", ".SCENE", "Asset"])
        expected = [".prefab", ".scene", ".asset"]
        assert config.file_extensions == expected

    def test_database_config_defaults(self):
        """测试数据库配置默认值"""
        config = DatabaseConfig()
        assert config.type == DatabaseType.SQLITE
        assert config.path == "./unity_deps.db"
        assert config.backup_enabled is True
        assert config.backup_interval_hours == 24

    def test_database_config_url_property(self):
        """测试数据库URL属性"""
        config = DatabaseConfig(path="./test.db")
        assert config.url.startswith("sqlite:///")
        assert config.url.endswith("test.db")

    def test_performance_config_validation(self):
        """测试性能配置验证"""
        # 测试最大工作线程数限制 - 现在需要直接调用validator
        with patch('os.cpu_count', return_value=4):
            # 测试正常情况
            config = PerformanceConfig(max_workers=8)
            assert config.max_workers == 8
            
            # 测试超过限制的情况，应该被调整为CPU数量*2
            # 直接测试validator函数
            result = PerformanceConfig.validate_max_workers(100)
            assert result == 8  # 4 * 2

    def test_output_config_color_validation(self):
        """测试输出配置彩色输出验证"""
        # 在非终端环境中应该禁用彩色输出
        with patch('sys.stdout.isatty', return_value=False):
            config = OutputConfig(color_output=True)
            assert config.color_output is False

    def test_app_config_consistency_validation(self):
        """测试应用配置一致性验证"""
        config = AppConfig()
        # 基本验证应该通过
        assert isinstance(config.project, ProjectConfig)
        assert isinstance(config.scan, ScanConfig)
        assert isinstance(config.database, DatabaseConfig)


class TestConfigManager:
    """配置管理器测试"""

    def test_init_with_default_path(self):
        """测试使用默认路径初始化"""
        manager = ConfigManager()
        assert manager.config_path.name == "default.yaml"

    def test_init_with_custom_path(self):
        """测试使用自定义路径初始化"""
        custom_path = Path("/custom/config.yaml")
        manager = ConfigManager(custom_path)
        assert manager.config_path == custom_path

    def test_load_config_success(self):
        """测试成功加载配置"""
        yaml_content = """
project:
  name: "Test Project"
  unity_project_path: "."

scan:
  paths:
    - "Assets/"
  file_extensions:
    - ".prefab"

database:
  type: "sqlite"
  path: "./test.db"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            try:
                manager = ConfigManager(f.name)
                config = manager.load_config()
                
                assert config.project.name == "Test Project"
                assert "Assets/" in config.scan.paths
                assert config.database.path == "./test.db"
            finally:
                os.unlink(f.name)

    def test_load_config_file_not_found(self):
        """测试配置文件不存在的情况"""
        manager = ConfigManager("/nonexistent/config.yaml")
        with pytest.raises(FileNotFoundError):
            manager.load_config()

    def test_load_config_invalid_yaml(self):
        """测试无效YAML格式"""
        invalid_yaml = "invalid: yaml: content: ["
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(invalid_yaml)
            f.flush()
            
            try:
                manager = ConfigManager(f.name)
                with pytest.raises(ValueError):
                    manager.load_config()
            finally:
                os.unlink(f.name)

    def test_env_override(self):
        """测试环境变量覆盖"""
        yaml_content = """
project:
  name: "Test Project"

scan:
  max_file_size_mb: 50

database:
  type: "sqlite"
  path: "./test.db"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            try:
                # 设置环境变量
                with patch.dict(os.environ, {
                    'UNITY_SCANNER_SCAN_MAX_FILE_SIZE_MB': '100',
                    'UNITY_SCANNER_PROJECT_NAME': 'Overridden Project'
                }):
                    manager = ConfigManager(f.name)
                    config = manager.load_config()
                    
                    assert config.project.name == "Overridden Project"
                    assert config.scan.max_file_size_mb == 100
            finally:
                os.unlink(f.name)

    def test_save_config(self):
        """测试保存配置"""
        config = AppConfig()
        config.project.name = "Saved Project"
        
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as f:
            try:
                manager = ConfigManager()
                manager.save_config(config, Path(f.name))
                
                # 重新加载验证
                manager2 = ConfigManager(f.name)
                loaded_config = manager2.load_config()
                assert loaded_config.project.name == "Saved Project"
            finally:
                os.unlink(f.name)

    def test_generate_default_config(self):
        """测试生成默认配置"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "default.yaml"
            
            manager = ConfigManager()
            manager.generate_default_config(config_path)
            
            assert config_path.exists()
            
            # 验证生成的配置可以加载
            manager2 = ConfigManager(config_path)
            config = manager2.load_config()
            assert isinstance(config, AppConfig)

    def test_reload_config(self):
        """测试重新加载配置"""
        yaml_content = """
project:
  name: "Original Project"

scan:
  paths:
    - "Assets/"

database:
  type: "sqlite"
  path: "./test.db"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            try:
                manager = ConfigManager(f.name)
                config1 = manager.load_config()
                assert config1.project.name == "Original Project"
                
                # 修改文件内容
                with open(f.name, 'w') as f2:
                    f2.write(yaml_content.replace("Original Project", "Modified Project"))
                
                # 重新加载
                config2 = manager.reload()
                assert config2.project.name == "Modified Project"
            finally:
                os.unlink(f.name)

    def test_update_config(self):
        """测试更新配置"""
        manager = ConfigManager()
        manager._config = AppConfig()
        
        updates = {
            "project": {"name": "Updated Project"},
            "scan": {"max_file_size_mb": 100}
        }
        
        updated_config = manager.update_config(updates)
        assert updated_config.project.name == "Updated Project"
        assert updated_config.scan.max_file_size_mb == 100

    def test_convert_env_value(self):
        """测试环境变量值转换"""
        manager = ConfigManager()
        
        # 布尔值
        assert manager._convert_env_value("true") is True
        assert manager._convert_env_value("false") is False
        assert manager._convert_env_value("True") is True
        
        # 整数
        assert manager._convert_env_value("123") == 123
        assert manager._convert_env_value("-456") == -456
        
        # 浮点数
        assert manager._convert_env_value("3.14") == 3.14
        
        # 列表
        assert manager._convert_env_value("a,b,c") == ["a", "b", "c"]
        assert manager._convert_env_value("a, b , c ") == ["a", "b", "c"]
        
        # 字符串
        assert manager._convert_env_value("hello") == "hello"


class TestGlobalFunctions:
    """全局函数测试"""

    def test_get_config_manager_singleton(self):
        """测试配置管理器单例"""
        manager1 = get_config_manager()
        manager2 = get_config_manager()
        assert manager1 is manager2

    @patch('src.core.config.get_config_manager')
    def test_get_config(self, mock_get_manager):
        """测试获取配置"""
        mock_config = AppConfig()
        mock_manager = ConfigManager()
        mock_manager._config = mock_config
        mock_get_manager.return_value = mock_manager
        
        config = get_config()
        assert config is mock_config

    @patch('src.core.config.get_config_manager')
    def test_reload_config(self, mock_get_manager):
        """测试重新加载配置"""
        mock_config = AppConfig()
        mock_manager = ConfigManager()
        mock_manager.reload = lambda: mock_config
        mock_get_manager.return_value = mock_manager
        
        from src.core.config import reload_config
        config = reload_config()
        assert config is mock_config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
