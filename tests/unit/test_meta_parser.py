"""Meta解析器单元测试

测试Unity Meta文件解析器的各种功能和边界情况。
"""

import pytest
import tempfile
from pathlib import Path
from typing import Dict, Any

from src.parsers.meta_parser import MetaParser, MetaFileInfo, ImporterType
from src.parsers.base_parser import ParseResultType
from src.utils.yaml_utils import YAMLParser


class TestMetaParser:
    """Meta解析器测试类"""
    
    @pytest.fixture
    def meta_parser(self):
        """创建Meta解析器实例"""
        return MetaParser()
    
    @pytest.fixture 
    def strict_meta_parser(self):
        """创建严格模式的Meta解析器实例"""
        return MetaParser(strict_mode=True)
    
    @pytest.fixture
    def sample_texture_meta_data(self) -> Dict[str, Any]:
        """纹理Meta文件测试数据"""
        return {
            "fileFormatVersion": 2,
            "guid": "3f4b8c2d1e7a9f6c8d2a4b5e7c9d1f8e",
            "TextureImporter": {
                "internalIDToNameTable": [],
                "externalObjects": {},
                "serializedVersion": 12,
                "mipmaps": {
                    "mipMapMode": 0,
                    "enableMipMap": 1
                },
                "textureFormat": 1,
                "maxTextureSize": 2048,
                "userData": "",
                "assetBundleName": "",
                "assetBundleVariant": ""
            }
        }
    
    @pytest.fixture
    def sample_model_meta_data(self) -> Dict[str, Any]:
        """模型Meta文件测试数据"""
        return {
            "fileFormatVersion": 2,
            "guid": "8a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d",
            "ModelImporter": {
                "serializedVersion": 21300,
                "internalIDToNameTable": [],
                "materials": {
                    "materialImportMode": 2
                },
                "animations": {
                    "legacyGenerateAnimations": 4
                }
            },
            "userData": "test_data",
            "assetBundleName": "test_bundle"
        }
    
    @pytest.fixture
    def sample_script_meta_data(self) -> Dict[str, Any]:
        """脚本Meta文件测试数据"""
        return {
            "fileFormatVersion": 2,
            "guid": "6d4e2f1a8b9c0d3e6f2a5b8c1d4e7f0a",
            "MonoImporter": {
                "externalObjects": {},
                "serializedVersion": 2,
                "defaultReferences": [],
                "executionOrder": 0,
                "icon": {"instanceID": 0}
            }
        }
    
    @pytest.fixture
    def invalid_meta_data(self) -> Dict[str, Any]:
        """无效Meta文件测试数据"""
        return {
            "fileFormatVersion": 2,
            "guid": "invalid-guid-format",  # 无效的GUID格式
            "TextureImporter": {}
        }
    
    def create_temp_meta_file(self, data: Dict[str, Any]) -> Path:
        """创建临时Meta文件"""
        yaml_parser = YAMLParser()
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.meta', delete=False)
        temp_path = Path(temp_file.name)
        temp_file.close()
        
        yaml_parser.save_to_file(data, temp_path)
        return temp_path
    
    def test_can_parse_valid_meta_file(self, meta_parser, sample_texture_meta_data):
        """测试：能否识别有效的Meta文件"""
        temp_path = self.create_temp_meta_file(sample_texture_meta_data)
        try:
            assert meta_parser.can_parse(temp_path) is True
        finally:
            temp_path.unlink()
    
    def test_cannot_parse_non_meta_file(self, meta_parser):
        """测试：不能解析非Meta文件"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
        temp_path = Path(temp_file.name)
        temp_file.close()
        
        try:
            assert meta_parser.can_parse(temp_path) is False
        finally:
            temp_path.unlink()
    
    def test_cannot_parse_nonexistent_file(self, meta_parser):
        """测试：不能解析不存在的文件"""
        fake_path = Path("nonexistent.meta")
        assert meta_parser.can_parse(fake_path) is False
    
    def test_get_supported_extensions(self, meta_parser):
        """测试：获取支持的扩展名"""
        extensions = meta_parser.get_supported_extensions()
        assert extensions == ['.meta']
    
    def test_parse_texture_meta_success(self, meta_parser, sample_texture_meta_data):
        """测试：成功解析纹理Meta文件"""
        temp_path = self.create_temp_meta_file(sample_texture_meta_data)
        try:
            result = meta_parser.parse(temp_path)
            
            assert result.is_success is True
            assert result.guid == "3f4b8c2d1e7a9f6c8d2a4b5e7c9d1f8e"
            assert result.asset_type == "TEXTURE"
            assert result.data is not None
            assert result.data['importer_type'] == ImporterType.TEXTURE_IMPORTER.value
            
        finally:
            temp_path.unlink()
    
    def test_parse_model_meta_success(self, meta_parser, sample_model_meta_data):
        """测试：成功解析模型Meta文件"""
        temp_path = self.create_temp_meta_file(sample_model_meta_data)
        try:
            result = meta_parser.parse(temp_path)
            
            assert result.is_success is True
            assert result.guid == "8a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d"
            assert result.asset_type == "MODEL"
            assert result.data['user_data'] == "test_data"
            assert result.data['asset_bundle_name'] == "test_bundle"
            
        finally:
            temp_path.unlink()
    
    def test_parse_script_meta_success(self, meta_parser, sample_script_meta_data):
        """测试：成功解析脚本Meta文件"""
        temp_path = self.create_temp_meta_file(sample_script_meta_data)
        try:
            result = meta_parser.parse(temp_path)
            
            assert result.is_success is True
            assert result.guid == "6d4e2f1a8b9c0d3e6f2a5b8c1d4e7f0a"
            assert result.asset_type == "SCRIPT"
            assert result.data['importer_type'] == ImporterType.MONO_IMPORTER.value
            
        finally:
            temp_path.unlink()
    
    def test_parse_invalid_guid_format(self, meta_parser, invalid_meta_data):
        """测试：解析无效GUID格式的Meta文件"""
        temp_path = self.create_temp_meta_file(invalid_meta_data)
        try:
            result = meta_parser.parse(temp_path)
            
            assert result.is_failed is True
            assert "无效的GUID格式" in result.error_message
            
        finally:
            temp_path.unlink()
    
    def test_parse_missing_required_fields(self, meta_parser):
        """测试：解析缺少必需字段的Meta文件"""
        incomplete_data = {
            "fileFormatVersion": 2
            # 缺少 guid 字段
        }
        temp_path = self.create_temp_meta_file(incomplete_data)
        try:
            result = meta_parser.parse(temp_path)
            
            assert result.is_failed is True
            assert "缺少必需字段" in result.error_message
            
        finally:
            temp_path.unlink()
    
    def test_parse_invalid_yaml_format(self, meta_parser):
        """测试：解析无效YAML格式的文件"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.meta', delete=False)
        temp_path = Path(temp_file.name)
        
        # 写入无效的YAML内容
        temp_file.write("invalid: yaml: content:\n  - broken\n    - structure")
        temp_file.close()
        
        try:
            result = meta_parser.parse(temp_path)
            assert result.is_failed is True
            
        finally:
            temp_path.unlink()
    
    def test_validate_guid_format(self, meta_parser):
        """测试：GUID格式验证"""
        # 有效的GUID格式
        valid_guids = [
            "3f4b8c2d1e7a9f6c8d2a4b5e7c9d1f8e",
            "0123456789abcdef0123456789ABCDEF",
            "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
        ]
        
        for guid in valid_guids:
            assert meta_parser._validate_guid(guid) is True
        
        # 无效的GUID格式
        invalid_guids = [
            "invalid-guid-format",
            "3f4b8c2d-1e7a-9f6c-8d2a-4b5e7c9d1f8e",  # 带连字符
            "3f4b8c2d1e7a9f6c8d2a4b5e7c9d1f8",       # 少一位
            "3f4b8c2d1e7a9f6c8d2a4b5e7c9d1f8ee",      # 多一位
            "3f4b8c2d1e7a9f6c8d2a4b5e7c9d1f8g",       # 包含非十六进制字符
            "",                                        # 空字符串
            None,                                      # None值
            123                                        # 非字符串类型
        ]
        
        for guid in invalid_guids:
            assert meta_parser._validate_guid(guid) is False
    
    def test_detect_importer_type(self, meta_parser, sample_texture_meta_data):
        """测试：导入器类型检测"""
        importer_type, importer_data = meta_parser._detect_importer_type(sample_texture_meta_data)
        
        assert importer_type == ImporterType.TEXTURE_IMPORTER
        assert importer_data == sample_texture_meta_data["TextureImporter"]
    
    def test_detect_unknown_importer_type(self, meta_parser):
        """测试：检测未知导入器类型"""
        unknown_data = {
            "fileFormatVersion": 2,
            "guid": "3f4b8c2d1e7a9f6c8d2a4b5e7c9d1f8e",
            "UnknownImporter": {
                "someProperty": "someValue"
            }
        }
        
        importer_type, importer_data = meta_parser._detect_importer_type(unknown_data)
        
        assert importer_type == ImporterType.UNKNOWN
        assert importer_data == {}
    
    def test_extract_guid_only(self, meta_parser, sample_texture_meta_data):
        """测试：快速提取GUID功能"""
        temp_path = self.create_temp_meta_file(sample_texture_meta_data)
        try:
            guid = meta_parser.extract_guid_only(temp_path)
            assert guid == "3f4b8c2d1e7a9f6c8d2a4b5e7c9d1f8e"
            
        finally:
            temp_path.unlink()
    
    def test_extract_guid_only_invalid_file(self, meta_parser):
        """测试：从无效文件快速提取GUID"""
        fake_path = Path("nonexistent.meta")
        guid = meta_parser.extract_guid_only(fake_path)
        assert guid is None
    
    def test_meta_file_info_creation(self):
        """测试：Meta文件信息对象创建"""
        meta_info = MetaFileInfo(
            guid="3f4b8c2d1e7a9f6c8d2a4b5e7c9d1f8e",
            file_format_version=2,
            importer_type=ImporterType.TEXTURE_IMPORTER,
            importer_data={"textureFormat": 1},
            user_data="test_data",
            asset_bundle_name="test_bundle",
            asset_bundle_variant="variant"
        )
        
        assert meta_info.guid == "3f4b8c2d1e7a9f6c8d2a4b5e7c9d1f8e"
        assert meta_info.importer_type == ImporterType.TEXTURE_IMPORTER
        assert meta_info.get_asset_type() == "TEXTURE"
        
        # 测试转换为字典
        dict_data = meta_info.to_dict()
        assert dict_data["guid"] == meta_info.guid
        assert dict_data["importer_type"] == ImporterType.TEXTURE_IMPORTER.value
        assert dict_data["user_data"] == "test_data"
    
    def test_importer_type_enum(self):
        """测试：导入器类型枚举"""
        # 测试从字符串创建
        texture_importer = ImporterType.from_string("TextureImporter")
        assert texture_importer == ImporterType.TEXTURE_IMPORTER
        
        unknown_importer = ImporterType.from_string("NonExistentImporter")
        assert unknown_importer == ImporterType.UNKNOWN
    
    def test_batch_parsing(self, meta_parser, sample_texture_meta_data, sample_model_meta_data):
        """测试：批量解析功能"""
        temp_path1 = self.create_temp_meta_file(sample_texture_meta_data)
        temp_path2 = self.create_temp_meta_file(sample_model_meta_data)
        
        try:
            results = meta_parser.parse_batch([temp_path1, temp_path2])
            
            assert len(results) == 2
            assert all(result.is_success for result in results)
            
            # 验证第一个结果（纹理）
            assert results[0].asset_type == "TEXTURE"
            assert results[0].guid == "3f4b8c2d1e7a9f6c8d2a4b5e7c9d1f8e"
            
            # 验证第二个结果（模型）
            assert results[1].asset_type == "MODEL"
            assert results[1].guid == "8a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d"
            
        finally:
            temp_path1.unlink()
            temp_path2.unlink()
    
    def test_strict_mode_behavior(self, strict_meta_parser, sample_texture_meta_data, invalid_meta_data):
        """测试：严格模式行为"""
        temp_path1 = self.create_temp_meta_file(sample_texture_meta_data)
        temp_path2 = self.create_temp_meta_file(invalid_meta_data)
        
        try:
            # 严格模式下，遇到错误应该停止
            results = strict_meta_parser.parse_batch([temp_path1, temp_path2])
            
            # 第一个文件应该成功解析
            assert len(results) >= 1
            assert results[0].is_success is True
            
            # 如果有第二个结果，应该是失败的
            if len(results) > 1:
                assert results[1].is_failed is True
                
        finally:
            temp_path1.unlink()
            temp_path2.unlink()
    
    def test_check_potential_issues(self, meta_parser):
        """测试：潜在问题检查"""
        # 创建一个有潜在问题的Meta信息
        meta_info = MetaFileInfo(
            guid="3f4b8c2d1e7a9f6c8d2a4b5e7c9d1f8e",
            file_format_version=1,  # 旧版本
            importer_type=ImporterType.UNKNOWN,  # 未知类型
            importer_data={}  # 空数据
        )
        
        raw_data = {
            "fileFormatVersion": 1,
            "guid": "3f4b8c2d1e7a9f6c8d2a4b5e7c9d1f8e",
            "unknownField": "unknownValue"  # 未知字段
        }
        
        warnings = meta_parser._check_potential_issues(meta_info, raw_data)
        
        # 应该检测到多个问题
        assert len(warnings) > 0
        warning_text = " ".join(warnings)
        assert "未能识别导入器类型" in warning_text
        assert "导入器数据为空" in warning_text
        assert "文件格式版本较旧" in warning_text
        assert "发现未知字段" in warning_text
    
    def test_get_parser_stats(self, meta_parser):
        """测试：获取解析器统计信息"""
        stats = meta_parser.get_parser_stats()
        
        assert "name" in stats
        assert "supported_extensions" in stats
        assert "supported_importers" in stats
        assert "guid_pattern" in stats
        assert "required_fields" in stats
        
        assert stats["name"] == "MetaParser"
        assert stats["supported_extensions"] == ['.meta']
        assert stats["supported_importers"] > 0
        assert stats["required_fields"] == ['fileFormatVersion', 'guid']


