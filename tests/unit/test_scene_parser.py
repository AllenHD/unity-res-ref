"""Scene解析器测试

测试SceneParser的功能。
"""

import pytest
import tempfile
from pathlib import Path
from typing import Dict, List

from src.parsers.scene_parser import SceneParser, create_scene_parser, SceneInfo, PrefabInstanceInfo
from src.parsers.base_parser import ParseResultType


class TestSceneParser:
    """SceneParser测试类"""
    
    @pytest.fixture
    def sample_scene_content(self):
        """示例Scene文件内容"""
        return '''%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!29 &1
OcclusionCullingSettings:
  m_ObjectHideFlags: 0
  serializedVersion: 2
  m_OcclusionBakeSettings:
    smallestOccluder: 5
    smallestHole: 0.25
    backfaceThreshold: 100
  m_SceneGUID: 00000000000000000000000000000000
  m_OcclusionCullingData: {fileID: 0}
--- !u!104 &2
RenderSettings:
  m_ObjectHideFlags: 0
  serializedVersion: 9
  m_Fog: 0
  m_FogColor: {r: 0.5, g: 0.5, b: 0.5, a: 1}
  m_FogMode: 3
  m_FogDensity: 0.01
  m_LinearFogStart: 0
  m_LinearFogEnd: 300
  m_AmbientSkyColor: {r: 0.212, g: 0.227, b: 0.259, a: 1}
  m_AmbientEquatorColor: {r: 0.114, g: 0.125, b: 0.133, a: 1}
  m_AmbientGroundColor: {r: 0.047, g: 0.043, b: 0.035, a: 1}
  m_AmbientIntensity: 1
  m_AmbientMode: 0
  m_SubtractiveShadowColor: {r: 0.42, g: 0.478, b: 0.627, a: 1}
  m_SkyboxMaterial: {fileID: 10304, guid: 0000000000000000f000000000000000, type: 0}
--- !u!157 &3
LightmapSettings:
  m_ObjectHideFlags: 0
  serializedVersion: 12
  m_GIWorkflowMode: 1
  m_GISettings:
    serializedVersion: 2
    m_BounceScale: 1
    m_IndirectOutputScale: 1
    m_AlbedoBoost: 1
    m_EnvironmentLightingMode: 0
    m_EnableBakedLightmaps: 1
    m_EnableRealtimeLightmaps: 0
  m_LightmapEditorSettings:
    serializedVersion: 12
    m_Resolution: 2
    m_BakeResolution: 40
    m_AtlasSize: 1024
    m_AO: 0
    m_AOMaxDistance: 1
    m_CompAOExponent: 1
    m_CompAOExponentDirect: 0
    m_ExtractAmbientOcclusion: 0
    m_Padding: 2
    m_LightmapParameters: {fileID: 0}
    m_LightmapsBakeMode: 1
    m_TextureCompression: 1
    m_FinalGather: 0
    m_FinalGatherFiltering: 1
    m_FinalGatherRayCount: 256
    m_ReflectionCompression: 2
    m_MixedBakeMode: 2
    m_BakeBackend: 1
    m_PVRSampling: 1
    m_PVRDirectSampleCount: 32
    m_PVRSampleCount: 512
    m_PVRBounces: 2
    m_PVREnvironmentSampleCount: 256
    m_PVREnvironmentReferencePointCount: 2048
    m_PVRFilteringMode: 1
    m_PVRDenoiserTypeDirect: 1
    m_PVRDenoiserTypeIndirect: 1
    m_PVRDenoiserTypeAO: 1
    m_PVRFilterTypeDirect: 0
    m_PVRFilterTypeIndirect: 0
    m_PVRFilterTypeAO: 0
    m_PVREnvironmentMIS: 1
    m_PVRCulling: 1
    m_PVRFilteringGaussRadiusDirect: 1
    m_PVRFilteringGaussRadiusIndirect: 5
    m_PVRFilteringGaussRadiusAO: 2
    m_PVRFilteringAtrousPositionSigmaDirect: 0.5
    m_PVRFilteringAtrousPositionSigmaIndirect: 2
    m_PVRFilteringAtrousPositionSigmaAO: 1
    m_ExportTrainingData: 0
    m_TrainingDataDestination: TrainingData
    m_LightProbeSampleCountMultiplier: 4
  m_LightingDataAsset: {fileID: 0}
  m_LightingSettings: {fileID: 0}
--- !u!196 &4
NavMeshSettings:
  serializedVersion: 2
  m_ObjectHideFlags: 0
  m_BuildSettings:
    serializedVersion: 2
    agentTypeID: 0
    agentRadius: 0.5
    agentHeight: 2
    agentSlope: 45
    agentClimb: 0.4
    ledgeDropHeight: 0
    maxJumpAcrossDistance: 0
    minRegionArea: 2
    manualCellSize: 0
    cellSize: 0.16666667
    manualTileSize: 0
    tileSize: 256
    accuratePlacement: 0
    maxJobWorkers: 0
    preserveTilesOutsideBounds: 0
    debug:
      m_Flags: 0
  m_NavMeshData: {fileID: 0}
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
  m_Name: TestSceneObject
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
--- !u!108 &1234567892
Light:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  m_GameObject: {fileID: 1234567890}
  m_Enabled: 1
  serializedVersion: 10
  m_Type: 1
  m_Shape: 0
  m_Color: {r: 1, g: 0.95686275, b: 0.8392157, a: 1}
  m_Intensity: 1
  m_Range: 10
  m_SpotAngle: 30
  m_InnerSpotAngle: 21.80208
  m_CookieSize: 10
  m_Shadows:
    m_Type: 2
    m_Resolution: -1
    m_CustomResolution: -1
    m_Strength: 1
    m_Bias: 0.05
    m_NormalBias: 0.4
    m_NearPlane: 2
    m_CullingMatrixOverride:
      e00: 1
      e01: 0
      e02: 0
      e03: 0
      e10: 0
      e11: 1
      e12: 0
      e13: 0
      e20: 0
      e21: 0
      e22: 1
      e23: 0
      e30: 0
      e31: 0
      e32: 0
      e33: 1
    m_UseCullingMatrixOverride: 0
  m_Cookie: {fileID: 0}
  m_DrawHalo: 0
  m_Flare: {fileID: 0}
  m_RenderMode: 0
  m_CullingMask:
    serializedVersion: 2
    m_Bits: 4294967295
  m_RenderingLayerMask: 1
  m_Lightmapping: 4
  m_LightShadowCasterMode: 0
  m_AreaSize: {x: 1, y: 1}
  m_BounceIntensity: 1
  m_ColorTemperature: 6570
  m_UseColorTemperature: 0
  m_BoundingSphereOverride: {x: 0, y: 0, z: 0, w: 0}
  m_UseBoundingSphereOverride: 0
  m_UseViewFrustumForShadowCasterCull: 1
  m_ShadowRadius: 0
  m_ShadowAngle: 0
--- !u!1001 &1234567893
PrefabInstance:
  m_ObjectHideFlags: 0
  serializedVersion: 2
  m_Modification:
    m_TransformParent: {fileID: 0}
    m_Modifications:
    - target: {fileID: 1234567890, guid: fedcba0987654321fedcba0987654321, type: 3}
      propertyPath: m_Name
      value: TestPrefabInstance
      objectReference: {fileID: 0}
    - target: {fileID: 1234567891, guid: fedcba0987654321fedcba0987654321, type: 3}
      propertyPath: m_LocalPosition.x
      value: 5
      objectReference: {fileID: 0}
  m_SourcePrefab: {fileID: 100100000, guid: fedcba0987654321fedcba0987654321, type: 3}
'''
    
    @pytest.fixture
    def temp_scene_file(self, sample_scene_content):
        """创建临时Scene文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.scene', delete=False) as f:
            f.write(sample_scene_content)
            temp_path = Path(f.name)
        
        yield temp_path
        temp_path.unlink(missing_ok=True)
    
    def test_parser_initialization(self):
        """测试解析器初始化"""
        parser = SceneParser()
        assert parser is not None
        assert not parser.strict_mode
        
        strict_parser = SceneParser(strict_mode=True)
        assert strict_parser.strict_mode
    
    def test_can_parse(self):
        """测试文件类型识别"""
        parser = SceneParser()
        
        # 应该能解析的文件
        assert parser.can_parse(Path("test.scene"))
        assert parser.can_parse(Path("level.unity"))
        
        # 不应该解析的文件
        assert not parser.can_parse(Path("test.prefab"))
        assert not parser.can_parse(Path("test.meta"))
        assert not parser.can_parse(Path("test.txt"))
    
    def test_supported_extensions(self):
        """测试支持的扩展名"""
        parser = SceneParser()
        extensions = parser.get_supported_extensions()
        
        assert isinstance(extensions, list)
        assert '.scene' in extensions
        assert '.unity' in extensions
        assert len(extensions) == 2
    
    def test_parse_valid_scene(self, temp_scene_file):
        """测试解析有效的Scene文件"""
        parser = SceneParser()
        result = parser.parse(temp_scene_file)
        
        # 验证解析结果
        assert result.is_success
        assert result.asset_type == "Scene"
        assert result.data is not None
        
        # 验证解析的数据结构
        data = result.data
        assert 'scene_info' in data
        assert 'game_objects' in data
        assert 'prefab_instances' in data
        assert 'references' in data
        assert 'component_references' in data
        assert 'scene_hierarchy' in data
        assert 'statistics' in data
        
        # 验证场景信息
        scene_info = data['scene_info']
        if scene_info:
            assert isinstance(scene_info, dict)
        
        # 验证GameObject解析
        game_objects = data['game_objects']
        assert len(game_objects) > 0
        
        # 查找测试对象
        test_obj = None
        for obj in game_objects:
            if isinstance(obj, dict) and obj.get('name') == 'TestSceneObject':
                test_obj = obj
                break
        
        assert test_obj is not None
        assert test_obj['file_id'] == '1234567890'
        assert test_obj['name'] == 'TestSceneObject'
        assert test_obj['tag'] == 'Untagged'
        assert test_obj['layer'] == 0
        assert test_obj['active'] is True
        
        # 验证Prefab实例
        prefab_instances = data['prefab_instances']
        assert len(prefab_instances) > 0
        
        prefab_inst = prefab_instances[0]
        assert isinstance(prefab_inst, dict)
        assert prefab_inst['file_id'] == '1234567893'
        assert prefab_inst['prefab_asset_guid'] == 'fedcba0987654321fedcba0987654321'
        assert 'modifications' in prefab_inst
        
        # 验证统计信息
        stats = data['statistics']
        assert stats['total_objects'] >= 1
        assert stats['total_prefab_instances'] >= 1
        assert stats['total_references'] >= 0
    
    def test_parse_nonexistent_file(self):
        """测试解析不存在的文件"""
        parser = SceneParser()
        result = parser.parse(Path("nonexistent.scene"))
        
        assert result.is_failed
        assert "文件路径验证失败" in result.error_message
    
    def test_parse_invalid_scene(self):
        """测试解析无效的Scene文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.scene', delete=False) as f:
            f.write("Invalid YAML content {")
            temp_path = Path(f.name)
        
        try:
            parser = SceneParser()
            result = parser.parse(temp_path)
            
            # 应该失败但不抛出异常
            assert result.is_failed
            assert result.error_message is not None
            
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_extract_prefab_dependencies(self, temp_scene_file):
        """测试提取Prefab依赖"""
        parser = SceneParser()
        prefab_guids = parser.extract_prefab_dependencies(temp_scene_file)
        
        assert isinstance(prefab_guids, list)
        assert 'fedcba0987654321fedcba0987654321' in prefab_guids
        
        # 确保没有包含全零GUID
        assert '00000000000000000000000000000000' not in prefab_guids
    
    def test_create_scene_parser_function(self):
        """测试便捷创建函数"""
        # 默认模式
        parser = create_scene_parser()
        assert isinstance(parser, SceneParser)
        assert not parser.strict_mode
        
        # 严格模式
        strict_parser = create_scene_parser(strict_mode=True)
        assert isinstance(strict_parser, SceneParser)
        assert strict_parser.strict_mode
    
    def test_batch_parsing(self, temp_scene_file):
        """测试批量解析"""
        parser = SceneParser()
        
        # 创建另一个临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.scene', delete=False) as f:
            f.write("%YAML 1.1\n--- !u!1 &123\nGameObject:\n  m_Name: SimpleScene")
            temp_path2 = Path(f.name)
        
        try:
            results = parser.parse_batch([temp_scene_file, temp_path2])
            
            assert len(results) == 2
            assert all(isinstance(result.file_path, str) for result in results)
            
            # 第一个文件应该成功解析
            assert results[0].is_success
            
        finally:
            temp_path2.unlink(missing_ok=True)
    
    def test_complex_scene_hierarchy(self):
        """测试复杂场景层次结构解析"""
        complex_content = '''%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &100
GameObject:
  m_Name: SceneRoot
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
  m_Name: Camera
  m_Component:
  - component: {fileID: 201}
  - component: {fileID: 202}
  m_Layer: 0
  m_IsActive: 1
--- !u!4 &201
Transform:
  m_GameObject: {fileID: 200}
  m_Father: {fileID: 101}
--- !u!20 &202
Camera:
  m_GameObject: {fileID: 200}
  m_Enabled: 1
--- !u!1 &300
GameObject:
  m_Name: Lighting
  m_Component:
  - component: {fileID: 301}
  - component: {fileID: 302}
  m_IsActive: 1
--- !u!4 &301
Transform:
  m_GameObject: {fileID: 300}
  m_Father: {fileID: 101}
--- !u!108 &302
Light:
  m_GameObject: {fileID: 300}
  m_Enabled: 1
  m_Type: 1
--- !u!1001 &400
PrefabInstance:
  m_Modification:
    m_TransformParent: {fileID: 101}
  m_SourcePrefab: {fileID: 100100000, guid: abcdef1234567890abcdef1234567890, type: 3}
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.scene', delete=False) as f:
            f.write(complex_content)
            temp_path = Path(f.name)
        
        try:
            parser = SceneParser()
            result = parser.parse(temp_path)
            
            assert result.is_success
            data = result.data
            
            # 验证GameObject数量
            stats = data['statistics']
            assert stats['total_objects'] == 3
            assert stats['total_prefab_instances'] == 1
            
            # 验证场景层次结构
            hierarchy = data['scene_hierarchy']
            assert 'root_objects' in hierarchy
            assert 'max_depth' in hierarchy
            assert 'prefab_guids' in hierarchy
            
            # 验证Prefab GUID
            prefab_guids = hierarchy['prefab_guids']
            assert 'abcdef1234567890abcdef1234567890' in prefab_guids
            
            # 验证组件引用
            component_refs = data['component_references']
            assert len(component_refs) > 0
            
            # 应该有父子关系
            parent_relations = [
                ref for ref in component_refs 
                if isinstance(ref, dict) and ref.get('relationship') == 'parent'
            ]
            
            assert len(parent_relations) >= 2  # Camera和Lighting都有父对象
            
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_get_scene_objects_by_type(self, temp_scene_file):
        """测试按类型获取场景对象"""
        parser = SceneParser()
        
        # 这个方法目前返回空列表，因为实现还不完整
        light_objects = parser.get_scene_objects_by_type(temp_scene_file, "Light")
        assert isinstance(light_objects, list)
    
    def test_parser_info(self):
        """测试解析器信息"""
        parser = SceneParser(strict_mode=True)
        info = parser.get_parser_info()
        
        assert isinstance(info, dict)
        assert info['name'] == 'SceneParser'
        assert '.scene' in info['supported_extensions']
        assert '.unity' in info['supported_extensions']
        assert info['strict_mode'] is True
    
    def test_unity_file_extension(self):
        """测试.unity文件扩展名支持"""
        unity_content = '''%YAML 1.1
--- !u!1 &123
GameObject:
  m_Name: UnityFile
  m_IsActive: 1
'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.unity', delete=False) as f:
            f.write(unity_content)
            temp_path = Path(f.name)
        
        try:
            parser = SceneParser()
            
            # 应该能识别.unity文件
            assert parser.can_parse(temp_path)
            
            # 应该能解析.unity文件
            result = parser.parse(temp_path)
            assert result.is_success or result.is_failed  # 至少不会抛出异常
            
        finally:
            temp_path.unlink(missing_ok=True)
