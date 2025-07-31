"""测试项目基础架构是否正确搭建"""

import sys
from pathlib import Path

import pytest

# 添加src路径到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


def test_project_structure():
    """测试项目目录结构是否完整"""
    project_root = Path(__file__).parent.parent.parent

    # 检查主要目录
    assert (project_root / "src").exists()
    assert (project_root / "src" / "core").exists()
    assert (project_root / "src" / "parsers").exists()
    assert (project_root / "src" / "models").exists()
    assert (project_root / "src" / "utils").exists()
    assert (project_root / "src" / "cli").exists()
    assert (project_root / "src" / "api").exists()

    assert (project_root / "config").exists()
    assert (project_root / "tests").exists()
    assert (project_root / "tests" / "unit").exists()
    assert (project_root / "tests" / "integration").exists()
    assert (project_root / "tests" / "fixtures").exists()
    assert (project_root / "docs").exists()


def test_config_files_exist():
    """测试配置文件是否存在"""
    project_root = Path(__file__).parent.parent.parent

    assert (project_root / "pyproject.toml").exists()
    assert (project_root / "config" / "default.yaml").exists()
    assert (project_root / "config" / "schema.json").exists()
    assert (project_root / ".pre-commit-config.yaml").exists()
    assert (project_root / "pytest.ini").exists()


def test_init_files_exist():
    """测试__init__.py文件是否存在"""
    project_root = Path(__file__).parent.parent.parent

    assert (project_root / "src" / "__init__.py").exists()
    assert (project_root / "src" / "core" / "__init__.py").exists()
    assert (project_root / "src" / "parsers" / "__init__.py").exists()
    assert (project_root / "src" / "models" / "__init__.py").exists()
    assert (project_root / "src" / "utils" / "__init__.py").exists()
    assert (project_root / "src" / "cli" / "__init__.py").exists()
    assert (project_root / "src" / "api" / "__init__.py").exists()


def test_module_imports():
    """测试基础模块导入（当模块实际存在时）"""
    # 目前只测试包导入不报错
    try:
        import src
        import src.api
        import src.cli
        import src.core
        import src.models
        import src.parsers
        import src.utils
    except ImportError as e:
        pytest.skip(f"模块导入测试跳过，等待模块实现: {e}")


if __name__ == "__main__":
    pytest.main([__file__])
