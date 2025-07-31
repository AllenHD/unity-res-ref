"""YAML工具单元测试

测试YAML处理工具的各种功能。
"""

import pytest
import tempfile
from pathlib import Path
from typing import Dict, Any

from src.utils.yaml_utils import YAMLParser, load_yaml_file, validate_yaml_keys


class TestYAMLParser:
    """YAML解析器测试类"""
    
    @pytest.fixture
    def yaml_parser(self):
        """创建YAML解析器实例"""
        return YAMLParser()
    
    @pytest.fixture
    def sample_yaml_data(self) -> Dict[str, Any]:
        """示例YAML数据"""
        return {
            "fileFormatVersion": 2,
            "guid": "3f4b8c2d1e7a9f6c8d2a4b5e7c9d1f8e",
            "TextureImporter": {
                "serializedVersion": 12,
                "mipmaps": {
                    "mipMapMode": 0,
                    "enableMipMap": True
                },
                "textureSettings": {
                    "filterMode": 1,
                    "aniso": 1
                }
            },
            "userData": "",
            "assetBundleName": "",
            "list_data": [1, 2, 3, "test"],
            "boolean_data": True,
            "null_data": None
        }
    
    def create_temp_yaml_file(self, data: Dict[str, Any]) -> Path:
        """创建临时YAML文件"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        temp_path = Path(temp_file.name)
        temp_file.close()
        
        yaml_parser = YAMLParser()
        yaml_parser.save_to_file(data, temp_path)
        return temp_path
    
    def test_load_from_file_success(self, yaml_parser, sample_yaml_data):
        """测试：成功从文件加载YAML"""
        temp_path = self.create_temp_yaml_file(sample_yaml_data)
        try:
            loaded_data = yaml_parser.load_from_file(temp_path)
            
            assert loaded_data is not None
            assert loaded_data["fileFormatVersion"] == 2
            assert loaded_data["guid"] == "3f4b8c2d1e7a9f6c8d2a4b5e7c9d1f8e"
            assert loaded_data["TextureImporter"]["mipmaps"]["enableMipMap"] is True
            assert loaded_data["list_data"] == [1, 2, 3, "test"]
            
        finally:
            temp_path.unlink()
    
    def test_load_from_nonexistent_file(self, yaml_parser):
        """测试：加载不存在的文件"""
        nonexistent_path = Path("nonexistent.yaml")
        result = yaml_parser.load_from_file(nonexistent_path)
        assert result is None
    
    def test_load_from_directory(self, yaml_parser):
        """测试：尝试加载目录路径"""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            result = yaml_parser.load_from_file(temp_dir)
            assert result is None
        finally:
            temp_dir.rmdir()
    
    def test_load_from_invalid_yaml_file(self, yaml_parser):
        """测试：加载无效的YAML文件"""
        invalid_yaml = "invalid: yaml: content:\n  - broken\n    - structure"
        
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        temp_path = Path(temp_file.name)
        temp_file.write(invalid_yaml)
        temp_file.close()
        
        try:
            result = yaml_parser.load_from_file(temp_path)
            assert result is None
        finally:
            temp_path.unlink()
    
    def test_load_from_string_success(self, yaml_parser):
        """测试：成功从字符串加载YAML"""
        yaml_string = """
fileFormatVersion: 2
guid: 3f4b8c2d1e7a9f6c8d2a4b5e7c9d1f8e
TextureImporter:
  serializedVersion: 12
  mipmaps:
    mipMapMode: 0
    enableMipMap: true
