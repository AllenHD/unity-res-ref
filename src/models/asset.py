"""Unity Resource Reference Scanner - Asset Data Model

资源数据模型定义，用于存储Unity项目中的资源信息。
包含GUID、路径、类型、元数据等核心信息。
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum

from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Index, Boolean
from sqlalchemy.orm import DeclarativeBase, relationship

class Base(DeclarativeBase):
    pass


class AssetType(str, Enum):
    """Unity资源类型枚举"""
    PREFAB = "prefab"
    SCENE = "scene"
    SCRIPT = "script"
    TEXTURE = "texture"
    MATERIAL = "material"
    MESH = "mesh"
    AUDIO = "audio"
    ANIMATION = "animation"
    ANIMATOR_CONTROLLER = "animator_controller"
    SHADER = "shader"
    COMPUTE_SHADER = "compute_shader"
    FONT = "font"
    VIDEO = "video"
    RENDER_TEXTURE = "render_texture"
    CUBEMAP = "cubemap"
    LIGHTMAP = "lightmap"
    TERRAIN_DATA = "terrain_data"
    PHYSICS_MATERIAL = "physics_material"
    AVATAR_MASK = "avatar_mask"
    SPRITE_ATLAS = "sprite_atlas"
    TILEMAP = "tilemap"
    UNKNOWN = "unknown"


class Asset(Base):
    """Unity资源数据模型
    
    存储Unity项目中每个资源的基本信息，包括GUID、路径、类型等。
    作为依赖关系分析和资源管理的核心数据结构。
    """
    __tablename__ = "assets"

    # 主键：Unity资源的GUID，确保唯一性
    guid = Column(String(32), primary_key=True, comment="Unity资源GUID")
    
    # 资源基本信息
    file_path = Column(String(512), nullable=False, comment="资源文件路径")
    asset_type = Column(String(50), nullable=False, comment="资源类型")
    file_size = Column(Integer, nullable=True, comment="文件大小(字节)")
    
    # 时间戳信息
    created_at = Column(DateTime, default=datetime.utcnow, comment="记录创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="记录更新时间")
    file_modified_at = Column(DateTime, nullable=True, comment="文件最后修改时间")
    
    # 扫描状态
    is_active = Column(Boolean, default=True, comment="资源是否活跃(存在)")
    is_analyzed = Column(Boolean, default=False, comment="是否已分析依赖关系")
    
    # 元数据和扩展信息（JSON格式存储）
    asset_metadata = Column(JSON, nullable=True, comment="资源元数据信息")
    import_settings = Column(JSON, nullable=True, comment="资源导入设置")
    
    # 依赖关系（通过外键关联）
    outgoing_dependencies = relationship(
        "Dependency",
        foreign_keys="Dependency.source_guid",
        back_populates="source_asset",
        cascade="all, delete-orphan"
    )
    
    incoming_dependencies = relationship(
        "Dependency", 
        foreign_keys="Dependency.target_guid",
        back_populates="target_asset"
    )

    # 数据库索引定义
    __table_args__ = (
        Index('idx_asset_file_path', 'file_path'),
        Index('idx_asset_type', 'asset_type'),
        Index('idx_asset_created_at', 'created_at'),
        Index('idx_asset_updated_at', 'updated_at'),
        Index('idx_asset_active', 'is_active'),
        Index('idx_asset_analyzed', 'is_analyzed'),
        Index('idx_asset_file_modified', 'file_modified_at'),
        # 复合索引用于常见查询
        Index('idx_asset_type_active', 'asset_type', 'is_active'),
        Index('idx_asset_path_type', 'file_path', 'asset_type'),
    )

    def __init__(self, guid: str, file_path: str, asset_type: str, **kwargs):
        """初始化Asset实例
        
        Args:
            guid: Unity资源GUID
            file_path: 资源文件路径
            asset_type: 资源类型
            **kwargs: 其他可选参数
        """
        self.guid = guid
        self.file_path = str(file_path)
        self.asset_type = asset_type
        
        # 设置默认值
        self.is_active = kwargs.get('is_active', True)
        self.is_analyzed = kwargs.get('is_analyzed', False)
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self.updated_at = kwargs.get('updated_at', datetime.utcnow())
        
        # 设置其他属性
        for key, value in kwargs.items():
            if hasattr(self, key) and key not in ['is_active', 'is_analyzed', 'created_at', 'updated_at']:
                setattr(self, key, value)

    @property
    def path(self) -> Path:
        """获取文件路径对象"""
        return Path(self.file_path)

    @property
    def name(self) -> str:
        """获取资源文件名"""
        return self.path.name

    @property
    def extension(self) -> str:
        """获取文件扩展名"""
        return self.path.suffix.lower()

    @property
    def directory(self) -> str:
        """获取资源所在目录"""
        return str(self.path.parent)

    @classmethod
    def detect_asset_type(cls, file_path: str) -> AssetType:
        """根据文件扩展名检测资源类型
        
        Args:
            file_path: 文件路径
            
        Returns:
            AssetType: 检测到的资源类型
        """
        ext = Path(file_path).suffix.lower()
        
        type_mapping = {
            '.prefab': AssetType.PREFAB,
            '.scene': AssetType.SCENE,
            '.cs': AssetType.SCRIPT,
            '.js': AssetType.SCRIPT,
            '.boo': AssetType.SCRIPT,
            '.png': AssetType.TEXTURE,
            '.jpg': AssetType.TEXTURE,
            '.jpeg': AssetType.TEXTURE,
            '.tga': AssetType.TEXTURE,
            '.bmp': AssetType.TEXTURE,
            '.tiff': AssetType.TEXTURE,
            '.gif': AssetType.TEXTURE,
            '.psd': AssetType.TEXTURE,
            '.mat': AssetType.MATERIAL,
            '.fbx': AssetType.MESH,
            '.obj': AssetType.MESH,
            '.dae': AssetType.MESH,
            '.3ds': AssetType.MESH,
            '.blend': AssetType.MESH,
            '.wav': AssetType.AUDIO,
            '.mp3': AssetType.AUDIO,
            '.ogg': AssetType.AUDIO,
            '.aiff': AssetType.AUDIO,
            '.anim': AssetType.ANIMATION,
            '.controller': AssetType.ANIMATOR_CONTROLLER,
            '.shader': AssetType.SHADER,
            '.compute': AssetType.COMPUTE_SHADER,
            '.ttf': AssetType.FONT,
            '.otf': AssetType.FONT,
            '.fontsettings': AssetType.FONT,
            '.mp4': AssetType.VIDEO,
            '.mov': AssetType.VIDEO,
            '.avi': AssetType.VIDEO,
            '.webm': AssetType.VIDEO,
            '.renderTexture': AssetType.RENDER_TEXTURE,
            '.cubemap': AssetType.CUBEMAP,
            '.physicMaterial': AssetType.PHYSICS_MATERIAL,
            '.mask': AssetType.AVATAR_MASK,
            '.spriteatlas': AssetType.SPRITE_ATLAS,
        }
        
        return type_mapping.get(ext, AssetType.UNKNOWN)

    def update_metadata(self, metadata: Dict[str, Any]) -> None:
        """更新资源元数据
        
        Args:
            metadata: 元数据字典
        """
        if self.asset_metadata is None:
            self.asset_metadata = {}
        self.asset_metadata.update(metadata)
        self.updated_at = datetime.utcnow()

    def update_import_settings(self, import_settings: Dict[str, Any]) -> None:
        """更新导入设置
        
        Args:
            import_settings: 导入设置字典
        """
        if self.import_settings is None:
            self.import_settings = {}
        self.import_settings.update(import_settings)
        self.updated_at = datetime.utcnow()

    def mark_as_analyzed(self) -> None:
        """标记资源已完成依赖分析"""
        self.is_analyzed = True
        self.updated_at = datetime.utcnow()

    def mark_as_inactive(self) -> None:
        """标记资源为非活跃状态（已删除或移动）"""
        self.is_active = False
        self.updated_at = datetime.utcnow()

    def __repr__(self) -> str:
        """字符串表示"""
        return f"<Asset(guid='{self.guid}', path='{self.file_path}', type='{self.asset_type}')>"

    def __str__(self) -> str:
        """用户友好的字符串表示"""
        return f"{self.name} ({self.asset_type})"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式
        
        Returns:
            Dict[str, Any]: 资源信息字典
        """
        return {
            'guid': self.guid,
            'file_path': self.file_path,
            'asset_type': self.asset_type,
            'file_size': self.file_size,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'file_modified_at': self.file_modified_at.isoformat() if self.file_modified_at else None,
            'is_active': self.is_active,
            'is_analyzed': self.is_analyzed,
            'asset_metadata': self.asset_metadata,
            'import_settings': self.import_settings,
        }