class TestFixtureFiles:
    """测试fixture文件的解析"""
    
    @pytest.fixture
    def meta_parser(self):
        """创建Meta解析器实例"""
        return MetaParser()
    
    def test_parse_texture_fixture(self, meta_parser):
        """测试：解析纹理fixture文件"""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "texture.meta"
        
        if fixture_path.exists():
            result = meta_parser.parse(fixture_path)
            assert result.is_success is True
            assert result.asset_type == "TEXTURE"
            assert result.guid == "3f4b8c2d1e7a9f6c8d2a4b5e7c9d1f8e"
    
    def test_parse_model_fixture(self, meta_parser):
        """测试：解析模型fixture文件"""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "model.meta"
        
        if fixture_path.exists():
            result = meta_parser.parse(fixture_path)
            assert result.is_success is True
            assert result.asset_type == "MODEL"
            assert result.guid == "8a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d"
    
    def test_parse_script_fixture(self, meta_parser):
        """测试：解析脚本fixture文件"""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "script.meta"
        
        if fixture_path.exists():
            result = meta_parser.parse(fixture_path)
            assert result.is_success is True
            assert result.asset_type == "SCRIPT"
            assert result.guid == "6d4e2f1a8b9c0d3e6f2a5b8c1d4e7f0a"
    
    def test_parse_invalid_fixture(self, meta_parser):
        """测试：解析无效fixture文件"""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "invalid.meta"
        
        if fixture_path.exists():
            result = meta_parser.parse(fixture_path)
            assert result.is_failed is True
            assert "无效的GUID格式" in result.error_message
