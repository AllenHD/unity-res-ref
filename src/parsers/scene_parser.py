"""Unity Scene文件解析器

专门处理Unity .scene文件的解析，提取场景中的GameObject层次结构和组件引用关系。
"""

import re
from typing import Dict, Any, Optional, List, Set, Tuple
from pathlib import Path
import logging
from dataclasses import dataclass

from .base_parser import BaseParser, ParseResult, ParseResultType
from .prefab_parser import GameObjectInfo, ReferenceInfo, ComponentType
from ..utils.yaml_utils import YAMLParser

logger = logging.getLogger(__name__)


@dataclass
class SceneInfo:
    """场景信息数据类"""
    name: str
    build_index: int = -1
    is_loading_scene: bool = False
    scene_settings: Optional[Dict[str, Any]] = None
    lighting_settings: Optional[Dict[str, Any]] = None
    
    def __str__(self) -> str:
        return f"Scene({self.name})"


@dataclass 
class PrefabInstanceInfo:
    """Prefab实例信息数据类"""
    file_id: str
    prefab_asset_guid: str
    source_prefab: Optional[str] = None
    modifications: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.modifications is None:
            self.modifications = []
    
    def __str__(self) -> str:
        return f"PrefabInstance({self.prefab_asset_guid})"


class SceneParser(BaseParser):
    """Unity Scene文件解析器
    
    解析.scene/.unity文件的YAML结构，提取场景中的GameObject和组件引用。
    """
    
    def __init__(self, strict_mode: bool = False):
        """初始化Scene解析器
        
        Args:
            strict_mode: 严格模式，遇到错误时立即失败
        """
        super().__init__(strict_mode)
        self.yaml_parser = YAMLParser()
        
        # 编译正则表达式模式
        self.guid_pattern = re.compile(r'guid:\s*([a-f0-9]{32})', re.IGNORECASE)
        self.file_id_pattern = re.compile(r'fileID:\s*(-?\d+)', re.IGNORECASE)
        self.reference_pattern = re.compile(
            r'\{fileID:\s*(-?\d+),\s*guid:\s*([a-f0-9]{32}),\s*type:\s*(\d+)\}',
            re.IGNORECASE
        )
        self.scene_object_pattern = re.compile(
            r'--- !u!(\d+)\s+&(\d+)',
            re.IGNORECASE
        )
        
        logger.info("Scene解析器初始化完成")
    
    def can_parse(self, file_path: Path) -> bool:
        """判断是否可以解析指定文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            可以解析返回True，否则返回False
        """
        return file_path.suffix.lower() in ['.scene', '.unity']
    
    def get_supported_extensions(self) -> List[str]:
        """获取支持的文件扩展名列表
        
        Returns:
            支持的扩展名列表
        """
        return ['.scene', '.unity']
    
    def parse(self, file_path: Path) -> ParseResult:
        """解析Scene文件
        
        Args:
            file_path: Scene文件路径
            
        Returns:
            解析结果
        """
        if not self.validate_file_path(file_path):
            return self.create_failed_result(file_path, "文件路径验证失败")
        
        try:
            logger.debug(f"开始解析Scene文件: {file_path}")
            
            # 读取文件内容
            file_content = file_path.read_text(encoding='utf-8')
            
            # 解析YAML文档
            yaml_documents = self._parse_unity_yaml(file_content)
            if not yaml_documents:
                return self.create_failed_result(file_path, "无法解析YAML文档")
            
            # 提取场景信息
            scene_info = self._extract_scene_info(yaml_documents)
            
            # 提取GameObject
            game_objects = self._extract_game_objects(yaml_documents)
            
            # 提取Prefab实例
            prefab_instances = self._extract_prefab_instances(yaml_documents)
            
            # 提取所有引用关系
            references = self._extract_references(file_content)
            
            # 提取组件引用
            component_references = self._extract_component_references(yaml_documents)
            
            # 分析场景结构
            scene_hierarchy = self._build_scene_hierarchy(game_objects, prefab_instances)
            
            # 构建解析数据
            data = {
                'scene_info': scene_info.__dict__ if scene_info else None,
                'game_objects': [obj.__dict__ for obj in game_objects],
                'prefab_instances': [inst.__dict__ for inst in prefab_instances],
                'references': [ref.__dict__ for ref in references],
                'component_references': component_references,
                'scene_hierarchy': scene_hierarchy,
                'statistics': {
                    'total_objects': len(game_objects),
                    'total_prefab_instances': len(prefab_instances),
                    'total_references': len(references),
                    'root_objects': len(scene_hierarchy.get('root_objects', [])),
                    'max_depth': scene_hierarchy.get('max_depth', 0)
                }
            }
            
            logger.info(f"Scene解析完成: {len(game_objects)}个GameObject, "
                       f"{len(prefab_instances)}个Prefab实例, {len(references)}个引用")
            
            return self.create_success_result(
                file_path=file_path,
                asset_type="Scene",
                data=data
            )
            
        except Exception as e:
            error_msg = f"解析Scene文件时发生错误: {str(e)}"
            logger.error(error_msg)
            return self.create_failed_result(file_path, error_msg)
    
    def _extract_scene_info(self, yaml_documents: List[Dict[str, Any]]) -> Optional[SceneInfo]:
        """从YAML文档中提取场景信息
        
        Args:
            yaml_documents: YAML文档列表
            
        Returns:
            SceneInfo对象或None
        """
        for doc in yaml_documents:
            if not isinstance(doc, dict):
                continue
            
            # 查找SceneSettings
            for key, value in doc.items():
                if 'SceneSettings' in key and isinstance(value, dict):
                    return SceneInfo(
                        name=value.get('m_Name', 'Untitled Scene'),
                        build_index=value.get('m_BuildIndex', -1),
                        scene_settings=value
                    )
        
        return SceneInfo(name="Unknown Scene")
    
    def _extract_game_objects(self, yaml_documents: List[Dict[str, Any]]) -> List[GameObjectInfo]:
        """从YAML文档中提取GameObject信息
        
        Args:
            yaml_documents: YAML文档列表
            
        Returns:
            GameObject信息列表
        """
        game_objects = []
        
        for doc in yaml_documents:
            if not isinstance(doc, dict):
                continue
            
            # 检查是否是GameObject (Unity class ID 1)
            class_id = doc.get('_unity_class_id')
            file_id = doc.get('_unity_file_id')
            
            if class_id == '1':  # GameObject的Unity class ID是1
                try:
                    # 在Unity YAML中，GameObject数据直接在文档中
                    # 我们需要过滤掉Unity特定的键
                    gameobject_data = {k: v for k, v in doc.items() 
                                     if not k.startswith('_unity_')}
                    
                    if gameobject_data and file_id:
                        game_obj = self._parse_game_object(file_id, gameobject_data)
                        if game_obj:
                            game_objects.append(game_obj)
                except Exception as e:
                    logger.warning(f"解析GameObject时出错: {e}")
                    continue
        
        return game_objects
    
    def _extract_prefab_instances(self, yaml_documents: List[Dict[str, Any]]) -> List[PrefabInstanceInfo]:
        """从YAML文档中提取Prefab实例信息
        
        Args:
            yaml_documents: YAML文档列表
            
        Returns:
            Prefab实例信息列表
        """
        prefab_instances = []
        
        for doc in yaml_documents:
            if not isinstance(doc, dict):
                continue
            
            # 查找PrefabInstance条目
            for key, value in doc.items():
                if 'PrefabInstance' in key and isinstance(value, dict):
                    try:
                        file_id = self._extract_file_id(key)
                        if file_id:
                            prefab_inst = self._parse_prefab_instance(file_id, value)
                            if prefab_inst:
                                prefab_instances.append(prefab_inst)
                    except Exception as e:
                        logger.warning(f"解析PrefabInstance时出错: {e}")
                        continue
        
        return prefab_instances
    
    def _parse_game_object(self, file_id: str, data: Dict[str, Any]) -> Optional[GameObjectInfo]:
        """解析单个GameObject数据
        
        Args:
            file_id: GameObject的file ID
            data: GameObject数据
            
        Returns:
            GameObjectInfo对象或None
        """
        try:
            name = data.get('m_Name', 'Unnamed')
            layer = int(data.get('m_Layer', 0)) if data.get('m_Layer') is not None else 0
            tag = data.get('m_TagString', 'Untagged')
            active = bool(data.get('m_IsActive', True)) if data.get('m_IsActive') is not None else True
            
            # 解析组件列表
            components = []
            component_list = data.get('m_Component', [])
            
            if isinstance(component_list, list):
                for component in component_list:
                    if isinstance(component, dict) and 'component' in component:
                        components.append(component)
            
            return GameObjectInfo(
                file_id=file_id,
                name=name,
                components=components,
                children=[],  # 稍后通过Transform组件填充
                layer=layer,
                tag=tag,
                active=active
            )
            
        except Exception as e:
            logger.warning(f"解析GameObject数据时出错: {e}")
            return None
    
    def _parse_prefab_instance(self, file_id: str, data: Dict[str, Any]) -> Optional[PrefabInstanceInfo]:
        """解析Prefab实例数据
        
        Args:
            file_id: PrefabInstance的file ID
            data: PrefabInstance数据
            
        Returns:
            PrefabInstanceInfo对象或None
        """
        try:
            # 提取源Prefab信息
            source_prefab = data.get('m_SourcePrefab', {})
            prefab_guid = ''
            
            if isinstance(source_prefab, dict):
                prefab_guid = source_prefab.get('guid', '')
            
            # 提取修改信息
            modifications = []
            modification_list = data.get('m_Modification', {}).get('m_Modifications', [])
            
            if isinstance(modification_list, list):
                for mod in modification_list:
                    if isinstance(mod, dict):
                        modifications.append(mod)
            
            return PrefabInstanceInfo(
                file_id=file_id,
                prefab_asset_guid=prefab_guid,
                source_prefab=source_prefab.get('fileID'),
                modifications=modifications
            )
            
        except Exception as e:
            logger.warning(f"解析PrefabInstance数据时出错: {e}")
            return None
    
    def _extract_references(self, content: str) -> List[ReferenceInfo]:
        """从文件内容中提取所有引用关系
        
        Args:
            content: 文件内容
            
        Returns:
            引用信息列表
        """
        references = []
        
        # 查找所有引用模式
        matches = self.reference_pattern.finditer(content)
        
        for match in matches:
            file_id = match.group(1)
            guid = match.group(2)
            ref_type = int(match.group(3)) if match.group(3).isdigit() else 0
            
            # 确定引用类型
            reference_type = self._determine_reference_type(ref_type)
            
            # 查找属性路径上下文
            property_path = self._find_property_path(content, match.start())
            
            reference = ReferenceInfo(
                file_id=file_id,
                guid=guid,
                type=ref_type,
                property_path=property_path,
                reference_type=reference_type
            )
            
            references.append(reference)
        
        return references
    
    def _extract_component_references(self, yaml_documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """提取组件之间的引用关系
        
        Args:
            yaml_documents: YAML文档列表
            
        Returns:
            组件引用信息列表
        """
        component_refs = []
        
        for doc in yaml_documents:
            if not isinstance(doc, dict):
                continue
            
            for key, value in doc.items():
                # 检查Transform和RectTransform组件
                if ('Transform' in key or 'RectTransform' in key) and isinstance(value, dict):
                    file_id = self._extract_file_id(key)
                    if file_id:
                        # 提取父子关系
                        parent_ref = value.get('m_Father', {})
                        children_refs = value.get('m_Children', [])
                        
                        if parent_ref and isinstance(parent_ref, dict):
                            component_refs.append({
                                'source_file_id': file_id,
                                'target_file_id': parent_ref.get('fileID'),
                                'relationship': 'parent',
                                'component_type': 'Transform'
                            })
                        
                        if children_refs and isinstance(children_refs, list):
                            for child_ref in children_refs:
                                if isinstance(child_ref, dict):
                                    component_refs.append({
                                        'source_file_id': file_id,
                                        'target_file_id': child_ref.get('fileID'),
                                        'relationship': 'child',
                                        'component_type': 'Transform'
                                    })
                
                # 检查其他组件类型的引用
                elif ('MonoBehaviour' in key or 'Component' in key) and isinstance(value, dict):
                    file_id = self._extract_file_id(key)
                    if file_id:
                        # 提取脚本引用
                        script_ref = value.get('m_Script', {})
                        if script_ref and isinstance(script_ref, dict):
                            component_refs.append({
                                'source_file_id': file_id,
                                'target_file_id': script_ref.get('fileID'),
                                'target_guid': script_ref.get('guid'),
                                'relationship': 'script_reference',
                                'component_type': 'MonoBehaviour'
                            })
        
        return component_refs
    
    def _build_scene_hierarchy(
        self, 
        game_objects: List[GameObjectInfo], 
        prefab_instances: List[PrefabInstanceInfo]
    ) -> Dict[str, Any]:
        """构建场景层次结构
        
        Args:
            game_objects: GameObject列表
            prefab_instances: Prefab实例列表
            
        Returns:
            场景层次结构信息
        """
        # 构建对象映射
        object_map = {obj.file_id: obj for obj in game_objects}
        
        # 查找根对象（没有父对象的对象）
        all_children = set()
        for obj in game_objects:
            all_children.update(obj.children)
        
        root_objects = []
        for obj in game_objects:
            if obj.file_id not in all_children:
                root_objects.append(obj.file_id)
        
        # 计算最大深度
        def calculate_depth(obj_id: str, visited: Set[str] = None) -> int:
            if visited is None:
                visited = set()
            
            if obj_id in visited:  # 防止循环引用
                return 0
            
            visited.add(obj_id)
            obj = object_map.get(obj_id)
            if not obj or not obj.children:
                return 1
            
            max_child_depth = max(
                calculate_depth(child_id, visited.copy()) 
                for child_id in obj.children
            )
            return 1 + max_child_depth
        
        max_depth = 0
        for root_id in root_objects:
            depth = calculate_depth(root_id)
            max_depth = max(max_depth, depth)
        
        return {
            'root_objects': root_objects,
            'max_depth': max_depth,
            'total_prefab_instances': len(prefab_instances),
            'prefab_guids': list(set(inst.prefab_asset_guid for inst in prefab_instances))
        }
    
    def _extract_file_id(self, key: str) -> Optional[str]:
        """从YAML key中提取file ID
        
        Args:
            key: YAML key，格式如 "GameObject &1234567890"
            
        Returns:
            file ID字符串或None
        """
        # 匹配格式: "GameObject &1234567890" 或其他组件
        match = re.search(r'&(\d+)', key)
        if match:
            return match.group(1)
        
        return None
    
    def _determine_reference_type(self, type_id: int) -> str:
        """根据类型ID确定引用类型
        
        Args:
            type_id: Unity类型ID
            
        Returns:
            引用类型字符串
        """
        # Unity资源类型ID映射
        type_map = {
            2: "Material",
            21: "Material", 
            43: "Mesh",
            74: "AnimationClip", 
            83: "AudioClip",
            128: "Font",
            213: "Sprite",
            28: "Texture2D",
            89: "CubemapTexture",
            48: "Shader",
            114: "MonoScript",
            115: "MonoScript",
            1001: "PrefabInstance",
            1002: "EditorExtensionImpl",
            157: "LightingDataAsset",
            156: "TerrainData"
        }
        
        return type_map.get(type_id, f"Unknown({type_id})")
    
    def _find_property_path(self, content: str, position: int) -> str:
        """查找引用所在的属性路径
        
        Args:
            content: 文件内容
            position: 引用在文件中的位置
            
        Returns:
            属性路径字符串
        """
        # 向前查找属性名
        before_content = content[:position]
        lines = before_content.split('\n')
        
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if line and ':' in line and not line.startswith('#'):
                # 提取属性名
                property_name = line.split(':')[0].strip()
                if property_name and not property_name.startswith('{'):
                    return property_name
        
        return "unknown"
    
    def get_scene_objects_by_type(self, file_path: Path, object_type: str) -> List[Dict[str, Any]]:
        """按类型获取场景中的对象
        
        Args:
            file_path: Scene文件路径
            object_type: 对象类型（如'Camera', 'Light'等）
            
        Returns:
            对象信息列表
        """
        result = self.parse(file_path)
        if not result.is_success or not result.data:
            return []
        
        game_objects = result.data.get('game_objects', [])
        filtered_objects = []
        
        for obj in game_objects:
            if isinstance(obj, dict):
                components = obj.get('components', [])
                for component in components:
                    if isinstance(component, dict):
                        component_ref = component.get('component', {})
                        # 这里可以根据组件类型进一步过滤
                        # 实际实现需要解析组件的具体类型
                        pass
        
        return filtered_objects
    
    def extract_prefab_dependencies(self, file_path: Path) -> List[str]:
        """提取场景中引用的Prefab GUID列表
        
        Args:
            file_path: Scene文件路径
            
        Returns:
            Prefab GUID列表
        """
        result = self.parse(file_path)
        if not result.is_success or not result.data:
            return []
        
        prefab_instances = result.data.get('prefab_instances', [])
        guids = set()
        
        for instance in prefab_instances:
            if isinstance(instance, dict) and instance.get('prefab_asset_guid'):
                guid = instance['prefab_asset_guid']
                if guid and guid != '00000000000000000000000000000000':
                    guids.add(guid)
        
        return list(guids)


def create_scene_parser(strict_mode: bool = False) -> SceneParser:
    """创建Scene解析器的便捷函数
    
    Args:
        strict_mode: 是否启用严格模式
        
    Returns:
        SceneParser实例
    """
    return SceneParser(strict_mode)