userData: ""
"""
        
        loaded_data = yaml_parser.load_from_string(yaml_string)
        
        assert loaded_data is not None
        assert loaded_data["fileFormatVersion"] == 2
        assert loaded_data["guid"] == "3f4b8c2d1e7a9f6c8d2a4b5e7c9d1f8e"
        assert loaded_data["TextureImporter"]["mipmaps"]["enableMipMap"] is True
    
    def test_load_from_empty_string(self, yaml_parser):
        """测试：从空字符串加载YAML"""
        result = yaml_parser.load_from_string("")
        assert result is None
        
        result = yaml_parser.load_from_string("   ")
        assert result is None
    
    def test_load_from_invalid_yaml_string(self, yaml_parser):
        """测试：从无效YAML字符串加载"""
        invalid_yaml = "invalid: yaml: content:\n  - broken\n    - structure"
        
        result = yaml_parser.load_from_string(invalid_yaml)
        assert result is None
    
    def test_save_to_file_success(self, yaml_parser, sample_yaml_data):
        """测试：成功保存YAML到文件"""
        temp_file = tempfile.NamedTemporaryFile(suffix='.yaml', delete=False)
        temp_path = Path(temp_file.name)
        temp_file.close()
        
        try:
            success = yaml_parser.save_to_file(sample_yaml_data, temp_path)
            assert success is True
            
            # 验证保存的内容
            loaded_data = yaml_parser.load_from_file(temp_path)
            assert loaded_data == sample_yaml_data
            
        finally:
            temp_path.unlink()
    
    def test_save_to_file_create_directory(self, yaml_parser, sample_yaml_data):
        """测试：保存文件时自动创建目录"""
        temp_dir = Path(tempfile.mkdtemp())
        nested_path = temp_dir / "nested" / "directory" / "test.yaml"
        
        try:
            success = yaml_parser.save_to_file(sample_yaml_data, nested_path)
            assert success is True
            assert nested_path.exists()
            
            # 验证保存的内容
            loaded_data = yaml_parser.load_from_file(nested_path)
            assert loaded_data == sample_yaml_data
            
        finally:
            if nested_path.exists():
                nested_path.unlink()
            if nested_path.parent.exists():
                nested_path.parent.rmdir()
            if nested_path.parent.parent.exists():
                nested_path.parent.parent.rmdir()
            temp_dir.rmdir()
    
    def test_validate_structure_success(self, yaml_parser, sample_yaml_data):
        """测试：成功验证YAML结构"""
        required_keys = ["fileFormatVersion", "guid", "TextureImporter"]
        
        result = yaml_parser.validate_structure(sample_yaml_data, required_keys)
        assert result is True
    
    def test_validate_structure_missing_keys(self, yaml_parser, sample_yaml_data):
        """测试：验证缺少必需键的YAML结构"""
        required_keys = ["fileFormatVersion", "guid", "missingKey"]
        
        result = yaml_parser.validate_structure(sample_yaml_data, required_keys)
        assert result is False
    
    def test_validate_structure_non_dict_data(self, yaml_parser):
        """测试：验证非字典数据"""
        non_dict_data = ["not", "a", "dict"]
        required_keys = ["key1", "key2"]
        
        result = yaml_parser.validate_structure(non_dict_data, required_keys)
        assert result is False
    
    def test_yaml_parser_initialization(self):
        """测试：YAML解析器初始化"""
        # 默认配置
        parser1 = YAMLParser()
        assert parser1.yaml.preserve_quotes is True
        assert parser1.yaml.default_flow_style is False
        assert parser1.yaml.width == 4096
        
        # 自定义配置
        parser2 = YAMLParser(preserve_quotes=False)
        assert parser2.yaml.preserve_quotes is False


class TestYAMLUtilityFunctions:
    """测试YAML工具函数"""
    
    @pytest.fixture
    def sample_yaml_data(self) -> Dict[str, Any]:
        """示例YAML数据"""
        return {
            "key1": "value1",
            "key2": {
                "nested_key": "nested_value"
            },
            "key3": [1, 2, 3]
        }
    
    def test_load_yaml_file_convenience_function(self, sample_yaml_data):
        """测试：load_yaml_file便捷函数"""
        yaml_parser = YAMLParser()
        temp_path = Path(tempfile.mktemp(suffix='.yaml'))
        
        try:
            # 先保存文件
            yaml_parser.save_to_file(sample_yaml_data, temp_path)
            
            # 使用便捷函数加载
            loaded_data = load_yaml_file(temp_path)
            
            assert loaded_data is not None
            assert loaded_data == sample_yaml_data
            
        finally:
            if temp_path.exists():
                temp_path.unlink()
    
    def test_load_yaml_file_nonexistent(self):
        """测试：load_yaml_file加载不存在的文件"""
        result = load_yaml_file("nonexistent.yaml")
        assert result is None
    
    def test_validate_yaml_keys_convenience_function(self, sample_yaml_data):
        """测试：validate_yaml_keys便捷函数"""
        # 验证存在的键
        result = validate_yaml_keys(sample_yaml_data, ["key1", "key2"])
        assert result is True
        
        # 验证不存在的键
        result = validate_yaml_keys(sample_yaml_data, ["key1", "nonexistent_key"])
        assert result is False
    
    def test_validate_yaml_keys_empty_requirements(self, sample_yaml_data):
        """测试：验证空的必需键列表"""
        result = validate_yaml_keys(sample_yaml_data, [])
        assert result is True
    
    def test_validate_yaml_keys_non_dict_data(self):
        """测试：验证非字典数据的键"""
        non_dict_data = "not a dict"
        result = validate_yaml_keys(non_dict_data, ["key1"])
        assert result is False


class TestYAMLParserEdgeCases:
    """测试YAML解析器的边界情况"""
    
    @pytest.fixture
    def yaml_parser(self):
        """创建YAML解析器实例"""
        return YAMLParser()
    
    def test_load_empty_yaml_file(self, yaml_parser):
        """测试：加载空的YAML文件"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        temp_path = Path(temp_file.name)
        temp_file.write("")  # 空内容
        temp_file.close()
        
        try:
            result = yaml_parser.load_from_file(temp_path)
            # 空文件应该返回None或空字典，具体取决于YAML库的行为
            assert result in [None, {}]
        finally:
            temp_path.unlink()
    
    def test_load_yaml_with_special_characters(self, yaml_parser):
        """测试：加载包含特殊字符的YAML"""
        special_data = {
            "unicode_text": "测试中文字符 🎯",
            "special_chars": "!@#$%^&*()[]{}|\\:;\"'<>?,./",
            "multiline_text": "Line 1\nLine 2\nLine 3",
            "quoted_values": {
                "single_quoted": "'single quotes'",
                "double_quoted": '"double quotes"'
            }
        }
        
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        temp_path = Path(temp_file.name)
        temp_file.close()
        
        try:
            # 保存并重新加载
            success = yaml_parser.save_to_file(special_data, temp_path)
            assert success is True
            
            loaded_data = yaml_parser.load_from_file(temp_path)
            assert loaded_data is not None
            assert loaded_data["unicode_text"] == "测试中文字符 🎯"
            assert "multiline_text" in loaded_data
            
        finally:
            temp_path.unlink()
    
    def test_load_large_yaml_file(self, yaml_parser):
        """测试：加载大型YAML文件"""
        # 创建一个相对较大的数据结构
        large_data = {
            "large_list": list(range(1000)),
            "nested_structure": {}
        }
        
        # 创建深度嵌套的结构
        current = large_data["nested_structure"]
        for i in range(10):
            current[f"level_{i}"] = {
                "data": f"value_{i}",
                "nested": {}
            }
            current = current[f"level_{i}"]["nested"]
        
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        temp_path = Path(temp_file.name)
        temp_file.close()
        
        try:
            success = yaml_parser.save_to_file(large_data, temp_path)
            assert success is True
            
            loaded_data = yaml_parser.load_from_file(temp_path)
            assert loaded_data is not None
            assert len(loaded_data["large_list"]) == 1000
            assert "nested_structure" in loaded_data
            
        finally:
            temp_path.unlink()
    
    def test_yaml_parser_encoding_handling(self, yaml_parser):
        """测试：YAML解析器编码处理"""
        # 创建包含各种编码字符的数据
        unicode_data = {
            "chinese": "中文测试",
            "japanese": "日本語テスト",
            "korean": "한국어 테스트",
            "arabic": "اختبار عربي",
            "emoji": "🎯🚀✅❌🔧📝",
            "mixed": "Mixed English 中文 🎯"
        }
        
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8')
        temp_path = Path(temp_file.name)
        temp_file.close()
        
        try:
            success = yaml_parser.save_to_file(unicode_data, temp_path)
            assert success is True
            
            loaded_data = yaml_parser.load_from_file(temp_path)
            assert loaded_data is not None
            assert loaded_data["chinese"] == "中文测试"
            assert loaded_data["emoji"] == "🎯🚀✅❌🔧📝"
            
        finally:
            temp_path.unlink()
