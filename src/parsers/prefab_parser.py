"""Unity Prefab文件解析器

专门处理Unity .prefab文件的解析，提取GameObject层次结构和组件引用关系。
"""

import re
from typing import Dict, Any, Optional, List, Set, Tuple
from pathlib import Path
import logging
from dataclasses import dataclass
from enum import Enum

from .base_parser import BaseParser, ParseResult, ParseResultType
from ..utils.yaml_utils import YAMLParser

logger = logging.getLogger(__name__)


class ComponentType(Enum):
    """Unity组件类型枚举"""
    TRANSFORM = "Transform"
    RECT_TRANSFORM = "RectTransform"
    MESH_RENDERER = "MeshRenderer"
    MESH_FILTER = "MeshFilter"
    COLLIDER = "Collider"
    RIGIDBODY = "Rigidbody"
    AUDIO_SOURCE = "AudioSource"
    LIGHT = "Light"
    CAMERA = "Camera"
    CANVAS = "Canvas"
    UI_ELEMENT = "UIElement"
    MONO_BEHAVIOUR = "MonoBehaviour"
    PREFAB_INSTANCE = "PrefabInstance"
    GAME_OBJECT = "GameObject"
    UNKNOWN = "Unknown"
    
    @classmethod
    def from_class_id(cls, class_id: int) -> 'ComponentType':
        """从Unity类ID获取组件类型"""
        # Unity常见组件的类ID映射
        class_id_map = {
            1: cls.GAME_OBJECT,
            4: cls.TRANSFORM,
            23: cls.MESH_RENDERER,
            33: cls.MESH_FILTER,
            54: cls.RIGIDBODY,
            82: cls.AUDIO_SOURCE,
            108: cls.LIGHT,
            20: cls.CAMERA,
            223: cls.CANVAS,
            114: cls.MONO_BEHAVIOUR,
            1001: cls.PREFAB_INSTANCE,
            224: cls.RECT_TRANSFORM
        }
        return class_id_map.get(class_id, cls.UNKNOWN)


@dataclass
class ReferenceInfo:
    """引用信息数据类"""
    file_id: str
    guid: str
    type: int
    property_path: str
    reference_type: str = "unknown"
    
    def __str__(self) -> str:
        return f"Ref({self.guid}:{self.file_id})"


@dataclass
class GameObjectInfo:
    """GameObject信息数据类"""
    file_id: str
    name: str
    components: List[Dict[str, Any]]
    children: List[str]  # 子对象的file_id列表
    parent: Optional[str] = None  # 父对象的file_id
    layer: int = 0
    tag: str = "Untagged"
    active: bool = True
    
    def __str__(self) -> str:
        return f"GameObject({self.name})"


