"""Meta文件解析器集成测试

测试Meta解析器与实际Unity项目文件的综合功能。
"""

import pytest
from pathlib import Path
from typing import List

from src.parsers.meta_parser import MetaParser, ImporterType
from src.parsers.base_parser import ParseResultType


class TestMetaParserIntegration:
    """Meta解析器集成测试"""
    
    @pytest.fixture
    def meta_parser(self):
        """创建Meta解析器实例"""
        return MetaParser()
    
    @pytest.fixture
    def fixtures_path(self) -> Path:
        """获取fixture文件路径"""
        return Path(__file__).parent.parent / "fixtures"
    
    def test_parse_all_fixture_files(self, meta_parser, fixtures_path):
        """测试：解析所有fixture文件"""
        if not fixtures_path.exists():
            pytest.skip("Fixtures目录不存在")
        
        meta_files = list(fixtures_path.glob("*.meta"))
        if not meta_files:
            pytest.skip("没有找到Meta文件")
        
        results = meta_parser.parse_batch(meta_files)
        
        # 统计结果
        success_count = sum(1 for r in results if r.is_success)
        failed_count = sum(1 for r in results if r.is_failed)
        
        print(f"\n解析结果统计:")
        print(f"成功: {success_count}")
        print(f"失败: {failed_count}")
        print(f"总计: {len(results)}")
        
        # 验证成功解析的文件
        successful_results = [r for r in results if r.is_success]
        for result in successful_results:
            assert result.guid is not None
            assert len(result.guid) == 32  # GUID长度验证
            assert result.asset_type is not None
            print(f"✅ {Path(result.file_path).name}: {result.asset_type} ({result.guid})")
        
        # 验证失败的文件（应该只有invalid.meta）
        failed_results = [r for r in results if r.is_failed]
        for result in failed_results:
            print(f"❌ {Path(result.file_path).name}: {result.error_message}")
        
        # 至少应该有一些成功的结果
        assert success_count > 0, "至少应该成功解析一些Meta文件"
    
    def test_validate_known_meta_files(self, meta_parser, fixtures_path):
        """测试：验证已知的Meta文件"""
        expected_files = {
            "texture.meta": {
                "guid": "3f4b8c2d1e7a9f6c8d2a4b5e7c9d1f8e",
                "asset_type": "TEXTURE",
                "importer_type": ImporterType.TEXTURE_IMPORTER
            },
            "model.meta": {
                "guid": "8a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d",
                "asset_type": "MODEL",
                "importer_type": ImporterType.MODEL_IMPORTER
            },
            "script.meta": {
                "guid": "6d4e2f1a8b9c0d3e6f2a5b8c1d4e7f0a",
                "asset_type": "SCRIPT",
                "importer_type": ImporterType.MONO_IMPORTER
            }
        }
        
        for filename, expected in expected_files.items():
            meta_path = fixtures_path / filename
            if not meta_path.exists():
                continue
                
            result = meta_parser.parse(meta_path)
            
            assert result.is_success, f"解析{filename}失败: {result.error_message}"
            assert result.guid == expected["guid"], f"{filename} GUID不匹配"
            assert result.asset_type == expected["asset_type"], f"{filename} 资源类型不匹配"
            
            # 验证导入器类型
            assert result.data is not None
            importer_type_str = result.data.get("importer_type")
            assert importer_type_str == expected["importer_type"].value
    
    def test_guid_extraction_performance(self, meta_parser, fixtures_path):
        """测试：GUID提取性能对比"""
        import time
        
        meta_files = list(fixtures_path.glob("*.meta"))
        if not meta_files:
            pytest.skip("没有找到Meta文件")
        
        # 测试完整解析
        start_time = time.time()
        full_results = meta_parser.parse_batch(meta_files)
        full_parse_time = time.time() - start_time
        
        # 测试快速GUID提取
        start_time = time.time()
        guid_results = []
        for meta_file in meta_files:
            guid = meta_parser.extract_guid_only(meta_file)
            guid_results.append(guid)
        quick_extract_time = time.time() - start_time
        
        print(f"\n性能对比:")
        print(f"完整解析时间: {full_parse_time:.4f}秒")
        print(f"快速提取时间: {quick_extract_time:.4f}秒")
        print(f"速度提升: {full_parse_time / quick_extract_time:.2f}x")
        
        # 验证结果一致性
        successful_full_results = [r for r in full_results if r.is_success]
        valid_guid_results = [g for g in guid_results if g is not None]
        
        assert len(successful_full_results) == len(valid_guid_results), "GUID提取结果数量不一致"
        
        # 验证GUID值一致性
        for full_result in successful_full_results:
            filename = Path(full_result.file_path).name
            corresponding_quick_guid = None
            
            for i, meta_file in enumerate(meta_files):
                if meta_file.name == filename:
                    corresponding_quick_guid = guid_results[i]
                    break
            
            assert corresponding_quick_guid is not None, f"未找到{filename}的快速GUID结果"
            assert full_result.guid == corresponding_quick_guid, f"{filename} GUID不一致"
    
    def test_parser_error_handling(self, meta_parser, fixtures_path):
        """测试：解析器错误处理"""
        invalid_meta_path = fixtures_path / "invalid.meta"
        
        if invalid_meta_path.exists():
            result = meta_parser.parse(invalid_meta_path)
            
            assert result.is_failed, "应该解析失败"
            assert result.error_message is not None, "应该有错误信息"
            assert "GUID" in result.error_message, "错误信息应该提及GUID问题"
    
    def test_parser_statistics(self, meta_parser):
        """测试：解析器统计信息"""
        stats = meta_parser.get_parser_stats()
        
        # 验证统计信息完整性
        required_stats = [
            "name", "supported_extensions", "supported_importers", 
            "guid_pattern", "required_fields"
        ]
        
        for stat in required_stats:
            assert stat in stats, f"统计信息缺少{stat}"
        
        # 验证统计信息内容
        assert stats["name"] == "MetaParser"
        assert ".meta" in stats["supported_extensions"]
        assert stats["supported_importers"] > 10  # 应该支持多种导入器
        assert "fileFormatVersion" in stats["required_fields"]
        assert "guid" in stats["required_fields"]
        
        print(f"\n解析器统计信息:")
        for key, value in stats.items():
            print(f"{key}: {value}")
    
    def test_warning_detection(self, meta_parser, fixtures_path):
        """测试：警告检测功能"""
        meta_files = list(fixtures_path.glob("*.meta"))
        if not meta_files:
            pytest.skip("没有找到Meta文件")
        
        results = meta_parser.parse_batch(meta_files)
        
        # 统计警告
        results_with_warnings = [r for r in results if r.warnings]
        
        print(f"\n警告统计:")
        print(f"有警告的文件: {len(results_with_warnings)}")
        print(f"总文件数: {len(results)}")
        
        for result in results_with_warnings:
            filename = Path(result.file_path).name
            print(f"⚠️  {filename}: {len(result.warnings)} 个警告")
            for warning in result.warnings:
                print(f"   - {warning}")
    
    def test_supported_importer_types(self, meta_parser):
        """测试：支持的导入器类型覆盖"""
        expected_importers = {
            "TextureImporter", "ModelImporter", "AudioImporter", 
            "MonoImporter", "NativeFormatImporter", "DefaultImporter",
            "FontImporter", "VideoClipImporter", "ShaderImporter"
        }
        
        supported_importers = meta_parser.supported_importers
        
        # 验证基本导入器类型都被支持
        for importer in expected_importers:
            assert importer in supported_importers, f"缺少对{importer}的支持"
        
        print(f"\n支持的导入器类型 ({len(supported_importers)}个):")
        for importer in sorted(supported_importers):
            print(f"  - {importer}")


def test_meta_parser_module_exports():
    """测试：Meta解析器模块导出"""
    from src.parsers import MetaParser, MetaFileInfo, ImporterType
    from src.parsers import BaseParser, ParseResult, ParseResultType
    
    # 验证类可以正常实例化
    parser = MetaParser()
    assert parser is not None
    
    # 验证枚举类型工作正常
    texture_importer = ImporterType.TEXTURE_IMPORTER
    assert texture_importer.value == "TextureImporter"
    
    # 验证基类功能
    assert hasattr(parser, 'parse')
    assert hasattr(parser, 'can_parse')
    assert hasattr(parser, 'get_supported_extensions')


if __name__ == "__main__":
    # 允许直接运行此测试文件
    pytest.main([__file__, "-v"])
