"""Prefab解析器测试

测试PrefabParser的功能。
"""

import pytest
import tempfile
from pathlib import Path
from typing import Dict, List

from src.parsers.prefab_parser import PrefabParser, create_prefab_parser, GameObjectInfo, ReferenceInfo
from src.parsers.base_parser import ParseResultType


class TestPrefabParser:
    """PrefabParser测试类"""
    
    @pytest.fixture
    def sample_prefab_content(self):
        """示例Prefab文件内容"""
        return '''%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &1234567890
GameObject:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  serializedVersion: 6
  m_Component:
  - component: {fileID: 1234567891}
  - component: {fileID: 1234567892}
  m_Layer: 0
  m_Name: TestObject
  m_TagString: Untagged
  m_Icon: {fileID: 0}
  m_NavMeshLayer: 0
  m_StaticEditorFlags: 0
  m_IsActive: 1
--- !u!4 &1234567891
Transform:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  m_GameObject: {fileID: 1234567890}
  m_LocalRotation: {x: 0, y: 0, z: 0, w: 1}
  m_LocalPosition: {x: 0, y: 0, z: 0}
  m_LocalScale: {x: 1, y: 1, z: 1}
  m_Children: []
  m_Father: {fileID: 0}
  m_RootOrder: 0
  m_LocalEulerAnglesHint: {x: 0, y: 0, z: 0}
--- !u!23 &1234567892
MeshRenderer:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  m_GameObject: {fileID: 1234567890}
  m_Enabled: 1
  m_CastShadows: 1
  m_ReceiveShadows: 1
  m_DynamicOccludee: 1
  m_MotionVectors: 1
  m_LightProbeUsage: 1
  m_Materials:
  - {fileID: 2100000, guid: abcdef1234567890abcdef1234567890, type: 2}
  m_StaticBatchInfo:
    firstSubMesh: 0
    subMeshCount: 0
  m_StaticBatchRoot: {fileID: 0}
'''
    
    @pytest.fixture
    def temp_prefab_file(self, sample_prefab_content):
        """创建临时Prefab文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.prefab', delete=False) as f:
            f.write(sample_prefab_content)
            temp_path = Path(f.name)
        
        yield temp_path
        temp_path.unlink(missing_ok=True)
    
    def test_parser_initialization(self):
        """测试解析器初始化"""
        parser = PrefabParser()
        assert parser is not None
        assert not parser.strict_mode
        
        strict_parser = PrefabParser(strict_mode=True)
        assert strict_parser.strict_mode
    
    def test_can_parse(self):
        """测试文件类型识别"""
        parser = PrefabParser()
        
        # 应该能解析的文件
        assert parser.can_parse(Path("test.prefab"))
        assert parser.can_parse(Path("complex.prefab"))
        
        # 不应该解析的文件
        assert not parser.can_parse(Path("test.scene"))
        assert not parser.can_parse(Path("test.meta"))
        assert not parser.can_parse(Path("test.txt"))
    
    def test_supported_extensions(self):
        """测试支持的扩展名"""
        parser = PrefabParser()
        extensions = parser.get_supported_extensions()
        
        assert isinstance(extensions, list)
        assert '.prefab' in extensions
        assert len(extensions) == 1
    
    def test_parse_valid_prefab(self, temp_prefab_file):
        """测试解析有效的Prefab文件"""
        parser = PrefabParser()
        result = parser.parse(temp_prefab_file)
        
        # 验证解析结果
        assert result.is_success
        assert result.asset_type == "Prefab"
        assert result.data is not None
        
        # 验证解析的数据结构
        data = result.data
        assert 'game_objects' in data
        assert 'references' in data
        assert 'component_references' in data
        assert 'total_objects' in data
        assert 'total_references' in data
        assert 'root_objects' in data
        
        # 验证GameObject解析
        game_objects = data['game_objects']
        assert len(game_objects) > 0
        
        # 查找测试对象
        test_obj = None
        for obj in game_objects:
            if isinstance(obj, dict) and obj.get('name') == 'TestObject':
                test_obj = obj
                break
        
        assert test_obj is not None
        assert test_obj['file_id'] == '1234567890'
        assert test_obj['name'] == 'TestObject'
        assert test_obj['tag'] == 'Untagged'
        assert test_obj['layer'] == 0
        assert test_obj['active'] is True
        
        # 验证组件
        components = test_obj['components']
        assert len(components) == 2
        
        # 验证引用解析
        references = data['references']
        assert len(references) > 0
        
        # 查找材质引用
        material_ref = None
        for ref in references:
            if isinstance(ref, dict) and ref.get('guid') == 'abcdef1234567890abcdef1234567890':
                material_ref = ref
                break
        
        assert material_ref is not None
        assert material_ref['file_id'] == '2100000'
        assert material_ref['type'] == 2  # Material类型
        assert material_ref['reference_type'] == 'Material'
    
    def test_parse_nonexistent_file(self):
        """测试解析不存在的文件"""
        parser = PrefabParser()
        result = parser.parse(Path("nonexistent.prefab"))
        
        assert result.is_failed
        assert "文件路径验证失败" in result.error_message
    
    def test_parse_invalid_prefab(self):
        """测试解析无效的Prefab文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.prefab', delete=False) as f:
            f.write("Invalid YAML content {")
            temp_path = Path(f.name)
        
        try:
            parser = PrefabParser()
            result = parser.parse(temp_path)
            
            # 应该失败但不抛出异常
            assert result.is_failed
            assert result.error_message is not None
            
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_extract_asset_references(self, temp_prefab_file):
        """测试提取资源引用"""
        parser = PrefabParser()
        guids = parser.extract_asset_references(temp_prefab_file)
        
        assert isinstance(guids, list)
        assert 'abcdef1234567890abcdef1234567890' in guids
        
        # 确保没有包含全零GUID
        assert '00000000000000000000000000000000' not in guids
    
    def test_get_prefab_hierarchy(self, temp_prefab_file):
        """测试获取Prefab层次结构"""
        parser = PrefabParser()
        hierarchy = parser.get_prefab_hierarchy(temp_prefab_file)
        
        assert hierarchy is not None
        assert 'root_objects' in hierarchy
        assert 'total_objects' in hierarchy
        assert 'objects' in hierarchy
        
        # 验证根对象
        root_objects = hierarchy['root_objects']
        assert isinstance(root_objects, list)
        assert len(root_objects) > 0
        
        # 验证对象映射
        objects = hierarchy['objects']
        assert isinstance(objects, dict)
        assert '1234567890' in objects
    
    def test_create_prefab_parser_function(self):
        """测试便捷创建函数"""
        # 默认模式
        parser = create_prefab_parser()
        assert isinstance(parser, PrefabParser)
        assert not parser.strict_mode
        
        # 严格模式
        strict_parser = create_prefab_parser(strict_mode=True)
        assert isinstance(strict_parser, PrefabParser)
        assert strict_parser.strict_mode
    
    def test_batch_parsing(self, temp_prefab_file):
        """测试批量解析"""
        parser = PrefabParser()
        
        # 创建另一个临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.prefab', delete=False) as f:
            f.write("%YAML 1.1\n--- !u!1 &123\nGameObject:\n  m_Name: Simple")
            temp_path2 = Path(f.name)
        
        try:
            results = parser.parse_batch([temp_prefab_file, temp_path2])
            
            assert len(results) == 2
            assert all(isinstance(result.file_path, str) for result in results)
            
            # 第一个文件应该成功解析
            assert results[0].is_success
            
        finally:
            temp_path2.unlink(missing_ok=True)
    
    def test_complex_prefab_structure(self):
        """测试复杂Prefab结构解析"""
        complex_content = '''%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &100
GameObject:
  m_Name: Parent
  m_Component:
  - component: {fileID: 101}
  m_IsActive: 1
--- !u!4 &101
Transform:
  m_GameObject: {fileID: 100}
  m_Children:
  - {fileID: 201}
  - {fileID: 301}
--- !u!1 &200
GameObject:
  m_Name: Child1
  m_Component:
  - component: {fileID: 201}
--- !u!4 &201
Transform:
  m_GameObject: {fileID: 200}
  m_Father: {fileID: 101}
--- !u!1 &300
GameObject:
  m_Name: Child2
  m_Component:
  - component: {fileID: 301}
--- !u!4 &301
Transform:
  m_GameObject: {fileID: 300}
  m_Father: {fileID: 101}
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.prefab', delete=False) as f:
            f.write(complex_content)
            temp_path = Path(f.name)
        
        try:
            parser = PrefabParser()
            result = parser.parse(temp_path)
            
            assert result.is_success
            data = result.data
            
            # 验证GameObject数量
            assert data['total_objects'] == 3
            
            # 验证层次结构
            game_objects = data['game_objects']
            obj_names = [obj['name'] for obj in game_objects if isinstance(obj, dict)]
            assert 'Parent' in obj_names
            assert 'Child1' in obj_names
            assert 'Child2' in obj_names
            
            # 验证组件引用
            component_refs = data['component_references']
            assert len(component_refs) > 0
            
            # 应该有父子关系
            parent_relations = [
                ref for ref in component_refs 
                if isinstance(ref, dict) and ref.get('relationship') == 'parent'
            ]
            child_relations = [
                ref for ref in component_refs 
                if isinstance(ref, dict) and ref.get('relationship') == 'child'
            ]
            
            assert len(parent_relations) == 2  # Child1和Child2都有父对象
            assert len(child_relations) == 2   # Parent有两个子对象
            
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_parser_info(self):
        """测试解析器信息"""
        parser = PrefabParser(strict_mode=True)
        info = parser.get_parser_info()
        
        assert isinstance(info, dict)
        assert info['name'] == 'PrefabParser'
        assert info['supported_extensions'] == ['.prefab']
        assert info['strict_mode'] is True