class PrefabParser(BaseParser):
    """Unity Prefab文件解析器
    
    解析.prefab文件的YAML结构，提取GameObject层次和组件引用。
    """
    
    def __init__(self, strict_mode: bool = False):
        """初始化Prefab解析器
        
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
        self.component_reference_pattern = re.compile(
            r'component:\s*\{fileID:\s*(-?\d+)\}',
            re.IGNORECASE
        )
        
        logger.info("Prefab解析器初始化完成")
    
    def can_parse(self, file_path: Path) -> bool:
        """判断是否可以解析指定文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            可以解析返回True，否则返回False
        """
        return file_path.suffix.lower() == '.prefab'
    
    def get_supported_extensions(self) -> List[str]:
        """获取支持的文件扩展名列表
        
        Returns:
            支持的扩展名列表
        """
        return ['.prefab']
    
    def parse(self, file_path: Path) -> ParseResult:
        """解析Prefab文件
        
        Args:
            file_path: Prefab文件路径
            
        Returns:
            解析结果
        """
        if not self.validate_file_path(file_path):
            return self.create_failed_result(file_path, "文件路径验证失败")
        
        try:
            logger.debug(f"开始解析Prefab文件: {file_path}")
            
            # 读取并解析YAML内容
            file_content = file_path.read_text(encoding='utf-8')
            yaml_documents = self._parse_unity_yaml(file_content)
            if not yaml_documents:
                return self.create_failed_result(file_path, "无法解析YAML文档")
            
            # 解析GameObject层次结构
            game_objects = self._extract_game_objects(yaml_documents)
            
            # 提取所有引用关系
            references = self._extract_references(file_content)
            
            # 提取组件引用
            component_references = self._extract_component_references(yaml_documents)
            
            # 构建解析数据
            data = {
                'game_objects': [obj.__dict__ for obj in game_objects],
                'references': [ref.__dict__ for ref in references],
                'component_references': component_references,
                'total_objects': len(game_objects),
                'total_references': len(references),
                'root_objects': self._find_root_objects(game_objects)
            }
            
            logger.info(f"Prefab解析完成: {len(game_objects)}个GameObject, {len(references)}个引用")
            
            return self.create_success_result(
                file_path=file_path,
                asset_type="Prefab",
                data=data
            )
            
        except Exception as e:
            error_msg = f"解析Prefab文件时发生错误: {str(e)}"
            logger.error(error_msg)
            return self.create_failed_result(file_path, error_msg)
    
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
        
        return component_refs
    
    def _extract_file_id(self, key: str) -> Optional[str]:
        """从YAML key中提取file ID
        
        Args:
            key: YAML key，格式如 "GameObject &1234567890"
            
        Returns:
            file ID字符串或None
        """
        # 匹配格式: "GameObject &1234567890" 或 "Transform &1234567890"
        match = re.search(r'&(\d+)', key)
        if match:
            return match.group(1)
        
        # 尝试其他格式
        match = re.search(r'fileID:\s*(\d+)', key)
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
            1002: "EditorExtensionImpl"
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
    
    def _find_root_objects(self, game_objects: List[GameObjectInfo]) -> List[str]:
        """查找根GameObject（没有父对象的GameObject）
        
        Args:
            game_objects: GameObject列表
            
        Returns:
            根GameObject的file_id列表
        """
        # 构建父子关系映射
        children_set = set()
        for obj in game_objects:
            children_set.update(obj.children)
        
        # 找到没有父对象的GameObject
        root_objects = []
        for obj in game_objects:
            if obj.file_id not in children_set:
                root_objects.append(obj.file_id)
        
        return root_objects
    
    def get_prefab_hierarchy(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """获取Prefab的层次结构信息
        
        Args:
            file_path: Prefab文件路径
            
        Returns:
            层次结构信息字典或None
        """
        result = self.parse(file_path)
        if not result.is_success or not result.data:
            return None
        
        game_objects = result.data.get('game_objects', [])
        if not game_objects:
            return None
        
        # 构建层次结构树
        hierarchy = {
            'root_objects': result.data.get('root_objects', []),
            'total_objects': result.data.get('total_objects', 0),
            'objects': {obj['file_id']: obj for obj in game_objects}
        }
        
        return hierarchy
    
    def extract_asset_references(self, file_path: Path) -> List[str]:
        """提取Prefab中引用的外部资源GUID列表
        
        Args:
            file_path: Prefab文件路径
            
        Returns:
            GUID列表
        """
        result = self.parse(file_path)
        if not result.is_success or not result.data:
            return []
        
        references = result.data.get('references', [])
        guids = set()
        
        for ref in references:
            if isinstance(ref, dict) and ref.get('guid'):
                # 过滤掉内部引用（guid为全零）
                guid = ref['guid']
                if guid and guid != '00000000000000000000000000000000':
                    guids.add(guid)
        
        return list(guids)


def create_prefab_parser(strict_mode: bool = False) -> PrefabParser:
    """创建Prefab解析器的便捷函数
    
    Args:
        strict_mode: 是否启用严格模式
        
    Returns:
        PrefabParser实例
    """
    return PrefabParser(strict_mode)
