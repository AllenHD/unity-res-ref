"""Unity Resource Reference Scanner - Configuration Management System

配置管理系统，支持YAML配置文件加载、验证、默认值处理和运行时配置更新。
使用Pydantic进行数据验证，支持配置文件的层级结构和环境变量覆盖。
"""

import os
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from enum import Enum

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from ruamel.yaml import YAML


class LogLevel(str, Enum):
    """日志级别枚举"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DatabaseType(str, Enum):
    """数据库类型枚举"""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"


class ExportFormat(str, Enum):
    """导出格式枚举"""
    JSON = "json"
    CSV = "csv"
    DOT = "dot"
    XML = "xml"


class ProjectConfig(BaseModel):
    """项目基础配置"""
    name: str = Field(default="Unity Project Scanner", description="项目名称")
    unity_project_path: Path = Field(default=Path("."), description="Unity项目根路径")
    unity_version: Optional[str] = Field(default=None, description="Unity版本")

    @field_validator('unity_project_path')
    @classmethod
    def validate_unity_project_path(cls, v):
        """验证Unity项目路径"""
        if v and not Path(v).exists():
            raise ValueError(f"Unity项目路径不存在: {v}")
        return Path(v).resolve() if v else Path(".")

    @field_validator('unity_version')
    @classmethod
    def validate_unity_version(cls, v):
        """验证Unity版本格式"""
        if v and not v.replace(".", "").replace("f", "").isdigit():
            raise ValueError(f"Unity版本格式无效: {v}")
        return v


class ScanConfig(BaseModel):
    """扫描配置"""
    paths: List[str] = Field(
        default=["Assets/", "Packages/"], 
        description="扫描路径列表"
    )
    exclude_paths: List[str] = Field(
        default=[
            "Assets/StreamingAssets/",
            "Assets/Plugins/Android/",
            "Assets/Plugins/iOS/",
            "Library/",
            "Temp/",
            "Build/",
            "Logs/"
        ],
        description="排除路径列表"
    )
    file_extensions: List[str] = Field(
        default=[".prefab", ".scene", ".asset", ".mat", ".controller", ".anim", ".cs"],
        description="扫描的文件扩展名"
    )
    max_file_size_mb: int = Field(
        default=50, 
        ge=1, 
        le=1000, 
        description="最大文件大小限制(MB)"
    )
    ignore_hidden_files: bool = Field(
        default=True, 
        description="是否忽略隐藏文件"
    )

    @field_validator('paths')
    @classmethod
    def validate_paths(cls, v):
        """验证扫描路径"""
        if not v:
            raise ValueError("扫描路径不能为空")
        return [path.rstrip('/') + '/' for path in v if path.strip()]

    @field_validator('file_extensions')
    @classmethod
    def validate_file_extensions(cls, v):
        """验证文件扩展名"""
        valid_extensions = []
        for ext in v:
            if not ext.startswith('.'):
                ext = '.' + ext
            valid_extensions.append(ext.lower())
        return valid_extensions


class DatabaseConfig(BaseModel):
    """数据库配置"""
    type: DatabaseType = Field(default=DatabaseType.SQLITE, description="数据库类型")
    path: str = Field(default="./unity_deps.db", description="数据库路径")
    backup_enabled: bool = Field(default=True, description="是否启用自动备份")
    backup_interval_hours: int = Field(
        default=24, 
        ge=1, 
        le=168, 
        description="备份间隔(小时)"
    )
    vacuum_on_startup: bool = Field(
        default=False, 
        description="启动时是否压缩数据库"
    )

    @property
    def url(self) -> str:
        """获取数据库连接URL"""
        if self.type == DatabaseType.SQLITE:
            db_path = Path(self.path).resolve()
            return f"sqlite:///{db_path}"
        else:
            # 其他数据库类型的连接字符串可以在此扩展
            return self.path

    @field_validator('path')
    @classmethod
    def validate_database_path(cls, v, info):
        """验证数据库路径"""
        values = info.data if info else {}
        db_type = values.get('type', DatabaseType.SQLITE)
        if db_type == DatabaseType.SQLITE:
            db_path = Path(v)
            # 确保父目录存在
            db_path.parent.mkdir(parents=True, exist_ok=True)
        return v


class PerformanceConfig(BaseModel):
    """性能配置"""
    max_workers: int = Field(
        default=4, 
        ge=1, 
        le=32, 
        description="最大工作线程数"
    )
    batch_size: int = Field(
        default=100, 
        ge=10, 
        le=1000, 
        description="批处理大小"
    )
    memory_limit_mb: int = Field(
        default=512, 
        ge=128, 
        le=4096, 
        description="内存使用限制(MB)"
    )
    enable_async_io: bool = Field(
        default=True, 
        description="启用异步I/O"
    )
    cache_size_mb: int = Field(
        default=128, 
        ge=32, 
        le=1024, 
        description="解析缓存大小(MB)"
    )

    @field_validator('max_workers')
    @classmethod
    def validate_max_workers(cls, v):
        """验证最大工作线程数"""
        cpu_count = os.cpu_count() or 4
        if v > cpu_count * 2:
            return cpu_count * 2
        return v


class OutputConfig(BaseModel):
    """输出配置"""
    verbosity: LogLevel = Field(default=LogLevel.INFO, description="日志级别")
    progress_bar: bool = Field(default=True, description="显示进度条")
    color_output: bool = Field(default=True, description="彩色输出")
    export_formats: List[ExportFormat] = Field(
        default=[ExportFormat.JSON, ExportFormat.CSV, ExportFormat.DOT],
        description="支持的导出格式"
    )

    @field_validator('color_output')
    @classmethod
    def validate_color_output(cls, v):
        """在非终端环境中禁用彩色输出"""
        if v and not sys.stdout.isatty():
            return False
        return v


class FeaturesConfig(BaseModel):
    """功能特性配置"""
    detect_unused_assets: bool = Field(
        default=True, 
        description="检测未使用资源"
    )
    detect_circular_deps: bool = Field(
        default=True, 
        description="检测循环依赖"
    )
    generate_reports: bool = Field(
        default=True, 
        description="生成报告"
    )
    web_interface: bool = Field(
        default=False, 
        description="启用Web界面"
    )


class AppConfig(BaseModel):
    """应用程序完整配置"""
    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True,
        extra="forbid"
    )
    
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    scan: ScanConfig = Field(default_factory=ScanConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)

    @model_validator(mode='after')
    def validate_config_consistency(self):
        """验证配置的一致性"""
        # 检查Unity项目路径与扫描路径的一致性
        project = self.project
        scan = self.scan
        
        if project and scan:
            unity_path = project.unity_project_path
            for scan_path in scan.paths:
                full_path = unity_path / scan_path
                if not full_path.exists() and unity_path != Path("."):
                    print(f"Warning: 扫描路径不存在: {full_path}")
        
        return self


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认为config/default.yaml
        """
        self.config_path = self._resolve_config_path(config_path)
        self._config: Optional[AppConfig] = None
        self._yaml = YAML()
        self._yaml.preserve_quotes = True
        self._yaml.width = 4096

    def _resolve_config_path(self, config_path: Optional[Union[str, Path]]) -> Path:
        """解析配置文件路径"""
        if config_path:
            return Path(config_path).resolve()
        
        # 尝试多个默认位置
        default_paths = [
            Path("config/default.yaml"),
            Path("../config/default.yaml"),
            Path("./default.yaml"),
        ]
        
        for path in default_paths:
            if path.exists():
                return path.resolve()
        
        # 如果都不存在，返回默认路径
        return Path("config/default.yaml").resolve()

    def load_config(self, reload: bool = False) -> AppConfig:
        """加载配置文件
        
        Args:
            reload: 是否强制重新加载
            
        Returns:
            AppConfig: 应用配置实例
            
        Raises:
            FileNotFoundError: 配置文件不存在
            ValueError: 配置文件格式错误或验证失败
        """
        if self._config and not reload:
            return self._config

        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            # 应用环境变量覆盖
            config_data = self._apply_env_overrides(config_data)
            
            # 创建配置实例
            self._config = AppConfig(**config_data)
            
            return self._config
            
        except Exception as e:
            raise ValueError(f"配置文件加载失败 {self.config_path}: {e}")

    def _apply_env_overrides(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """应用环境变量覆盖
        
        环境变量格式: UNITY_SCANNER_<SECTION>_<KEY>
        例如: UNITY_SCANNER_SCAN_MAX_FILE_SIZE_MB=100
        """
        env_prefix = "UNITY_SCANNER_"
        
        for key, value in os.environ.items():
            if not key.startswith(env_prefix):
                continue
                
            # 解析环境变量键
            config_key = key[len(env_prefix):].lower()
            parts = config_key.split('_')
            
            if len(parts) < 2:
                continue
                
            section = parts[0]
            field = '_'.join(parts[1:])
            
            if section in config_data:
                # 类型转换
                converted_value = self._convert_env_value(value)
                config_data[section][field] = converted_value
                
        return config_data

    def _convert_env_value(self, value: str) -> Union[str, int, float, bool, List[str]]:
        """转换环境变量值到合适的类型"""
        # 布尔值
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # 整数
        if value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
            return int(value)
        
        # 浮点数
        try:
            return float(value)
        except ValueError:
            pass
        
        # 列表（逗号分隔）
        if ',' in value:
            return [item.strip() for item in value.split(',') if item.strip()]
        
        # 字符串
        return value

    def save_config(self, config: AppConfig, path: Optional[Path] = None) -> None:
        """保存配置到文件
        
        Args:
            config: 要保存的配置
            path: 保存路径，默认为当前配置文件路径
        """
        save_path = path or self.config_path
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 转换为字典，将枚举转换为字符串值
        config_dict = config.model_dump(by_alias=True, exclude_unset=False)
        
        # 转换特殊对象为字符串以便YAML序列化
        self._convert_objects_to_strings(config_dict)
        
        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                self._yaml.dump(config_dict, f)
                
        except Exception as e:
            raise ValueError(f"配置文件保存失败 {save_path}: {e}")

    def _convert_objects_to_strings(self, data: Dict[str, Any]) -> None:
        """递归转换Path对象和枚举为字符串"""
        from enum import Enum
        
        for key, value in data.items():
            if isinstance(value, Path):
                data[key] = str(value)
            elif isinstance(value, Enum):
                data[key] = value.value
            elif isinstance(value, dict):
                self._convert_objects_to_strings(value)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, Path):
                        value[i] = str(item)
                    elif isinstance(item, Enum):
                        value[i] = item.value
                    elif isinstance(item, dict):
                        self._convert_objects_to_strings(item)

    def generate_default_config(self, path: Optional[Path] = None) -> None:
        """生成默认配置文件
        
        Args:
            path: 生成路径，默认为config/default.yaml
        """
        default_config = AppConfig()
        save_path = path or Path("config/default.yaml")
        self.save_config(default_config, save_path)

    @property
    def config(self) -> AppConfig:
        """获取当前配置"""
        if not self._config:
            self._config = self.load_config()
        return self._config

    def reload(self) -> AppConfig:
        """重新加载配置"""
        return self.load_config(reload=True)

    def update_config(self, updates: Dict[str, Any]) -> AppConfig:
        """更新配置
        
        Args:
            updates: 更新的配置项
            
        Returns:
            AppConfig: 更新后的配置
        """
        current = self.config.model_dump()
        
        # 深度合并更新
        def deep_merge(base_dict: Dict, update_dict: Dict) -> Dict:
            for key, value in update_dict.items():
                if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                    deep_merge(base_dict[key], value)
                else:
                    base_dict[key] = value
            return base_dict
        
        updated = deep_merge(current, updates)
        self._config = AppConfig(**updated)
        
        return self._config


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_path: Optional[Union[str, Path]] = None) -> ConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager
    if _config_manager is None or config_path:
        _config_manager = ConfigManager(config_path)
    return _config_manager


def get_config() -> AppConfig:
    """获取当前应用配置"""
    return get_config_manager().config


def reload_config() -> AppConfig:
    """重新加载配置"""
    return get_config_manager().reload()
